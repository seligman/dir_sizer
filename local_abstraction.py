#!/usr/bin/env python3

from collections import deque
from utils import TempMessage, size_to_string
import os
import stat

MAIN_SWITCH = "--local"
DESCRIPTION = "Scan local file system"

def handle_args(opts, args):
    while True:
        if len(args) >= 2 and args[0] == "--base":
            opts['lfs_base'] = args[1]
            args = args[2:]
        else:
            break
    
    if not opts['show_help'] and 'lfs_base' not in opts:
        opts['show_help'] = True
        print("ERROR: No base path specified for local file system")
    
    return args

def get_help():
    return """
        --base <value> = Base path to scan for files
    """

def scan_folder(opts):
    msg = TempMessage()
    msg("Scanning...", force=True)

    # Scan all folders under the selected path
    total_objects, total_size = 0, 0
    # Use expanduser to allow things like "~/"
    todo = deque([os.path.expanduser(opts['lfs_base'])])
    while len(todo) > 0:
        path = todo.pop()
        # Use scandir instead of other options to speed force FindFirstFile on windows
        # for a considerable speedup, but these functions aren't recursive on their
        # own, so track directories in a deque and recurse manually
        # Order here isn't important, it'll be sorted elsewhere, so whatever scandir
        # returns in is fine.
        # TODO: Consider ignoring symbolic links
        for cur in os.scandir(path):
            try:
                if stat.S_ISDIR(cur.stat().st_mode):
                    # It's a directory, add it to our list ot do
                    todo.append(cur.path)
                else:
                    # It's a file, add to our count and send it out
                    total_objects += 1
                    total_size += cur.stat().st_size
                    msg(f"Scanning, gathered {total_objects} totaling {size_to_string(total_size)}...")
                    yield cur.path, cur.stat().st_size
            except (FileNotFoundError, OSError):
                # Ignore any files we don't see (mostly dangling links)
                pass
    msg(f"Done, saw {total_objects} totaling {size_to_string(total_size)}", newline=True)

def split(path):
    # Simple split/join methods meant to be symmentrical and somewhat OS aware
    return path.split(os.path.sep)

def join(path):
    return os.path.sep.join(path)

if __name__ == "__main__":
    print("This module is not meant to be run directly")
