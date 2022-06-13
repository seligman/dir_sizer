#!/usr/bin/env python3

from datetime import datetime
from grid_layout import get_webpage, get_image, AUTO_SCALE, SET_SIZE
from utils import Folder, BatchingSql, ALL_ABSTRACTIONS
import json
import os
import sqlite3
import sys
import textwrap

# Abstractions will self-register if they're able
import local_abstraction
import s3_abstraction
import ssh_abstraction
import test_abstraction # TODO: Remove this when it's no longer needed

def set_output(opts, args):
    if len(args) > 0:
        if opts['output_mode'] is not None:
            print("ERROR: Output already specified")
            opts['show_help'] = True
            return args
        opts['output'] = args[0]
        opts['output_mode'] = 'html'
        return args[1:]
    else:
        print("ERROR: No filename for --output specified")
        opts['show_help'] = True
        return args

def set_output_image(opts, args):
    if len(args) > 0:
        if opts['output_mode'] is not None:
            print("ERROR: Output already specified")
            opts['show_help'] = True
            return args
        opts['output'] = args[0]
        opts['output_mode'] = 'png'
        return args[1:]
    else:
        print("ERROR: No filename for --output_image specified")
        opts['show_help'] = True
        return args


def set_cache(opts, args):
    if len(args) > 0:
        if opts['cache'] is not None:
            print("ERROR: Cache already specified")
            opts['show_help'] = True
            return args
        opts['cache'] = args[0]
        return args[1:]
    else:
        print("ERROR: No filename for --cache specified")
        opts['show_help'] = True
        return args

def set_cache_dir(opts, args):
    if len(args) > 0:
        if opts['cache'] is not None:
            print("ERROR: Cache already specified")
            opts['show_help'] = True
            return args
        dn = os.path.expanduser(args[0])
        if not os.path.isdir(dn):
            print(f"ERROR: Directory {dn} does not exist")
            opts['show_help'] = True
            return args
        now = datetime.utcnow()
        dn = os.path.join(dn, now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
        if not os.path.isdir(dn):
            os.makedirs(dn)
        opts['cache'] = os.path.join(dn, now.strftime("%Y-%m-%d-%H-%M-%S") + ".db")
        return args[1:]
    else:
        print("ERROR: No directory name for --cache_dir specified")
        opts['show_help'] = True
        return args

def set_debug(opts, args):
    opts['debug'] = True
    return args

def set_no_output(opts, args):
    if opts['output_mode'] is not None:
        print("ERROR: Output already specified")
        opts['show_help'] = True
        return args
    opts['output_mode'] = 'none'
    return args

def get_abstraction_flags(opts):
    ret = {}
    for key, value in opts.items():
        if key == "target_switch" or key.startswith(opts['target_prefix']):
            ret[key] = value
    return ret

def main():
    args = sys.argv[1:]
    opts = {
        'target': None,
        'output': None,
        'output_mode': None,
        'show_help': False,
        'cache': None,
        'debug': False,
    }

    flags = {
        '--output': set_output,
        '--output_image': set_output_image,
        '--no_output': set_no_output,
        '--cache': set_cache,
        '--cache_dir': set_cache_dir,
        '--debug': set_debug,
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
                    opts['target_switch'] = cur.MAIN_SWITCH
                    opts['target_prefix'] = cur.FLAG_PREFIX
                    args = args[1:]
                    args = cur.handle_args(opts, args)
                    break
            if not found:
                print("ERROR: Invalid options " + args[0])
                opts['show_help'] = True

    if not opts['show_help'] and opts['target'] is None:
        print("ERROR: No target scanner module specified")
        opts['show_help'] = True

    if not opts['show_help'] and opts['output_mode'] is None:
        print("ERROR: No output specified")
        opts['show_help'] = True

    if opts['debug']:
        print(textwrap.dedent("""
            Debug options:

            --cache <value>     = Store and use cache of files in <value> file
            --cache_dir <value> = Create a new cache file in <value> directory with 
                                  the current timestamp
                                  Note that one cache file can store different options
        """))
        exit(1)

    if opts['show_help']:
        print(textwrap.dedent("""
            Usage: 

            --output <value>       = Filename to output results to
            --output_image <value> = Filename to output image to
            --no_output            = Don't create any output file
            --debug                = Show some additional options useful for debugging
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

    if opts['output_mode'] == 'html':
        with open(opts['output'], "wt", newline="\n", encoding="utf-8") as f:
            # The values 1900x965 are designed to be about the real-estate available
            # on a 1080p display with some space left over for the browser UI
            f.write(get_webpage(opts, abstraction, folder, 1900, 965, AUTO_SCALE))
        print(f"All done, created {opts['output']}")
    elif opts['output_mode'] == 'png':
        im = get_image(opts, abstraction, folder, 1920, 1080)
        im.save(opts['output'])
        print(f"All done, created {opts['output']}")
    elif opts['output_mode'] == 'none':
        print(f"All done")
    else:
        raise Exception("ERROR: Unknown output mode!")


def cache_init(opts, flags):
    known_id, valid = None, False
    if opts['cache'] is not None:
        opts['cache_db'] = sqlite3.connect(opts['cache'])
        opts['cache_db'].execute("CREATE TABLE IF NOT EXISTS options(id INTEGER PRIMARY KEY AUTOINCREMENT, flags TEXT NOT NULL, valid INT NOT NULL);")
        opts['cache_db'].execute("CREATE UNIQUE INDEX IF NOT EXISTS options_flags_idx ON options(flags);")
        opts['cache_db'].execute("CREATE TABLE IF NOT EXISTS files(id INT NOT NULL, name NOT NULL, size NOT NULL);")
        opts['cache_db'].execute("CREATE INDEX IF NOT EXISTS files_id_idx ON files(id);")
        opts['cache_db'].commit()
        flags = json.dumps(flags, sort_keys=True)
        for row in opts['cache_db'].execute("SELECT id, valid FROM options WHERE flags = ?;", (flags,)):
            known_id, valid = row[0], row[1] == 1
        if known_id is None:
            cur = opts['cache_db'].execute("INSERT INTO options(flags, valid) VALUES (?, 0);", (flags,))
            opts['cache_db'].commit()
            known_id = cur.lastrowid
        elif not valid:
            opts['cache_db'].execute("DELETE FROM files WHERE id = ?;", (known_id,))
            opts['cache_db'].commit()
            valid = False
        if not valid:
            opts['cache_sql'] = BatchingSql(opts['cache_db'], f"INSERT INTO files(id, name, size) VALUES ({known_id}, ?, ?);")
    return known_id, valid

def cache_add(opts, name, size):
    opts['cache_sql'].execute(json.dumps(name), size)

def cache_finish(opts, known_id):
    opts['cache_sql'].finish()
    opts['cache_db'].execute("UPDATE options SET valid=1 WHERE id=?;", (known_id,))
    opts['cache_db'].commit()

def cache_get(opts, known_id):
    for name, size in opts['cache_db'].execute("SELECT name, size FROM files WHERE id = ?;", (known_id,)):
        yield json.loads(name), size

def load_files(opts, abstraction):
    if opts['cache'] is not None:
        known_id, valid = cache_init(opts, get_abstraction_flags(opts))
    else:
        known_id, valid = None, False

    if valid:
        for filename, size in cache_get(opts, known_id):
            yield filename, size
    else:
        for filename, size in abstraction.scan_folder(opts):
            yield filename, size
            if known_id is not None:
                cache_add(opts, filename, size)
        if known_id is not None:
            cache_finish(opts, known_id)

if __name__ == "__main__":
    main()
