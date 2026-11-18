#!/usr/bin/env python3
"""Write SHA-256 checksums for every file a registry entry lists.

Run this after changing an adapter's manifest or script, then commit the
updated registry.json. Validation fails when a declared checksum is missing or
does not match the file on disk.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for entry in registry["adapters"]:
        folder = ROOT / entry["folder"]
        files = []
        for declared in entry["files"]:
            name = declared["path"] if isinstance(declared, dict) else declared
            files.append({"path": name, "sha256": digest(folder / name)})
        entry["files"] = files
    REGISTRY.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Updated checksums for {len(registry['adapters'])} adapters.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
