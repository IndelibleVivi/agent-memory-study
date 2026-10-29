#!/usr/bin/env python3
"""Build pinned SQLite for isolated Linux CI; never replace the system library.

The source digest is published at https://www.sqlite.org/releaselog/3_53_4.html.
Use --check-source to verify the download without compiling on another platform.
"""
import argparse
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

VERSION='3.53.4'
URL='https://www.sqlite.org/2026/sqlite-amalgamation-3530400.zip'
SOURCE_DIGEST='67f423e9ebbbdc473cbc4772c872ee6b89f31fde4ed0279a5c25d5f65c043a16'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--check-source',action='store_true')
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Select a new isolated output directory.')
    with urllib.request.urlopen(URL,timeout=60) as response:raw=response.read(16*1024*1024)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        source=archive.read('sqlite-amalgamation-3530400/sqlite3.c')
    if hashlib.sha3_256(source).hexdigest()!=SOURCE_DIGEST:raise SystemExit('SQLite source identity does not match its release.')
    if not args.check_source and not sys.platform.startswith('linux'):raise SystemExit('CI library compilation is Linux-only.')
    args.output.mkdir(parents=True);c=args.output/'sqlite3.c';c.write_bytes(source)
    if not args.check_source:
        subprocess.run(['cc','-shared','-fPIC','-O2','-DSQLITE_ENABLE_FTS5','-DSQLITE_ENABLE_COLUMN_METADATA','-DSQLITE_THREADSAFE=1','-Wl,-soname,libsqlite3.so.0','-o',str(args.output/'libsqlite3.so.0'),str(c),'-lm','-ldl','-pthread'],check=True)
    print('Verified SQLite',VERSION,'source; isolated output:',args.output)

if __name__=='__main__':main()
