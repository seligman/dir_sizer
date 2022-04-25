#!/usr/bin/env python3

import boto3
from utils import TempMessage, size_to_string

MAIN_SWITCH = "--s3"
DESCRIPTION = "Scan AWS S3 for object sizes"

# TODO: A flag to sort by "cost"

def handle_args(opts, args):
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
    return """
        --profile <value> = AWS CLI profile name to use (optional)
        --bucket <value>  = S3 Bucket to scan
        --prefix <value>  = Prefix to start scanning from (optional)
    """

def scan_folder(opts):
    if 's3_profile' in opts:
        s3 = boto3.Session(profile_name=opts['s3_profile']).client('s3')
    else:
        s3 = boto3.client('s3')

    msg = TempMessage()
    msg("Scanning...", force=True)

    paginator = s3.get_paginator("list_objects_v2")
    args = {"Bucket": opts['s3_bucket']}
    if 's3_prefix' in opts:
        args['Prefix'] = opts['s3_prefix']
    total_objects, total_size = 0, 0
    for page in paginator.paginate(**args):
        todo = []
        for cur in page['Contents']:
            total_objects += 1
            total_size += cur['Size']
            todo.append((cur['Key'], cur['Size']))
            yield cur['Key'], cur['Size']
        msg(f"Scanning, gathered {total_objects} totaling {size_to_string(total_size)}...")
    msg(f"Done, saw {total_objects} totaling {size_to_string(total_size)}", newline=True)

def split(path):
    return path.split('/')

def join(path):
    return "/".join(path)

if __name__ == "__main__":
    print("This module is not meant to be run directly")
