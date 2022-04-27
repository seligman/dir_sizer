#!/usr/bin/env python3

from grid_layout import get_webpage
from utils import Folder, BatchingSql, ALL_ABSTRACTIONS
import json
import os
import sqlite3
import sys
import textwrap

# Abstractions will self-register if they're able
import local_abstraction
import s3_abstraction
import test_abstraction # TODO: Remove this when it's no longer needed

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

    if len(sys.argv) == 1:
        opts['show_help'] = True
    else:
        if sys.argv[1] in {"--help", "-h", "/?", "/h"}:
            opts['show_help'] = True

    while len(args) > 0 and not opts['show_help']:
        if args[0] in flags:
            temp = flags[args[0]]
            args = args[1:]
            args = temp(opts, args)
        else:
            found = False
            for cur in ALL_ABSTRACTIONS:
                if cur.MAIN_SWITCH == args[0]:
                    found = True
                    if opts['target'] is not None:
                        opts['show_help'] = True
                        print("ERROR: More than one module specified")
                        break
                    opts['target'] = cur
                    args = args[1:]
                    args = cur.handle_args(opts, args)
                    break
            if not found:
                print("ERROR: Invalid options " + args[0])
                opts['show_help'] = True

    if not opts['show_help'] and opts['target'] is None:
        print("ERROR: No target scanner module specified")
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
        for cur in ALL_ABSTRACTIONS:
            print(f"{cur.MAIN_SWITCH} = {cur.DESCRIPTION}")
            msg = textwrap.dedent(cur.get_help()).strip()
            for row in msg.split("\n"):
                print(" " * 4 + row)
            print("")
        exit(1)

    folder = Folder()
    abstraction = opts['target']

    for filename, size in load_files(opts, abstraction):
        folder.add(filename, size)
    folder.sum_up()

    with open(opts['output'], "wt", newline="\n", encoding="utf-8") as f:
        # TODO: Let the final size be an option
        f.write(get_webpage(opts, abstraction, folder, 900, 600))

    print(f"All done, created {opts['output']}")

def load_files(opts, abstraction):
    if opts['cache'] is not None and os.path.isfile(opts['cache']):
        db = sqlite3.connect(opts['cache'])
        for key, size in db.execute("SELECT key, size FROM files;"):
            yield json.loads(key), size
        db.close()
    else:
        db, sql = None, None
        if opts['cache'] is not None:
            db = sqlite3.connect(opts['cache'])
            db.execute("CREATE TABLE files(key TEXT NOT NULL, size NOT NULL);")
            db.commit()
            sql = BatchingSql(db, "INSERT INTO files(key, size) VALUES (?, ?);")
        todo = []
        for filename, size in abstraction.scan_folder(opts):
            yield filename, size
            if sql is not None:
                sql.execute(json.dumps(filename), size)

        if sql is not None:
            sql.finish()
            db.close()

if __name__ == "__main__":
    main()
