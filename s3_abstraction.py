#!/usr/bin/env python3

from collections import defaultdict
from datetime import datetime, timedelta
from utils import chunks, count_to_string, hide_value, register_abstraction, size_to_string, TempMessage
from multiprocessing import Pool
from urllib.parse import unquote, unquote_plus
from aws_pager import aws_pager
import csv
import gzip
import io
import json
import os
import re
import sys
if sys.version_info >= (3, 11): from datetime import UTC
else: import datetime as datetime_fix; UTC=datetime_fix.timezone.utc
try:
    # Wrap boto3 in a try/except block so we can still show the help, but
    # only fail if the user tries to call into S3
    import boto3
    import botocore.exceptions
    from botocore import UNSIGNED
    from botocore.config import Config
    IMPORTS_OK = True
except:
    IMPORTS_OK = False
register_abstraction(__name__)

MAIN_SWITCH = "--s3"
FLAG_PREFIX = "s3_"
DESCRIPTION = "Scan AWS S3 for object sizes"

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
        elif len(args) >= 1 and args[0] == "--inventory":
            opts['s3_inventory'] = True
            args = args[1:]
        elif len(args) >= 1 and args[0] == "--no-sign-request":
            opts['no-sign-request'] = True
            args = args[1:]
        elif len(args) >= 2 and args[0] == "--endpoint":
            opts['s3_endpoint'] = args[1]
            args = args[2:]
        else:
            break
    
    if not opts['show_help']:
        exclusive = [
            ['bucket', ['all_buckets',]],
            ['all_buckets', ['bucket', 'prefix', 'inventory']],
        ]

        for opt_a, opts_b in exclusive:
            for opt_b in opts_b:
                if ('s3_' + opt_a) in opts and ('s3_' + opt_b) in opts:
                    opts['show_help'] = True
                    print(f"ERROR: Both {opt_a} and {opt_b} specified, options are mutually exclusive")
    elif ('s3_bucket' not in opts) and ('s3_all_buckets' not in opts):
        opts['show_help'] = True
        print("ERROR: Neither bucket or all_buckets specified")
    elif ('s3_endpoint' in opts) and ('s3_inventory' in opts):
        opts['show_help'] = True
        print("ERROR: AWS S3 Inventory not supported with custom endpoints")
    elif ('s3_endpoint' in opts) and ('s3_cost' in opts):
        opts['show_help'] = True
        print("ERROR: AWS S3 cost not supported with custom endpoints")
    elif ('s3_endpoint' in opts) and ('s3_all_buckets' in opts):
        opts['show_help'] = True
        print("ERROR: AWS S3 bucket list not supported with custom endpoints")

    return args

def get_help():
    return f"""
        --profile <value>  = AWS CLI profile name to use (optional)
        --bucket <value>   = S3 Bucket to scan
        --endpoint <value> = Custom endpoint URL to use for S3
        --inventory        = Use S3 Inventory report to get list of objects in bucket
        --prefix <value>   = Prefix to start scanning from (optional)
        --all_buckets      = Show size of all buckets (only if --bucket/--prefix isn't used)
                             (--profile may be a comma delimited list of profiles for this mode)
        --cost             = Count cost instead of size for objects
        --no-sign-request  = Don't sign requests
    """ + ("" if IMPORTS_OK else """
        WARNING: boto3 import failed, module will not work correctly!
    """)

def get_profiles(opts):
    # Helper to enumerate different profile options in opts
    for cur in opts.get("s3_profile", "").split(","):
        temp = opts.copy()
        temp['s3_profile'] = cur
        yield cur

def get_s3(opts, profile_name=None):
    args = {}
    if 's3_endpoint' in opts:
        args['endpoint_url'] = opts['s3_endpoint']

    if profile_name is None:
        profile = opts.get('s3_profile', '')
    else:
        profile = profile_name

    if "no-sign-request" in opts:
        args['config'] = Config(signature_version=UNSIGNED)

    if len(profile):
        return boto3.Session(profile_name=profile).client('s3', **args)
    else:
        return boto3.client('s3', **args)

