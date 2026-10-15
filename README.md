# steam-monitor (Linux)

Automated tracker for Linux Steam client builds. Polls the stable and
beta client manifests, verifies known hook signatures against each new
`steamclient.so`, and records verified build hashes under
`data/updates.yaml` (`SafeModeHashes`, consumed by compatible clients).

Requires only Python 3.8+ from stdlib (no third-party packages).

## Channels

| Channel  | Manifest                                    | Contents                          |
|----------|---------------------------------------------|-----------------------------------|
| `stable` | `steam_client_ubuntu12`                     | Current public client build       |
| `beta`   | `steam_client_publicbeta_ubuntu12`          | Public beta (often == stable)     |

Both channels ship `bins_ubuntu12.zip` containing
`ubuntu12_32/steamclient.so`. Steam Deck uses the same binaries
(`steamdeck_stable` shares hashes with `ubuntu12_32`).

## Pipeline (every 15 min via `.github/workflows/monitor.yml`)

1. `tools/fetch_client.py` → `bins/<channel>/steamclient.so`
2. `tools/check_patterns.py` → every signature in
   `data/patterns.json` must match
3. `tools/publish.py` → `data/published.json` + `data/updates.yaml`

Exit contract:

| Exit | Meaning                                   | Pipeline action              |
|------|-------------------------------------------|------------------------------|
| 0    | New build(s) fetched                      | Verify, then publish         |
| 2    | All SHAs already published                | Skip silently                |
| 1    | Fetch/verify failure, or required `FAIL`  | Publish nothing, file issue  |

Local run:

```sh
python3 -m unittest discover -s tests
python3 tools/fetch_client.py --out bins/ --channels stable beta
python3 tools/check_patterns.py --so bins/stable/steamclient.so
python3 tools/publish.py --version <build> --channel stable --sha <sha256>
```

Refreshing the signature set (manual, review the diff before commit):

```sh
python3 tools/snapshot_patterns.py --src /path/to/patterns.cpp
```

## When a required pattern FAILs

1. Nothing is published — clients keep working on the last known build.
2. An issue is filed with the `FAIL <name>` lines.
3. Re-derive the signature from the new binary (disassemble the function,
   pick stable prologue bytes, keep `??` wildcards over addresses),
   refresh the snapshot, re-run via `workflow_dispatch`.

## Stale clients crash — update Steam

Hook code built for one client layout crashes on another
(`getProtoBufTypeName` AV in `RecvPkt` is the classic symptom).
If your local `steamclient.so` fails signatures the CDN build passes
(or vice versa), force the update and re-check:

```sh
steam -forcesteamupdate -forcepackagedownload -exitsteam
```

Check the *running* binary (`ubuntu12_32/steamclient.so`), not the stale
legacy copy in `linux32/` — they can be different builds under the same
install, and only the former is what Steam loads.

## Data formats

- `data/patterns.json`: `[{name, sig, optional}]` — `sig` is space-separated
  hex with `??` wildcards; `optional` mirrors the client's skip-list
  (warn-only misses for resilient hooks).
- `data/published.json`: `{version: {channel, sha, file}}`.
- `data/updates.yaml`: `SafeModeHashes:\n  <version>:\n    - <sha> #ubuntu12_32`.
