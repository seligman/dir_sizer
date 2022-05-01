#!/usr/bin/env python3

from collections import defaultdict
from datetime import datetime, timedelta
from utils import TempMessage, size_to_string, count_to_string, register_abstraction, chunks
from aws_constants import S3_COST_CLASSES
import json
try:
    # Wrap boto3 in a try/except block so we can still show the help, but
    # only fail if the user tries to call into S3
    import boto3
    IMPORTS_OK = True
except:
    IMPORTS_OK = False
register_abstraction(__name__)

MAIN_SWITCH = "--s3"
DESCRIPTION = "Scan AWS S3 for object sizes"

# TODO: A flag to sort by "cost"

def handle_args(opts, args):
    if not IMPORTS_OK:
        opts['show_help'] = True
        print("ERROR: Unable to import boto3, unable to call S3 APIs!")

    while not opts['show_help']:
        if len(args) >= 2 and args[0] == "--profile":
            opts['s3_profile'] = args[1]
            args = args[2:]
        elif len(args) >= 2 and args[0] == "--bucket":
            opts['s3_bucket'] = args[1]
            args = args[2:]
        elif len(args) >= 2 and args[0] == "--prefix":
            opts['s3_prefix'] = args[1]
            args = args[2:]
        elif len(args) >= 1 and args[0] == "--all_buckets":
            opts['s3_all_buckets'] = True
            args = args[1:]
        elif len(args) >= 1 and args[0] == "--cost":
            opts['s3_cost'] = True
            args = args[1:]
        else:
            break
    
    if not opts['show_help']:
        if 's3_bucket' in opts:
            if 's3_all_buckets' in opts:
                opts['show_help'] = True
                print("ERROR: Both bucket and all_buckets specified, options are mutually exclusive")
        elif 's3_all_buckets' in opts:
            if 's3_bucket' in opts:
                opts['show_help'] = True
                print("ERROR: Both bucket and all_buckets specified, options are mutually exclusive")
            elif 's3_prefix' in opts:
                opts['show_help'] = True
                print("ERROR: Both prefix and all_buckets specified, options are mutually exclusive")
        else:
            opts['show_help'] = True
            print("ERROR: Neither bucket or all_buckets specified")

    return args

def get_help():
    return f"""
        --profile <value> = AWS CLI profile name to use (optional)
        --bucket <value>  = S3 Bucket to scan
        --prefix <value>  = Prefix to start scanning from (optional)
        --all_buckets     = Show size of all buckets (only if --bucket/--prefix isn't used)
        --cost            = Count cost instead of size for objects
    """ + ("" if IMPORTS_OK else """
        WARNING: boto3 import failed, module will not work correctly!
    """)

def get_bucket_location(s3, bucket):
    location = s3.get_bucket_location(Bucket=bucket)['LocationConstraint']
    # us-east-1 and eu-west-1 are odd, they have weird values from this API, so map to the proper region
    location = {None: 'us-east-1', 'EU': 'eu-west-1'}.get(location, location)
    return location

