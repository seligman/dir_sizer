#!/usr/bin/env python3

from utils import BatchingSql
import sys, sqlite3, random, re, string

if len(sys.argv) != 3:
    print("Specify source cache file, and output file")
    print("Will obfuscate all filenames and write out file")
    exit(1)

db_src = sqlite3.connect(sys.argv[1])
db_dest = sqlite3.connect(sys.argv[2])

# Create and empty the dest database
db_dest.execute("CREATE TABLE IF NOT EXISTS files(key TEXT NOT NULL, size NOT NULL);")
db_dest.commit()
db_dest.execute("DELETE FROM files;")
db_dest.commit()

# Seed random so reruns produce the same obfuscated results
random.seed(42)

# All of the current random strings produced for each word
hidden = {}

sql = BatchingSql(db_dest, "INSERT INTO files(key, size) VALUES (?, ?);")
for key, value in db_src.execute("SELECT key, size FROM files;"):
    key = re.split("([/\\\\])", key)
    for x in key:
        if x not in {"/", "\\"}:
            if x not in hidden:
                hidden[x] = "".join(random.choice(string.ascii_lowercase) for _ in range(random.randint(5, 10)))
    sql.execute("".join(hidden.get(x, x) for x in key), value)
sql.finish()

db_dest.close()
db_src.close()

print("All done!")