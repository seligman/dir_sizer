#!/usr/bin/env python3

from collections import deque
from utils import TempMessage, size_to_string
import os
import stat

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
    return [
        ("base/001",        200),
        ("base/sub_a/002",  120),
        ("base/sub_b/003",  130),
        ("base/sub_c/004",  140),
    ]

def split(path):
    # Hardcoded to use forward slashes
    return path.split("/")

def join(path):
    return "/".join(path)

if __name__ == "__main__":
    print("This module is not meant to be run directly")
