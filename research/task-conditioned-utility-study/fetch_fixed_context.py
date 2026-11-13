#!/usr/bin/env python3
"""Fetch a single pinned, public input; verify content before publication."""
import argparse
import hashlib
from pathlib import Path
import tempfile
import urllib.request
import os

URL = "https://huggingface.co/datasets/AgentsSci/AAMAS2027-ConditionalMemory/resolve/332cd047e9093a948606c4251bf5b294b0664762/followups_package/x2/cells.jsonl"
SHA256 = "d7a7309044ffb02aed7ddb786359939c51de12bf910a5825f3a6933ef651b033"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        if hashlib.sha256(args.out.read_bytes()).hexdigest() != SHA256:
            raise SystemExit("Existing file differs; refusing to overwrite it")
        print(f"Already verified: {args.out}")
        return
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit("Downloaded content does not match pinned hash")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=args.out.parent, delete=False) as file:
            temp = Path(file.name)
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.link(temp, args.out)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    print(f"Verified {len(data)} bytes: {args.out}")


if __name__ == "__main__":
    main()