def get_cw(profile, region):
    if len(profile):
        return boto3.Session(profile_name=profile).client('cloudwatch', region_name=region)
    else:
        return boto3.client('cloudwatch', region_name=region)

def get_bucket_location(s3, bucket):
    location = s3.get_bucket_location(Bucket=bucket)['LocationConstraint']
    # us-east-1 and eu-west-1 are odd, they have weird values from this API, so map to the proper region
    location = {None: 'us-east-1', 'EU': 'eu-west-1'}.get(location, location)
    return location

def get_bucket_location_worker(job):
    # Helper to handle lookup on a different process
    opts, profile, bucket = job
    s3 = get_s3(opts, profile)
    location = get_bucket_location(s3, bucket)
    return bucket, location

def load_s3_cost_classes():
    # Load the pricing data, using this module's location as an anchor point
    fn = os.path.join(os.path.split(__file__)[0], "s3_cost_classes.json")
    with open(fn) as f:
        return json.load(f)["classes"]

def load_pricing_data():
    # Load the pricing data, using this module's location as an anchor point
    fn = os.path.join(os.path.split(__file__)[0], "s3_pricing_data.json")
    with open(fn) as f:
        return json.load(f)

def get_bucket_inventory(msg, s3, bucket, required_fields=set(), prefix=""):
    # Load a S3 inventory report, including parsing CSV files
    possible_configs = []
    config = None

    for _, cur in aws_pager(s3, 'list_bucket_inventory_configurations', 'InventoryConfigurationList', Bucket=bucket):
        valid = True
        # Look for backup configs that match what we need
        if not cur.get("IsEnabled", False):
            # Needs to be an active inventory report
            valid = False
        elif cur.get('Destination', {}).get('S3BucketDestination', {}).get('Format', '') != "CSV":
            # Require CSV format
            valid = False
        elif len(set(cur['OptionalFields']) & required_fields) != len(required_fields):
            # Require different fields, at least Size, but might also need StorageClass for "cost"
            valid = False
        elif not prefix.startswith(cur.get('Filter', {}).get('Prefix', '')):
            # Only look at inventory reports that match the prefix we're given
            valid = False
        elif cur.get("IncludedObjectVersions", "") != "All":
            # Need all object versions to get an an accurate view of the bucket
            valid = False

        if valid:
            possible_configs.append(cur)

    if len(possible_configs) > 0:
        # Sort the configs to find the best one
        # Basically, prefer:
        #   Longer prefix (less data to download and parse)
        #   Daily over anything else (more up to date)
        #   Only current object versions (less data to download)
        #   Less fields (less data to download)
        # Other differences are ignored
        possible_configs.sort(key=lambda x: (
            -len(x.get("Filter", {}).get("Prefix", "")),
            1 if x.get("Schedule", {}).get("Frequency", "") == "Daily" else 2,
            1 if x.get("IncludedObjectVersions", "") == "Current" else 2,
            -len(x.get("OptionalFields", [])),
        ))
        # And pull out the best option
        config = possible_configs[0]

    if config is None:
        msg = f"Unable to find S3 Inventory report for '{bucket}'"
        if len(prefix) > 0:
            msg += f", that includes at least the prefix '{prefix}'"
        msg += ", in the CSV format"
        if len(required_fields) > 0:
            msg += ", with the optional fields of " + ', '.join(f"'{x}'" for x in required_fields)
        msg += ", that includes all object versions"
        raise Exception(msg)
    
    # Build up the location of the reports
    inv_bucket = config['Destination']['S3BucketDestination']['Bucket'].split(":")[5]
    inv_prefix = config['Destination']['S3BucketDestination'].get('Prefix', '')
    if len(inv_prefix) > 0:
        inv_prefix += "/"
    inv_prefix += bucket + "/"
    inv_prefix += config['Id'] + "/"

    # List all of the reports
    reports = []
    for _, prefix in aws_pager(s3, 'list_objects_v2', 'CommonPrefixes', Bucket=inv_bucket, Prefix=inv_prefix, Delimiter="/"):
        # Look for report "folders", ignoring the hive and data folders
        if re.search("[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}Z/$", prefix['Prefix']) is not None:
            reports.append(prefix['Prefix'] + "manifest.json")

    found = False
    # Find the latest report we can get
    for report in reports[::-1]:
        try:
            resp = s3.get_object(Bucket=inv_bucket, Key=report)
            found = True
        except botocore.exceptions.ClientError as ex:
            if ex.response['Error']['Code'] == 'NoSuchKey':
                # It might fail if it's in the middle of an upload, so 
                # ignore that edge case, and go back in time to an older report
                continue
            else:
                raise
        # Load the manifest file
        resp = json.loads(resp['Body'].read())

        updated = int(resp['creationTimestamp'])
        updated = datetime.fromtimestamp(updated/1000)
        msg(f'Using S3 Inventory report "{config["Id"]}" generated {updated.strftime("%Y-%m-%d %H:%M:%S")}...', newline=True, force=True)

        # Pull out the schema for these CSV files
        schema = [x.strip() for x in resp['fileSchema'].split(",")]
        for file in resp['files']:
            # And read through each row in this file
            csv_gz = s3.get_object(Bucket=inv_bucket, Key=file['key'])['Body']
            with gzip.GzipFile(fileobj=csv_gz) as gzf:
                sr = io.TextIOWrapper(gzf)
                cr = csv.reader(sr)
                for row in cr:
                    # Merge the schema and each row
                    row = {x: y for x, y in zip(schema, row)}
                    # Ignore Delete Markers and other objects that don't have a size
                    if len(row['Size']) > 0:
                        yield row

        # We're done with this report, don't move on to the next one
        break

    if not found:
        raise Exception(f"Unable to find any inventory report data files for report '{config['Id']}', has it run?")

