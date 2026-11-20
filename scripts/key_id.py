#!/usr/bin/env python3
"""Print a minisign public key's key id and SHA-256 fingerprint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import registry as registry_lib  # noqa: E402


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Show a minisign public key identity.")
    parser.add_argument("--public-key", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        key = registry_lib.read_public_key(args.public_key)
    except (registry_lib.RegistryToolError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    payload = {
        "keyId": key.key_id,
        "fingerprint": key.fingerprint,
        "algorithm": key.algorithm,
        "publicKey": key.base64,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"key id:     {key.key_id}")
        print(f"fingerprint:{key.fingerprint}")
        print(f"algorithm:  {key.algorithm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
