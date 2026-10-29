#!/usr/bin/env python3
"""Build the sole public reader with Node and the shared React component tree."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = '/agent-memory-study/'


def build(output: Path, *, base: str = BASE_PATH):
    subprocess.run(['node', 'apps/reader/build.mjs', '--output', str(output.resolve()), '--base', base], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/site')
    parser.add_argument('--base', default=BASE_PATH, help='Use / for an explicitly launched local service')
    args = parser.parse_args()
    build(args.output, base=args.base)


if __name__ == '__main__':
    main()
