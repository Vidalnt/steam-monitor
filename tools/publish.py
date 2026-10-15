#!/usr/bin/env python3
"""Record a verified Steam build: data/published.json + updates.yaml.

Appends `  <version>:\n    - <sha> #ubuntu12_32` under SafeModeHashes,
keeping versions sorted.

Usage:
    python3 tools/publish.py --version 1791918634 --channel stable \\
        --sha <sha256>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
UPDATES = DATA / "updates.yaml"
PUBLISHED = DATA / "published.json"


def load_updates() -> str:
    if UPDATES.exists():
        return UPDATES.read_text()
    return "SafeModeHashes:\n"


def append_hash(text: str, version: str, sha: str) -> str:
    entry = f"    - {sha} #ubuntu12_32\n"
    block_re = re.compile(
        rf"(?m)^  {re.escape(version)}:\n((?:    - .*\n?)*)"
    )
    m = block_re.search(text)
    if m:
        if sha in m.group(1):
            return text  # already recorded
        return text[: m.end(1)] + entry + text[m.end(1):]
    # Insert keeping version keys sorted (versions sort lexicographically,
    # which matches chronological order for these zero-padded timestamps).
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    inserted = False
    i = 0
    while i < len(lines):
        if not inserted and lines[i].startswith("  ") and not lines[i].startswith("    "):
            key = lines[i].strip().rstrip(":")
            if key > version:
                out.append(f"  {version}:\n")
                out.append(entry)
                inserted = True
        out.append(lines[i])
        i += 1
    if not inserted:
        if out and not out[-1].endswith("\n"):
            out[-1] += "\n"
        out.append(f"  {version}:\n")
        out.append(entry)
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--channel", required=True)
    ap.add_argument("--sha", required=True)
    args = ap.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    published: dict = {}
    if PUBLISHED.exists():
        published = json.loads(PUBLISHED.read_text())
    published[args.version] = {
        "channel": args.channel,
        "sha": args.sha,
        "file": "updates.yaml",
    }
    PUBLISHED.write_text(json.dumps(published, indent=2) + "\n")

    UPDATES.write_text(append_hash(load_updates(), args.version, args.sha))
    print(f"recorded {args.version} {args.sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
