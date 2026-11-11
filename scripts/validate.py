#!/usr/bin/env python3
"""Validate the Red Pen adapter registry and every adapter manifest.

The JSON Schemas catch structural mistakes. The checks below catch mistakes
that a schema cannot express: a registry entry pointing at a missing folder, a
version mismatch, a runtime setting that does not exist, or a table formula
that refers to an unknown column section.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
FORMULA_NUMBER = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")


def load(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate(instance, schema, label: str) -> list[str]:
    errors = []
    for error in sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(instance),
        key=lambda item: list(item.path),
    ):
        location = "/".join(str(part) for part in error.absolute_path) or "(root)"
        errors.append(f"{label} at {location}: {error.message}")
    return errors


def unique_keys(items: list[dict], label: str) -> list[str]:
    seen: set[str] = set()
    errors = []
    for item in items:
        key = item.get("key", "")
        if key in seen:
            errors.append(f"{label}: duplicate key {key!r}")
        seen.add(key)
    return errors


def formula_names(value) -> list[str]:
    if isinstance(value, (int, float)):
        return []
    if not isinstance(value, str):
        return []
    return [name for name in IDENTIFIER.findall(value) if not FORMULA_NUMBER.match(name)]


def formula_errors(field: dict, label: str) -> list[str]:
    table = field.get("table")
    if not table:
        return []
    sections = table.get("columns") or []
    if not sections:
        sections = [
            {"key": "inputs"},
            {"key": "outputs"},
        ] + (table.get("rowSections") or [])
    known = {section["key"] for section in sections}
    known.add("rowCount")
    formulas: list[tuple[str, object]] = []
    for section in sections:
        for name in ("min", "max", "default"):
            if name in section:
                formulas.append((f"{section['key']}.{name}", section[name]))
    for name in ("min", "max", "count", "default"):
        if name in (table.get("rows") or {}):
            formulas.append((f"rows.{name}", table["rows"][name]))
    errors = []
    for formula_label, expression in formulas:
        for name in formula_names(expression):
            if name not in known:
                errors.append(
                    f"{label}: formula {formula_label} refers to unknown section {name!r}"
                )
    return errors


def field_errors(field: dict, label: str) -> list[str]:
    errors = formula_errors(field, label)
    if field.get("type") in {"select", "multiselect"} and not field.get("options"):
        errors.append(f"{label}: {field['type']} field needs options")
    return errors


def main() -> int:
    errors: list[str] = []
    registry_schema = load(ROOT / "schemas" / "registry.schema.json")
    manifest_schema = load(ROOT / "schemas" / "manifest.schema.json")
    registry = load(ROOT / "registry.json")
    errors.extend(validate(registry, registry_schema, "registry.json"))

    entries = registry.get("adapters", [])
    ids = [entry.get("id") for entry in entries]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        errors.append(f"registry.json: duplicate adapter ids: {', '.join(duplicates)}")

    for entry in entries:
        folder = ROOT / entry["folder"]
        label = f"registry entry {entry['id']}"
        if not folder.is_dir():
            errors.append(f"{label}: missing folder {entry['folder']}")
            continue
        manifest_path = folder / "manifest.json"
        if not manifest_path.is_file():
            errors.append(f"{label}: missing manifest.json")
            continue
        manifest = load(manifest_path)
        errors.extend(validate(manifest, manifest_schema, f"{label}/manifest.json"))
        if manifest.get("id") != entry["id"]:
            errors.append(
                f"{label}: manifest id {manifest.get('id')!r} does not match"
            )
        if manifest.get("version") != entry.get("version"):
            errors.append(
                f"{label}: manifest version {manifest.get('version')!r} does not "
                f"match registry version {entry.get('version')!r}"
            )
        for declared in entry.get("files", []):
            name = declared["path"] if isinstance(declared, dict) else declared
            if not (folder / name).is_file():
                errors.append(f"{label}: missing declared file {name!r}")
        settings_keys = {field["key"] for field in manifest.get("settings", [])}
        for runtime in manifest.get("runtimes", []):
            setting = runtime.get("setting")
            if setting and setting not in settings_keys:
                errors.append(
                    f"{label}: runtime setting {setting!r} is not a settings field"
                )
            packages = runtime.get("packages") or {}
            if packages.get("setting") and packages["setting"] not in settings_keys:
                errors.append(
                    f"{label}: package setting {packages['setting']!r} is not a settings field"
                )
        errors.extend(unique_keys(manifest.get("keyInput", []), f"{label} keyInput"))
        errors.extend(unique_keys(manifest.get("settings", []), f"{label} settings"))
        for field in manifest.get("keyInput", []) + manifest.get("settings", []):
            errors.extend(field_errors(field, f"{label} field {field.get('key')}"))
        readme = folder / "README.md"
        if not readme.is_file():
            errors.append(f"{label}: missing README.md for the marketplace page")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"\n{len(errors)} validation error(s).", file=sys.stderr)
        return 1
    print(f"Validated {len(entries)} adapters and registry.json against their schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
