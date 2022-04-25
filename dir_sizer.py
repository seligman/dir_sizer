#!/usr/bin/env python3

from grid_layout import get_webpage
from utils import Folder
import os
import sqlite3
import sys
import textwrap

import s3_abstraction
import local_abstraction
import test_abstraction
ABSTRACTIONS = [
    s3_abstraction,
    local_abstraction,
    test_abstraction,       # TODO: Remove this when it's no longer useful
]

def set_output(opts, args):
    if len(args) > 0:
        opts['output'] = args[0]
        return args[1:]
    else:
        print("ERROR: No filename for --output specified")
        opts['show_help'] = True
        return args

def set_cache(opts, args):
    if len(args) > 0:
        opts['cache'] = args[0]
        return args[1:]
    else:
        print("ERROR: No filename for --cache specified")
        opts['show_help'] = True
        return args

def main():
    args = sys.argv[1:]
    opts = {
        'target': None,
        'output': None,
        'show_help': False,
        'cache': None,
    }

    flags = {
        '--output': set_output,
        '--cache': set_cache,
    }

    while len(args) > 0 and not opts['show_help']:
        if args[0] in flags:
            temp = flags[args[0]]
            args = args[1:]
            args = temp(opts, args)
        else:
            for cur in ABSTRACTIONS:
                if cur.MAIN_SWITCH == args[0]:
                    if opts['target'] is not None:
                        opts['show_help'] = True
                        print("ERROR: More than one module specified")
                        break
                    opts['target'] = cur
                    args = args[1:]
                    args = cur.handle_args(opts, args)
                    break

    if not opts['show_help'] and opts['target'] is None:
        print("ERROR: No target scanner module found")
        opts['show_help'] = True

    if not opts['show_help'] and opts['output'] is None:
        print("ERROR: No output filename specified")
        opts['show_help'] = True

    if opts['show_help']:
        print(textwrap.dedent("""
            Usage: 

            --output <value> = Filename to output results to
            --cache <value>  = Store and use cache of files in <value> file (optional)
        """))
        for cur in ABSTRACTIONS:
            print(f"{cur.MAIN_SWITCH} = {cur.DESCRIPTION}")
            msg = textwrap.dedent(cur.get_help()).strip()
            for row in msg.split("\n"):
                print(" " * 4 + row)
            print("")
        exit(1)

    folder = Folder()
    abstraction = opts['target']

    for filename, size in load_files(opts, abstraction):
        folder.add(abstraction.split(filename), size)
    folder.sum_up()

    with open(opts['output'], "wt", newline="\n", encoding="utf-8") as f:
        # TODO: Let the final size be an option
        f.write(get_webpage(folder, 900, 600))

    print(f"All done, created {opts['output']}")

def load_files(opts, abstraction):
    if opts['cache'] is not None and os.path.isfile(opts['cache']):
        db = sqlite3.connect(opts['cache'])
        for key, size in db.execute("SELECT key, size FROM files;"):
            yield key, size
        db.close()
    else:
        db = None
        if opts['cache'] is not None:
            db = sqlite3.connect(opts['cache'])
            db.execute("CREATE TABLE files(key TEXT NOT NULL, size INTEGER NOT NULL);")
            db.commit()
        todo = []
        for filename, size in abstraction.scan_folder(opts):
            yield filename, size
            if db is not None:
                todo.append((filename, size))
                if len(todo) >= 5000:
                    db.executemany("INSERT INTO files(key, size) VALUES (?, ?);", todo)
                    db.commit()
                    todo = []

        if db is not None:
            if len(todo) > 0:
                db.executemany("INSERT INTO files(key, size) VALUES (?, ?);", todo)
                db.commit()
            db.close()

if __name__ == "__main__":
    main()