def s3_list_objects(msg, opts, s3):
    # Wrapper to call list_object_versions normally, or call into Inventory
    # if that option is specified

    prefix_len = len(opts.get('s3_prefix', ''))

    if opts.get('s3_inventory', False):
        # Using a S3 Inventory report
        required_fields = {"Size"}
        if opts.get('s3_cost', False):
            required_fields.add("StorageClass")
        prefix = opts.get('s3_prefix', '')
        for row in get_bucket_inventory(msg, s3, opts['s3_bucket'], required_fields=required_fields, prefix=prefix):
            key = unquote(row['Key'])
            if key.startswith(prefix):
                yield {
                    'Key': key[prefix_len:],
                    'Size': int(row['Size']),
                    'StorageClass': row.get('StorageClass', ''),
                }
    else:
        # Normal mode, just call list_object_versions and pass the results along
        args = {"Bucket": opts['s3_bucket']}
        if 's3_prefix' in opts:
            args['Prefix'] = opts['s3_prefix']

        for _, cur in aws_pager(s3, 'list_object_versions', 'Versions', **args):
            yield {
                'Key': cur['Key'][prefix_len:],
                'Size': cur['Size'],
                'StorageClass': cur['StorageClass'],
            }

def scan_folder(opts):
    msg = TempMessage()
    msg("Scanning...", force=True)

    total_objects, total_size = 0, 0
    if 's3_bucket' in opts:
        # Enumerate the objects in the target bucket
        s3 = get_s3(opts)

        if opts.get('s3_cost', False):
            location = get_bucket_location(s3, opts['s3_bucket'])
            temp = load_pricing_data()
            if location not in temp:
                raise Exception(f"Unknown costs for region {location}!")
            # Lookup table to look up a S3 Storage Class to price per GiB
            costs = {x['s3']: float(temp[location][x['desc']]) for x in load_s3_cost_classes()}
        else:
            location = None
            costs = None

        for i, cur in enumerate(s3_list_objects(msg, opts, s3)):
            if location is None:
                size = cur['Size']
            else:
                # We're in s3_cost mode, so use the cost as the size
                # This is (<size> / 1 GiB) * <price per GiB>
                size = (cur['Size'] / 1073741824) * costs[cur['StorageClass']]
            total_objects += 1
            total_size += size
            yield cur['Key'].split("/"), size
            if i % 1000 == 999:
                msg(f"Scanning, gathered {total_objects} totaling {dump_size(opts, total_size)}...")
    else:
        # List all the buckets, break out by region
        buckets = defaultdict(lambda: defaultdict(list))
        seen_buckets = 0
        for profile in get_profiles(opts):
            s3 = get_s3(opts, profile)
            with Pool() as pool:
                temp = {x: y for x, y in opts.items() if x.startswith("s3_")}
                for bucket, location in pool.imap_unordered(get_bucket_location_worker, [(temp, profile, x['Name']) for x in s3.list_buckets()['Buckets']]):
                    seen_buckets += 1
                    msg(f"Scanning, finding buckets, gathered data for {seen_buckets} buckets...")
                    buckets[profile][location].append(bucket)

        # The range to query from CloudWatch, basically, get the latest metric for each bucket, 
        # with some padding to handle the daily roll off of data
        now = datetime.now(UTC).replace(tzinfo=None)
        now = datetime(now.year, now.month, now.day)
        start_date = now - timedelta(hours=36)
        stats = defaultdict(lambda: defaultdict(dict))
        bucket_to_region = {}

        for profile in buckets:
            for region in buckets[profile]:
                queries = []
                bucket_ids = {}
                cw = get_cw(profile, region)

                # Pull out all of the possible cost classes
                storages = [(x['cw'], 'BucketSizeBytes', True) for x in load_s3_cost_classes()]
                # And ask for the number of objects in each bucket as well
                storages.append(('AllStorageTypes', 'NumberOfObjects', False))

                # For each bucket in this region, add a request for each metric we want to track
                for bucket in buckets[profile][region]:
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
                for bucket in buckets[profile][region]:
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
                metric_to_cost = {x['cw']: x['desc'] for x in load_s3_cost_classes()}
                temp = load_pricing_data()
                # Lookup table to look up a S3 Storage Class to price per GiB
                for region in buckets[profile]:
                    if region not in temp:
                        raise Exception(f"Unknown costs for region {region}!")
                    costs[region] = {x['cw']: float(temp[region][x['desc']]) for x in load_s3_cost_classes()}
            else:
                costs = None
                metric_to_cost = None

            # Create summary
            for bucket, bucket_stats in stats.items():
                # Ignore buckets we've already seen on a previous profile run
                if "_count" not in bucket_stats:
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
    if 's3_bucket' in opts:
        location = "s3://"
        if opts['hide_names']:
            location += "example-bucket-" + hide_value(opts, opts['s3_bucket'])
        else:
            location += opts['s3_bucket']
        location += "/"
        if len(opts.get('s3_prefix', "")) > 0:
            if opts['hide_names']:
                location += hide_value(opts, opts.get('s3_prefix', ""))
            else:
                location += opts.get('s3_prefix', "")
    else:
        if 's3_profile' in opts:
            temp = opts['s3_profile'].split(",")
            location = "All buckets for " + ", ".join(temp) + " " + ("profile" if len(temp) == 1 else "profiles")
        else:
            location = "All buckets"
    return [
        ("Location", location),
        ("Total objects", dump_count(opts, folder.count)),
        ("Total cost" if opts.get('s3_cost', False) else "Total size", dump_size(opts, folder.size)),
    ]

if __name__ == "__main__":
    print("This module is not meant to be run directly")
