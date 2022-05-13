#!/usr/bin/env python3

from utils import TempMessage, size_to_string, count_to_string, register_abstraction
import base64
import gzip
import json
import os
import textwrap
try:
    # Use paramiko for this connection, so wrap the import 
    # of that module in a try/except block
    import paramiko
    IMPORTS_OK = True
except:
    IMPORTS_OK = False
register_abstraction(__name__)

# The SSH abstraction.  This is an abstraction around running the local
# abstraction over a SSH connection to get size information for a 
# directory on a remote machine.

MAIN_SWITCH = "--ssh"
FLAG_PREFIX = "ssh_"
DESCRIPTION = "Scan remote folder over a SSH connection"

def handle_args(opts, args):
    if not IMPORTS_OK:
        opts['show_help'] = True
        print("ERROR: Unable to import paramiko, unable to launch remote helper!")

    while not opts['show_help']:
        if len(args) >= 2 and args[0] == "--hostname":
            opts['ssh_host'] = args[1]
            args = args[2:]
        elif len(args) >= 2 and args[0] == "--port":
            opts['ssh_port'] = int(args[1])
            args = args[2:]
        elif len(args) >= 2 and args[0] == "--username":
            opts['ssh_user'] = args[1]
            args = args[2:]
        elif len(args) >= 2 and args[0] == "--password":
            opts['ssh_password'] = args[1]
            args = args[2:]
        elif len(args) >= 2 and args[0] == "--private_key":
            opts['ssh_pem'] = args[1]
            args = args[2:]
        elif len(args) >= 2 and args[0] == "--path":
            opts['ssh_path'] = args[1]
            args = args[2:]
        else:
            break

    if not opts['show_help']:
        if 'ssh_host' not in opts:
            print("ERROR: hostname was not specified")
            opts['show_help'] = True
        if 'ssh_user' not in opts:
            print("ERROR: username was not specified")
            opts['show_help'] = True
        if 'ssh_user' not in opts:
            print("ERROR: username was not specified")
            opts['show_help'] = True
        if 'ssh_path' not in opts:
            print("ERROR: Remote path was not specified")
            opts['show_help'] = True
        if 'ssh_password' not in opts and 'ssh_pem' not in opts:
            print("ERROR: Neither password or private key were specified")
            opts['show_help'] = True
        if 'ssh_password' in opts and 'ssh_pem' in opts:
            print("ERROR: Both password or private key were specified")
            opts['show_help'] = True

    return args

def get_help():
    return f"""
        --hostname <value>    = The remote host to connect to
        --port <value>        = The port to connect to (optional)
        --username <value>    = The SSH username to use
        --password <value>    = The SSH password to use (optional)
        --private_key <value> = The private key .pem file to use (optional)
        --path <value>        = The directory on the remote machine to scan
    """ + ("" if IMPORTS_OK else """
        WARNING: paramiko import failed, module will not work correctly!
    """)

def get_remote_script(opts):
    # Internal helper to get the script to run on the remote machine

    # First off, find the main worker inside the local abstraction
    fn = os.path.join(os.path.split(__file__)[0], "local_abstraction.py")
    script = ""
    in_scanner = False
    with open(fn, "rt", encoding="utf-8") as f:
        for row in f:
            if row.startswith("#"):
                if "SCANNER_START" in row:
                    in_scanner = True
                if "SCANNER_END" in row:
                    in_scanner = False
            if in_scanner:
                if not row.strip().startswith("#") and len(row.strip()) > 0 and "msg" not in row:
                    script += row

    # Add a small helper that calls the local function
    script += textwrap.dedent("""
        import json,os,gzip,base64,sys
        batch = []
        def dump_batch(batch):
            batch = json.dumps(batch, separators=(',', ':'))
            batch = base64.b64encode(gzip.compress(batch.encode("utf-8"))).decode("utf-8")
            sys.stdout.write("%08d%s"%(len(batch),batch))
            sys.stdout.flush()
        for x in scan_folder({'lfs_base': os.path.expanduser(""" + json.dumps(opts["ssh_path"]) + """)}):
            batch.append(x)
            if len(batch) >= 1000:
                dump_batch(batch)
                batch = []
        batch.append("DONE")
        dump_batch(batch)
    """)

    # Encode the script to a base64 blob that can be run directly in REPL or command line
    # Note that single quotes aren't used here, allowing this string to be safely quoted
    script = base64.b64encode(gzip.compress(script.encode("utf-8"))).decode("utf-8")
    remote_code = "import gzip,base64;"
    remote_code += "exec(gzip.decompress(base64.b64decode(\"" + script + "\")));"
    remote_code += "exit(0)"

    return remote_code

def scan_folder(opts):
    # Connect to the remote machine
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    args = {
        "hostname": opts["ssh_host"],
        "username": opts["ssh_user"],
        "port": opts.get("ssh_port", 22),
    }
    if "ssh_password" in opts:
        args["password"] = opts["ssh_password"]
    else:
        args["pkey"] = paramiko.RSAKey.from_private_key_file(opts["ssh_pem"])
    
    ssh.connect(**args)

    remote_code = get_remote_script(opts)

    msg = TempMessage()
    msg("Scanning...", force=True)

    # Build up a command to run, use "python3" if it exists, otherwise fall back to "python" and a hope
    cmd = "`if type python3>/dev/null 2>&1;then echo python3;else echo python;fi` -c '" + remote_code + "'"

    stdin, stdout, stderr = ssh.exec_command(cmd)
    read_done = False
    total_objects, total_size = 0, 0
    while not read_done:
        # Ok, the remote script is running, go ahead and read one batch at a time
        to_read = stdout.read(8)
        if len(to_read) != 8:
            break
        to_read = int(to_read.decode("utf-8"))
        data = json.loads(gzip.decompress(base64.b64decode(stdout.read(to_read))))
        for row in data:
            if row == "DONE":
                read_done = True
            else:
                total_objects += 1
                total_size += row[1]
                yield row
        msg(f"Scanning, gathered {total_objects} totaling {dump_size(opts, total_size)}...")

    error_output = stderr.read()
    if len(error_output) > 0:
        raise Exception("Remote Error: " + error_output.decode("utf-8"))

    stdin.close()
    stdout.close()
    stderr.close()
    ssh.close()

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
    return [
        ("Location", f"{opts['ssh_host']}:{opts['ssh_path']}"),
        ("Total objects", dump_count(opts, folder.count)),
        ("Total cost" if opts.get('s3_cost', False) else "Total size", dump_size(opts, folder.size)),
    ]

if __name__ == "__main__":
    print("This module is not meant to be run directly")
