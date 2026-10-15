#!/usr/bin/env python3
"""Fetch Linux Steam client binaries for the pattern monitor.

Polls CHANNEL_MANIFESTS, downloads bins_ubuntu12.zip per new channel build,
extracts ubuntu12_32/steamclient.so into <out>/<channel>/.
Exit 0: new SHAs (downstream should verify + publish).
Exit 2: all SHAs already published (skip).
Exit 1: failure (atomic: nothing is written).

Usage:
    python3 tools/fetch_client.py --out bins/ --published-shas sha1 sha2
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import NamedTuple

CHANNEL_MANIFESTS = {
    "stable": "https://client-update.fastly.steamstatic.com/steam_client_ubuntu12",
    "beta": "https://client-update.fastly.steamstatic.com/steam_client_publicbeta_ubuntu12",
}
BASE_URL = "https://client-update.fastly.steamstatic.com/"
TARGET_SO = "steamclient.so"
# bins_ubuntu12 first, then any other bins_* package carrying the .so.
_PKG_PRIORITY = ("bins_ubuntu12",)

_VERSION_RE = re.compile(r'"version"\s+"(\d+)"')
_BLOCK_RE = re.compile(r'\r?\n[ \t]+"([a-z0-9_]+)"[ \t]*\r?\n[ \t]*\{([^}]*)\}')
_FILE_RE = re.compile(r'"file"\s+"([^"]+)"')


class Package(NamedTuple):
    name: str
    filename: str


def parse_manifest(text: str) -> tuple[str, list[Package]]:
    """Parse a client manifest (VDF) into (version, packages)."""
    version = _VERSION_RE.search(text)
    if version is None:
        raise ValueError("manifest has no version")
    packages = []
    for block in _BLOCK_RE.finditer(text):
        name, body = block.group(1), block.group(2)
        if name in ("version", "ostype"):
            continue
        found = _FILE_RE.search(body)
        if found is not None:
            packages.append(Package(name, found.group(1)))
    return version.group(1), packages


def select_packages(packages: list[Package]) -> list[str]:
    ordered = sorted(
        packages,
        key=lambda p: (0 if p.name in _PKG_PRIORITY else 1 if p.name.startswith("bins_") else 2),
    )
    return list(dict.fromkeys(p.filename for p in ordered))


def fetch_url(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=300) as r:
        return r.read()


def extract_target(data: bytes) -> bytes | None:
    """Return ubuntu12_32/steamclient.so (or any steamclient.so) from the zip."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        entries: dict[str, str] = {}
        for info in z.infolist():
            entries.setdefault(info.filename.rsplit("/", 1)[-1], info.filename)
        if TARGET_SO not in entries:
            return None
        with z.open(entries[TARGET_SO]) as f:
            return f.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--channels", nargs="*", default=sorted(CHANNEL_MANIFESTS))
    ap.add_argument("--base-url", default=BASE_URL)
    ap.add_argument("--published-shas", nargs="*", default=[])
    args = ap.parse_args()

    unknown = [c for c in args.channels if c not in CHANNEL_MANIFESTS]
    if unknown:
        print(f"unknown channels: {' '.join(unknown)}")
        return 1

    published = set(args.published_shas)
    out = Path(args.out)
    fetched: dict[str, dict[str, str]] = {}

    for channel in args.channels:
        try:
            text = fetch_url(CHANNEL_MANIFESTS[channel]).decode("utf-8", "replace")
            version, packages = parse_manifest(text)
        except Exception as e:  # noqa: BLE001
            print(f"{channel}: manifest fetch/parse failed: {e}")
            return 1
        blob = None
        for filename in select_packages(packages):
            try:
                data = fetch_url(args.base_url + filename)
            except Exception:  # noqa: BLE001
                continue
            blob = extract_target(data)
            if blob is not None:
                break
        if blob is None:
            print(f"{channel}: steamclient.so not found in any package")
            return 1
        sha = hashlib.sha256(blob).hexdigest()
        if sha in published:
            print(f"{channel}: {version} {sha} already published, skip")
            continue
        dest = out / channel / "steamclient.so"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        fetched[channel] = {"version": version, "sha": sha}
        print(f"{channel}: fetched version={version} sha={sha}")

    if not fetched:
        return 2
    for channel, info in fetched.items():
        print(f"NEW {channel} {info['version']} {info['sha']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
