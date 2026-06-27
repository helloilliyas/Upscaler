#!/usr/bin/env python3
"""Download model weights listed in the manifest, then verify their hashes.

Weights are large and licence-restricted, so they are never committed. This
script fetches them into ``--models-dir`` (for a Modal Volume or an image build)
and refuses to keep a file whose SHA-256 does not match the manifest.

    python scripts/download_models.py --models-dir ./weights

Note: only download from official sources you have verified. Filling in the
manifest hashes is required before a file is accepted.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from verify_model_hashes import sha256_of


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {url}")
    with urllib.request.urlopen(url) as resp, dest.open("wb") as out:  # noqa: S310
        while chunk := resp.read(1024 * 1024):
            out.write(chunk)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="scripts/models.json")
    parser.add_argument("--models-dir", default="weights")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"manifest not found: {manifest_path} (copy scripts/models.example.json)", file=sys.stderr)
        return 2

    models = json.loads(manifest_path.read_text()).get("models", [])
    models_dir = Path(args.models_dir)

    for model in models:
        name, url, expected = model["name"], model["url"], model.get("sha256", "")
        if not expected or expected.startswith("REPLACE_"):
            print(f"SKIP  {name}: pin a real sha256 in the manifest before downloading")
            continue

        dest = models_dir / f"{name}.pth"
        if dest.exists() and sha256_of(dest) == expected:
            print(f"OK    {name}: already present and verified")
            continue

        download(url, dest)
        actual = sha256_of(dest)
        if actual != expected:
            dest.unlink(missing_ok=True)
            print(f"FAIL  {name}: hash mismatch, deleted download", file=sys.stderr)
            return 1
        print(f"OK    {name}: verified")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
