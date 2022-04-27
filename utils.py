#!/usr/bin/env python3

from datetime import datetime, timedelta
from collections import defaultdict
import json
import sys

ALL_ABSTRACTIONS = []
def register_abstraction(module_name):
    ALL_ABSTRACTIONS.append(sys.modules[module_name])

def count_to_string(value):
    return f"{value:,}"

def size_to_string(value):
    if value >= 1024 ** 6:
        return f"{value/(1024**6):0.2f} EiB"
    elif value >= 1024 ** 5:
        return f"{value/(1024**5):0.2f} PiB"
    elif value >= 1024 ** 4:
        return f"{value/(1024**4):0.2f} TiB"
    elif value >= 1024 ** 3:
        return f"{value/(1024**3):0.2f} GiB"
    elif value >= 1024 ** 2:
        return f"{value/(1024**2):0.2f} MiB"
    elif value >= 1024:
        return f"{value/1024:0.2f} KiB"
    else:
        return f"{value} B"

class TempMessage:
    def __init__(self, update_freq=timedelta(seconds=1)):
        self.last = ""
        self.update_freq = update_freq
        self.next_update = datetime.utcnow()
    
    def __call__(self, msg, force=False, newline=False):
        now = datetime.utcnow()
        if force or newline:
            pass
        elif now >= self.next_update:
            while now >= self.next_update:
                self.next_update += self.update_freq
        else:
            return

        if len(self.last) > len(msg):
            extra = len(self.last) - len(msg)
            temp = "\b" * extra + " " * extra + "\b" * len(self.last)
        else:
            temp = "\b" * len(self.last)
        self.last = msg
        if newline:
            print(temp + msg, flush=True)
            self.last = ""
        else:
            print(temp + msg, end="", flush=True)

class Folder:
    __slots__ = ("count", "size", "sub")
    def __init__(self):
        self.count = 0
        self.size = 0
        self.sub = defaultdict(Folder)

    def __getitem__(self, key):
        return self.sub[key]

    def __iter__(self):
        return iter(self.sub.items())

    def add(self, filename, size):
        if len(filename) == 1:
            if isinstance(size, tuple):
                self.count += size[1]
                self.size += size[0]
            else:
                self.count += 1
                self.size += size
        else:
            self[filename[0]].add(filename[1:], size)

    def sum_up(self):
        count, size = self.count, self.size
        for sub in self.sub.values():
            sub.sum_up()
            count += sub.count
            size += sub.size
        self.count, self.size = count, size
    
    def dump(self, f, key=""):
        if len(self.sub) == 0:
            f.write(json.dumps([key, self.count, self.size], separators=(",",":")) + "\n")
        else:
            f.write(json.dumps([key, self.count, self.size, len(self.sub)], separators=(",",":")) + "\n")
            for key, value in self.sub.items():
                value.dump(f, key)

    def _load(self, f):
        row = json.loads(next(f))
        if len(row) == 3:
            key, self.count, self.size = row
            return key
        else:
            key, self.count, self.size, left = row
            for _ in range(left):
                temp = Folder()
                self.sub[temp._load(f)] = temp
            return key

    @staticmethod
    def load(f):
        ret = Folder()
        ret._load(f)
        return ret

class BatchingSql:
    # Simple helper to batch calls to SQLite
    def __init__(self, db, sql):
        self.db = db
        self.todo = []
        self.sql = sql

    # Execute on a set of values, if enough values have been gathered, pass to the database
    def execute(self, *values):
        self.todo.append(values)
        if len(self.todo) >= 1000:
            self.finish()

    # Flush out any remaining items
    def finish(self):
        if len(self.todo) > 0:
            self.db.executemany(self.sql, self.todo)
            self.db.commit()
            self.todo = []

def chunks(values, size):
    for i in range(0, len(values), size):
        yield values[i : i + size]

if __name__ == "__main__":
    print("This module is not meant to be run directly")
