#!/usr/bin/env python3

from utils import TempMessage, size_to_string, count_to_string, register_abstraction
try:
    # Wrap the use of the Google Cloud SDK in a try/except block
    # so if it's not available, the rest will work
    from google.cloud import storage
    IMPORTS_OK = True
except:
    IMPORTS_OK = False
register_abstraction(__name__)

# The Google Cloud abstraction.

MAIN_SWITCH = "--gcloud"
FLAG_PREFIX = "gcloud_"
DESCRIPTION = "Scan Google Cloud bucket for blob sizes"

def handle_args(opts, args):
    if not IMPORTS_OK:
        opts['show_help'] = True
        print("ERROR: Unable to import google-cloud-storage, unable to call Google Cloud APIs!")

    while not opts['show_help']:
        if len(args) >= 2 and args[0] == "--bucket":
            opts['gcloud_bucket'] = args[1]
            args = args[2:]
        elif len(args) >= 2 and args[0] == "--prefix":
            opts['gcloud_prefix'] = args[1]
            args = args[2:]
        elif len(args) >= 2 and args[0] == "--project":
            opts['gcloud_project'] = args[1]
            args = args[2:]
        else:
            break

    if not opts['show_help']:
        if 'gcloud_bucket' not in opts:
            print("ERROR: bucket was not specified")
            opts['show_help'] = True

    return args

def get_help():
    return f"""
        --bucket <value>      = The name of the bucket
        --prefix <value>      = The prefix inside the bucket to start scanning (optional)
        --project <value>     = The project ID to use (optional)
    """ + ("" if IMPORTS_OK else """
        WARNING: google-cloud-storage import failed, module will not work correctly!
    """)

def scan_folder(opts):
    msg = TempMessage()
    msg("Scanning...", force=True)

    # Connect to the remote machine
    if 'gcloud_project' in opts:
        sc = storage.Client(opts['gcloud_project'])
    else:
        sc = storage.Client()

    total_objects = 0
    total_size = 0

    for i, blob in enumerate(sc.list_blobs(opts['gcloud_bucket'], prefix=opts['gcloud_prefix'] if 'gcloud_prefix' in opts else None)):
        size = blob.size
        name = blob.name
        total_objects += 1
        total_size += size
        yield name.split("/"), size
        if i % 1000 == 999:
            msg(f"Scanning, gathered {total_objects} totaling {dump_size(opts, total_size)}...")

    msg(f"Done, saw {total_objects} totaling {dump_size(opts, total_size)}", newline=True)

def split(path):
    # Hardcoded to use forward slashes
    return path.split("/")

def join(path):
    return "/".join(path)

def dump_size(opts, value):
    return size_to_string(value)

def dump_count(opts, value):
    return count_to_string(value)

def get_summary(opts, folder):
    location = "gs://" + opts['gcloud_bucket'] + "/" + opts.get('gcloud_prefix', "")
    return [
        ("Location", location),
        ("Total objects", dump_count(opts, folder.count)),
        ("Total size", dump_size(opts, folder.size)),
    ]

if __name__ == "__main__":
    print("This module is not meant to be run directly")
