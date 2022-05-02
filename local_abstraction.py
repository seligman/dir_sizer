#!/usr/bin/env python3

from collections import deque
from utils import TempMessage, size_to_string, count_to_string, register_abstraction
import os
import stat
register_abstraction(__name__)

MAIN_SWITCH = "--local"
DESCRIPTION = "Scan local file system"

def handle_args(opts, args):
    while not opts['show_help']:
        if len(args) >= 2 and args[0] == "--base":
            opts['lfs_base'] = args[1]
            args = args[2:]
        elif len(args) >= 1 and args[0] == "--follow_links":
            opts['lfs_follow_links'] = True
            args = args[1:]
        else:
            break
    
    if not opts['show_help'] and 'lfs_base' not in opts:
        opts['show_help'] = True
        print("ERROR: No base path specified for local file system")
    
    return args

def get_help():
    return """
        --base <value> = Base path to scan for files
        --follow_links = Follow into links and junctions (optional)
    """

def is_link(dn):
    # Check to see if this is a symbolic link on Unix systems
    if os.path.islink(dn):
        # Simple case, it's a link
        return True
    else:
        # On Windows, the story is a bit more complex, try to read
        # the junction information.  This same technique works
        # for Unix platforms, but hopefully the islink call
        # above will short circuit it in some cases
        try:
            os.readlink(dn)
            # If we got this far, then readlink worked, which
            # means dn is a link or junction
            return True
        except:
            # It's something else, either a raw file, or directory
            return False

def scan_folder(opts):
    msg = TempMessage()
    msg("Scanning...", force=True)

    # Scan all folders under the selected path
    total_objects, total_size = 0, 0
    # Use expanduser to allow things like "~/"
    todo = deque([(os.path.expanduser(opts['lfs_base']), [])])
    while len(todo) > 0:
        path, path_parts = todo.pop()
        # Use scandir instead of other options to speed force FindFirstFile on windows
        # for a considerable speedup, but these functions aren't recursive on their
        # own, so track directories in a deque and recurse manually
        # Order here isn't important, it'll be sorted elsewhere, so whatever scandir
        # returns in is fine.
        try:
            for cur in os.scandir(path):
                try:
                    if stat.S_ISDIR(cur.stat().st_mode):
                        use_directory = True
                        if not opts.get("lfs_follow_links", False):
                            # We shouldn't follow into links and junctions, so see if this is junction
                            if is_link(cur.path):
                                # It's a link, so don't use it
                                use_directory = False
                        if use_directory:
                            # It's a directory, add it to our list ot do
                            todo.append((cur.path, path_parts + [cur.name]))
                    else:
                        # Pull out the size before doing anything with the data
                        # to give the exception a chance to fire
                        size = cur.stat().st_size
                        filename = cur.name
                        # It's a file, add to our count and send it out
                        total_objects += 1
                        total_size += size
                        msg(f"Scanning, gathered {total_objects} totaling {size_to_string(total_size)}...")
                        yield path_parts + [filename], size
                except (FileNotFoundError, OSError, PermissionError):
                    # Ignore any files we don't see (mostly dangling links)
                    # Also ignore any permission errors
                    pass
        except (FileNotFoundError, OSError, PermissionError):
            # And ignore any errors on the scandir itself, do this
            # in to seperate try/except blocks so any errors on a single
            # file don't break an entire folder
            pass
    msg(f"Done, saw {total_objects} totaling {size_to_string(total_size)}", newline=True)

def split(path):
    # Simple split/join methods meant to be symmentrical and somewhat OS aware
    return path.split(os.path.sep)

def join(path):
    return os.path.sep.join(path)

def dump_size(opts, value):
    return size_to_string(value)

def dump_count(opts, value):
    return count_to_string(value)

def get_summary(opts, folder):
    return [
        ("Directory", opts['lfs_base']),
        ("Total files", dump_count(opts, folder.count)),
        ("Total size", dump_size(opts, folder.size)),
    ]

if __name__ == "__main__":
    print("This module is not meant to be run directly")
