#!/usr/bin/env python3

from utils import TempMessage, size_to_string, count_to_string, register_abstraction
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
        return args

    while True:
        if len(args) >= 2 and args[0] == "--profile":
            opts['s3_profile'] = args[1]
            args = args[2:]
        elif len(args) >= 2 and args[0] == "--bucket":
            opts['s3_bucket'] = args[1]
            args = args[2:]
        elif len(args) >= 2 and args[0] == "--prefix":
            opts['s3_prefix'] = args[1]
            args = args[2:]
        else:
            break
    
    if not opts['show_help'] and 's3_bucket' not in opts:
        opts['show_help'] = True
        print("ERROR: No bucket specified for S3 mode")
    
    return args

def get_help():
    return f"""
        --profile <value> = AWS CLI profile name to use (optional)
        --bucket <value>  = S3 Bucket to scan
        --prefix <value>  = Prefix to start scanning from (optional)
    """ + ("" if IMPORTS_OK else """
        WARNING: boto3 import failed, module will not work correctly!
    """)

def scan_folder(opts):
    if 's3_profile' in opts:
        s3 = boto3.Session(profile_name=opts['s3_profile']).client('s3')
    else:
        s3 = boto3.client('s3')

    msg = TempMessage()
    msg("Scanning...", force=True)

    paginator = s3.get_paginator("list_objects_v2")
    args = {"Bucket": opts['s3_bucket']}
    prefix_len = 0
    if 's3_prefix' in opts:
        args['Prefix'] = opts['s3_prefix']
        prefix_len = len(opts['s3_prefix'])

    total_objects, total_size = 0, 0
    for page in paginator.paginate(**args):
        for cur in page['Contents']:
            total_objects += 1
            total_size += cur['Size']
            yield cur['Key'][prefix_len:].split("/"), cur['Size']
        msg(f"Scanning, gathered {total_objects} totaling {size_to_string(total_size)}...")
    msg(f"Done, saw {total_objects} totaling {size_to_string(total_size)}", newline=True)

def split(path):
    return path.split('/')

def join(path):
    return "/".join(path)

def dump_size(opts, value):
    # TODO: Show this as a "cost" when running in cost mode
    return size_to_string(value)

def dump_count(opts, value):
    return count_to_string(value)

def get_summary(opts, folder):
    return {
        "Location": "s3://" + opts['s3_bucket'] + "/" + opts.get('s3_prefix', ""),
        "Total objects": dump_count(opts, folder.count),
        "Total size": dump_size(opts, folder.size),
    }

if __name__ == "__main__":
    print("This module is not meant to be run directly")
