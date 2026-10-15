#!/usr/bin/env python3
"""Verify Pattern_t signatures against a steamclient.so.

Reads data/patterns.json (name + byte signature, ?/?? wildcards).
Optional patterns warn but do not fail; a miss on a required pattern
prints FAIL and exits 1.

Usage:
    python3 tools/check_patterns.py --so bins/stable/steamclient.so
        [--patterns data/patterns.json]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Pattern_t Name { "Full::Name", "55 89 E5 ...", ... }
_PATTERN_RE = re.compile(
    r'Pattern_t\s+\w+\s*\{\s*"([^"]+)"\s*,\s*"([0-9A-Fa-f? ]+)"', re.MULTILINE
)
# Skip-list inside Patterns::init(): == "Some::Name"
_SKIP_RE = re.compile(r'==\s*"([^"]+)"')


def parse_sig(sig: str) -> tuple[bytes, bytes]:
    """Turn '55 89 E5 ? ??' into (bytes, mask)."""
    blob = bytearray()
    mask = bytearray()
    for tok in sig.split():
        if set(tok) == {"?"}:
            blob.append(0)
            mask.append(0)
        else:
            blob.append(int(tok, 16))
            mask.append(1)
    return bytes(blob), bytes(mask)


def load_patterns_cpp(path: Path) -> tuple[list[tuple[str, bytes, bytes]], set[str]]:
    text = path.read_text()
    patterns = []
    for name, sig in _PATTERN_RE.findall(text):
        b, m = parse_sig(sig)
        patterns.append((name, b, m))
    skips = set(_SKIP_RE.findall(text))
    return patterns, skips


def load_patterns(path: Path) -> tuple[list[tuple[str, bytes, bytes]], set[str]]:
    """Accept data/patterns.json or a patterns.cpp file."""
    if path.suffix == ".json":
        import json as _json

        entries = _json.loads(path.read_text())
        patterns = []
        skips = set()
        for e in entries:
            b, m = parse_sig(e["sig"])
            patterns.append((e["name"], b, m))
            if e.get("optional"):
                skips.add(e["name"])
        return patterns, skips
    return load_patterns_cpp(path)


def scan(data: bytes, sig: bytes, mask: bytes) -> bool:
    n = len(sig)
    if n == 0 or n > len(data):
        return False
    first = next((i for i, m in enumerate(mask) if m), None)
    if first is None:
        return True  # all-wildcard: vacuously matches
    needle = sig[first]
    start = 0
    while True:
        i = data.find(needle, start)
        if i < 0 or i - first < 0 or i - first + n > len(data):
            return False
        base = i - first
        ok = True
        for j in range(n):
            if mask[j] and data[base + j] != sig[j]:
                ok = False
                break
        if ok:
            return True
        start = i + 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", required=True)
    ap.add_argument("--patterns", default=None)
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    patterns_path = (
        Path(args.patterns)
        if args.patterns
        else here.parent / "data" / "patterns.json"
    )
    if not patterns_path.exists():
        print(f"patterns.cpp not found: {patterns_path}")
        return 1

    patterns, skips = load_patterns(patterns_path)
    if not patterns:
        print("no Pattern_t entries parsed")
        return 1

    data = Path(args.so).read_bytes()
    failed_required = 0
    for name, sig, mask in patterns:
        hit = scan(data, sig, mask)
        optional = name in skips
        status = "OK" if hit else ("SKIP-OPTIONAL" if optional else "FAIL")
        print(f"{status} {name}")
        if not hit and not optional:
            failed_required += 1
    print(f"{len(patterns)} patterns, {failed_required} required failures")
    return 1 if failed_required else 0


if __name__ == "__main__":
    sys.exit(main())
