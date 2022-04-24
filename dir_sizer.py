#!/usr/bin/env python3

from grid_layout import get_webpage
import s3_abstraction
import sys
import textwrap
from utils import Folder

ABSTRACTIONS = [
    s3_abstraction,
]

def set_output(opts, args):
    if len(args) > 0:
        opts['output'] = args[0]
        return args[1:]
    else:
        print("ERROR: No filename for --output specified")
        opts['show_help'] = True
        return args

def main():
    args = sys.argv[1:]
    opts = {
        'target': None,
        'output': None,
        'show_help': False,
    }

    flags = {
        '--output': set_output,
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
        print("Usage: ")
        print("")
        print("--output <value> = Filename to output results to")
        for cur in ABSTRACTIONS:
            print(f"{cur.MAIN_SWITCH} = {cur.DESCRIPTION}")
            msg = textwrap.dedent(cur.get_help()).strip()
            for row in msg.split("\n"):
                print(" " * 4 + row)
        exit(1)

    folder = Folder()
    abstraction = opts['target']
    for filename, size in abstraction.scan_folder(opts):
        folder.add(abstraction.split(filename), size)
    folder.sum_up()

    with open(opts['output'], "wt", newline="\n", encoding="utf-8") as f:
        # TODO: Let the final size be an option
        f.write(get_webpage(folder, 900, 600))

    print(f"All done, created {opts['output']}")

if __name__ == "__main__":
    main()