def scan_folder(opts):
    if 's3_profile' in opts:
        s3 = boto3.Session(profile_name=opts['s3_profile']).client('s3')
    else:
        s3 = boto3.client('s3')

    msg = TempMessage()
    msg("Scanning...", force=True)

    total_objects, total_size = 0, 0
    if 's3_bucket' in opts:
        # Enumerate the objects in the target bucket
        paginator = s3.get_paginator("list_objects_v2")
        args = {"Bucket": opts['s3_bucket']}
        prefix_len = 0
        if 's3_prefix' in opts:
            args['Prefix'] = opts['s3_prefix']
            prefix_len = len(opts['s3_prefix'])
        
        if opts.get('s3_cost', False):
            location = get_bucket_location(s3, opts['s3_bucket'])
            with open("s3_pricing_data.json") as f:
                temp = json.load(f)
                if location not in temp:
                    raise Exception(f"Unknown costs for region {location}!")
                # Lookup table to look up a S3 Storage Class to price per GiB
                costs = {x['s3']: float(temp[location][x['desc']]) for x in S3_COST_CLASSES}
        else:
            location = None
            costs = None

        for page in paginator.paginate(**args):
            for cur in page['Contents']:
                if location is None:
                    size = cur['Size']
                else:
                    # We're in s3_cost mode, so use the cost as the size
                    # This is (<size> / 1 GiB) * <price per GiB>
                    size = (cur['Size'] / 1073741824) * costs[cur['StorageClass']]
                total_objects += 1
                total_size += size
                yield cur['Key'][prefix_len:].split("/"), size
            msg(f"Scanning, gathered {total_objects} totaling {dump_size(opts, total_size)}...")
    else:
        # List all the buckets, break out by region
        buckets = defaultdict(list)
        for i, bucket in enumerate(s3.list_buckets()['Buckets']):
            msg(f"Scanning, finding buckets, gathered data for {i} buckets...")
            bucket = bucket['Name']
            location = get_bucket_location(s3, bucket)
            buckets[location].append(bucket)

        # The range to query from CloudWatch, basically, get the latest metric for each bucket, 
        # with some padding to handle the daily roll off of data
        now = datetime.utcnow()
        now = datetime(now.year, now.month, now.day)
        start_date = now - timedelta(hours=36)
        stats = defaultdict(lambda: defaultdict(dict))
        bucket_to_region = {}

        for region in buckets:
            queries = []
            bucket_ids = {}
            if 's3_profile' in opts:
                cw = boto3.Session(profile_name=opts['s3_profile']).client('cloudwatch', region_name=region)
            else:
                cw = boto3.client('cloudwatch', region_name=region)

            # Pull out all of the possible cost classes
            storages = [(x['cw'], 'BucketSizeBytes', True) for x in S3_COST_CLASSES]
            # And ask for the number of objects in each bucket as well
            storages.append(('AllStorageTypes', 'NumberOfObjects', False))

            # For each bucket in this region, add a request for each metric we want to track
            for bucket in buckets[region]:
                bucket_to_region[bucket] = region
                bucket_ids[bucket] = "%02d" % (len(bucket_ids),)
                for storage, metric_name, _cost in storages:
                    queries.append({
                            'Id': 'i' + bucket_ids[bucket] + storage,
                            'MetricStat': {
                                'Metric': {
                                    'Namespace': 'AWS/S3',
                                    'MetricName': metric_name,
                                    'Dimensions': [
                                        {'Name': 'StorageType', 'Value': storage},
                                        {'Name': 'BucketName', 'Value': bucket},
                                    ],
                                },
                                'Period': 86400,
                                'Stat': 'Average',
                            }
                        })

            # A place to store the metrics we'll gather up
            final_metrics = {}
            
            # Call into cloudwatch as few times as possible
            for chunk_page, queries_chunk in enumerate(chunks(queries, 100)):
                msg(f"Scanning, got {len(queries_chunk)} stats for {region}, on page {chunk_page+1}, done with {len(stats)} buckets...")
                metrics = cw.get_metric_data(
                    MetricDataQueries=queries_chunk,
                    StartTime=start_date,
                    EndTime=start_date + timedelta(days=1)
                )
                # The metrics are returned in a list, turn it into a dictionary to make things easier
                for cur in metrics['MetricDataResults']:
                    final_metrics[cur['Id']] = cur

            # And for each bucket, pull out the metrics into our final stats object
            for bucket in buckets[region]:
                temp_cur = start_date.strftime("%Y-%m-%d")
                for storage, _metric_name, _cost in storages:
                    temp_metrics = final_metrics['i' + bucket_ids[bucket] + storage]
                    # Find the metric for the current day, treat lack of a value as 0
                    value = 0.0
                    for i in range(len(temp_metrics['Timestamps'])):
                        if temp_metrics['Timestamps'][i].strftime("%Y-%m-%d") == temp_cur:
                            value = temp_metrics['Values'][i]
                            break
                    # All of the values we want are really integers, so treat them as such
                    stats[bucket][storage] = int(value)

        # Load cost data if we want to use it
        if opts.get('s3_cost', False):
            costs = {}
            metric_to_cost = {x['cw']: x['desc'] for x in S3_COST_CLASSES}
            with open("s3_pricing_data.json") as f:
                temp = json.load(f)
                # Lookup table to look up a S3 Storage Class to price per GiB
                for region in buckets:
                    if region not in temp:
                        raise Exception(f"Unknown costs for region {region}!")
                    costs[region] = {x['cw']: float(temp[region][x['desc']]) for x in S3_COST_CLASSES}
        else:
            costs = None
            metric_to_cost = None

        # Create summary
        for bucket, bucket_stats in stats.items():
            size, count = 0, 0
            for storage, _metric_name, cost in storages:
                # Cost elements are storage in bytes, non-cost is the count (should only be one)
                if cost:
                    if costs is None:
                        size += bucket_stats.get(storage, 0)
                    else:
                        # This is (<size> / 1 GiB) * <price per GiB>
                        size += (bucket_stats.get(storage, 0) / 1073741824) * costs[bucket_to_region[bucket]][storage]
                else:
                    count += bucket_stats.get(storage, 0)
            # Store the results
            bucket_stats["_count"] = count
            bucket_stats["_size"] = size

        for bucket, bucket_stats in stats.items():
            if bucket_stats["_size"] > 0 and bucket_stats["_count"] > 0:
                total_objects += bucket_stats["_count"]
                total_size += bucket_stats["_size"]
                yield [bucket, ""], (bucket_stats["_size"], bucket_stats["_count"])

    msg(f"Done, saw {total_objects} totaling {dump_size(opts, total_size)}", newline=True)

def split(path):
    return path.split('/')

def join(path):
    return "/".join(path)

def dump_size(opts, value):
    if opts.get('s3_cost', False):
        return f"${value:0.2f}"
    else:
        return size_to_string(value)

def dump_count(opts, value):
    return count_to_string(value)

def get_summary(opts, folder):
    return {
        "Location": ("s3://" + opts['s3_bucket'] + "/" + opts.get('s3_prefix', "")) if 's3_bucket' in opts else "All Buckets",
        "Total objects": dump_count(opts, folder.count),
        "Total cost" if opts.get('s3_cost', False) else "Total size": dump_size(opts, folder.size),
    }

if __name__ == "__main__":
    print("This module is not meant to be run directly")
