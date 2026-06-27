#!/usr/bin/env python3
"""Verify downloaded model weights against pinned SHA-256 hashes.

Reads a manifest (default ``scripts/models.json``; see ``models.example.json``)
and checks each file under ``--models-dir``. Exits non-zero on any mismatch or
missing file so it can gate an image build.

    python scripts/verify_model_hashes.py --models-dir ./weights
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_CHUNK = 1024 * 1024


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="scripts/models.json")
    parser.add_argument("--models-dir", default="weights")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text())
    models = manifest.get("models", [])
    models_dir = Path(args.models_dir)

    failures = 0
    for model in models:
        name = model["name"]
        expected = model.get("sha256", "")
        path = models_dir / f"{name}.pth"

        if not expected or expected.startswith("REPLACE_"):
            print(f"SKIP  {name}: no real hash pinned yet")
            continue
        if not path.exists():
            print(f"FAIL  {name}: missing file {path}")
            failures += 1
            continue

        actual = sha256_of(path)
        if actual != expected:
            print(f"FAIL  {name}: sha256 mismatch\n  expected {expected}\n  actual   {actual}")
            failures += 1
        else:
            print(f"OK    {name}")

    if failures:
        print(f"\n{failures} model(s) failed verification", file=sys.stderr)
        return 1
    print("\nAll pinned models verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
