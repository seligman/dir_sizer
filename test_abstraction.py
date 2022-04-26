#!/usr/bin/env python3

from utils import size_to_string, count_to_string

MAIN_SWITCH = "--test"
DESCRIPTION = "Hardcoded test data"

def handle_args(opts, args):
    # Nothing to do here
    return args

def get_help():
    # No extra options
    return ""

def scan_folder(opts):
    # Just return a hard coded list of values to test things out
    temp = [
        ("001",        200),
        ("sub_a/002",  120),
        ("sub_b/003",  130),
        ("sub_c/004",  140),
    ]
    for key, value in temp:
        yield key.split("/"), value

def split(path):
    # Hardcoded to use forward slashes
    return path.split("/")

def join(path):
    return "/".join(path)

def dump_size(opts, value):
    return size_to_string(value)

def dump_count(opts, value):
    return count_to_string(value)

if __name__ == "__main__":
    print("This module is not meant to be run directly")
