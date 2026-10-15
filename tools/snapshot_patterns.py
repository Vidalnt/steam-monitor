#!/usr/bin/env python3
"""Snapshot a patterns.cpp file into data/patterns.json (manual step).

Usage:
    python3 tools/snapshot_patterns.py --src /path/to/patterns.cpp
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_patterns import load_patterns_cpp  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data" / "patterns.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    args = ap.parse_args()

    src = Path(args.src)
    if not src.exists():
        print(f"patterns.cpp not found: {src}")
        return 1

    patterns, skips = load_patterns_cpp(src)
    if not patterns:
        print("no Pattern_t entries parsed")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            [
                {"name": n, "sig": " ".join(f"{b:02X}" if m else "??" for b, m in zip(sig, mask)),
                 "optional": n in skips}
                for n, sig, mask in patterns
            ],
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {len(patterns)} patterns to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
