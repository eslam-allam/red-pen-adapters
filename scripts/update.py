#!/usr/bin/env python3
"""Regenerate registry.json from adapter folders and registry.config.json.

The signing workflow bumps ``sequence`` and refreshes ``issuedAt``/``expiresAt``
after this script runs. This script intentionally preserves those signing
fields so pull requests do not race the signer.

Official adapters publish exactly the manifest and the adapter script. Extra
files in an adapter folder (README, assets, documentation such as
``lua/red-pen-api.lua``) are not installed and are not listed in the index.
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import registry as registry_lib  # noqa: E402

PUBLISHED_FILES = ("manifest.json", "adapter.lua")

MIRRORED_FIELDS = (
    "name",
    "description",
    "author",
    "icon",
    "homepage",
    "extensions",
    "appliesTo",
    "permissions",
    "registry",
    "runtimes",
    "bootstrap",
)


def build_entry(folder: Path, manifest: dict, readme_base: str) -> dict[str, Any]:
    adapter_id = manifest.get("id")
    if adapter_id != folder.name:
        raise registry_lib.RegistryToolError(
            f"{folder}: manifest id {adapter_id!r} must equal the folder name"
        )
    entry: dict[str, Any] = {"id": adapter_id}
    for field in MIRRORED_FIELDS:
        if field in manifest:
            entry[field] = manifest[field]
    entry["version"] = manifest.get("version")
    if not isinstance(entry["version"], str):
        raise registry_lib.RegistryToolError(
            f"{folder}: manifest.version must be a string"
        )
    entry.setdefault("description", "")
    entry.setdefault("author", "")
    entry.setdefault("appliesTo", ["file"])
    entry.setdefault("permissions", [])
    entry.setdefault("extensions", [])
    entry["folder"] = adapter_id
    files = []
    for relative in PUBLISHED_FILES:
        path = folder / relative
        if not path.is_file():
            raise registry_lib.RegistryToolError(
                f"{folder}: missing published file {relative!r}"
            )
        files.append(
            {"path": relative, "sha256": registry_lib.sha256_file(path)}
        )
    if not files:
        raise registry_lib.RegistryToolError(f"{folder}: no files to publish")
    entry["files"] = files
    entry["readmeUrl"] = f"{readme_base}/{adapter_id}/README.md"
    return entry


def build_registry(
    root: Path,
    config: dict[str, Any],
    existing: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    base = existing or {}
    registry_id = config.get("registryId")
    if not isinstance(registry_id, str) or not registry_lib.REGISTRY_ID.fullmatch(
        registry_id
    ):
        raise registry_lib.RegistryToolError(
            "registry.config.json: registryId is missing or invalid"
        )
    readme_base = config.get("readmeBaseUrl")
    if not isinstance(readme_base, str) or readme_base.endswith("/"):
        raise registry_lib.RegistryToolError(
            "registry.config.json: readmeBaseUrl must not end with a slash"
        )

    adapters = []
    for name in registry_lib.adapter_folders(root):
        folder = root / name
        try:
            manifest = registry_lib.load_json(folder / "manifest.json")
        except registry_lib.RegistryToolError as exc:
            raise registry_lib.RegistryToolError(
                f"{folder / 'manifest.json'}: {exc}"
            ) from exc
        if not isinstance(manifest, dict):
            raise registry_lib.RegistryToolError(
                f"{folder / 'manifest.json'}: manifest must be an object"
            )
        adapters.append(build_entry(folder, manifest, readme_base))
    adapters.sort(key=lambda item: item["id"])
    ids = [item["id"] for item in adapters]
    if len(ids) != len(set(ids)):
        raise registry_lib.RegistryToolError("duplicate adapter ids")

    now = registry_lib.utc_now()
    sequence = base.get("sequence", 1)
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        sequence = 1
    issued_at = base.get("issuedAt") or registry_lib.format_timestamp(now)
    expires_at = base.get("expiresAt") or registry_lib.format_timestamp(
        now + timedelta(days=180)
    )
    publisher = config.get("publisher")
    if not isinstance(publisher, str) or not publisher.strip():
        existing_publisher = base.get("publisher")
        publisher = (
            existing_publisher
            if isinstance(existing_publisher, str) and existing_publisher.strip()
            else "Red Pen adapter registry"
        )

    result: dict[str, Any] = {
        "$schema": "./schemas/registry.schema.json",
        "schema": registry_lib.SCHEMA,
        "kind": registry_lib.KIND,
        "registryId": registry_id,
        "name": base.get("name") or "Red Pen adapter registry",
        "publisher": publisher,
        "sequence": sequence,
        "issuedAt": issued_at,
        "expiresAt": expires_at,
        "adapters": adapters,
    }
    for optional in ("description", "homepage"):
        if base.get(optional):
            result[optional] = base[optional]
    return result


def command(args) -> int:
    root = Path(args.root).resolve()
    config = registry_lib.load_json(root / args.config)
    if not isinstance(config, dict):
        raise registry_lib.RegistryToolError("registry.config.json must be an object")
    registry_path = root / "registry.json"
    existing = None
    if registry_path.is_file():
        existing = registry_lib.load_json(registry_path)
        if not isinstance(existing, dict):
            raise registry_lib.RegistryToolError("registry.json must be an object")
    built = build_registry(root, config, existing)
    expected = registry_lib.canonical_bytes(built)
    current = registry_path.read_bytes() if registry_path.is_file() else b""
    if args.check:
        if current != expected:
            print(
                "registry.json is out of date; run python scripts/update.py",
                file=sys.stderr,
            )
            return 1
        print("registry.json is up to date.")
        return 0
    if current == expected:
        print(f"registry.json already up to date ({len(built['adapters'])} adapters).")
        return 0
    registry_lib.atomic_write(registry_path, expected)
    print(f"Updated registry.json with {len(built['adapters'])} adapter(s).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Regenerate registry.json from adapter folders."
    )
    parser.add_argument("--root", default=str(registry_lib.ROOT))
    parser.add_argument("--config", default="registry.config.json")
    parser.add_argument(
        "--check", action="store_true", help="fail when registry.json is stale"
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return command(args)
    except (registry_lib.RegistryToolError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
