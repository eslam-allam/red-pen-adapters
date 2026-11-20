#!/usr/bin/env python3
"""Validate the Red Pen adapter registry and every adapter manifest.

The JSON Schemas catch structural mistakes. The checks below catch mistakes
that a schema cannot express: a registry entry pointing at a missing folder, a
version mismatch, a runtime setting that does not exist, an unsupported mise
tool or backend, a missing adapter.lua, or a table formula that refers to an
unknown column section.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
FORMULA_NUMBER = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
VERSION_LINE = re.compile(r"^-\s+\*\*Version:\*\*\s+(\S+)\s*$", re.MULTILINE)
README_BASE = "https://raw.githubusercontent.com/eslam-allam/red-pen-adapters/main"

# mise tools the registry may name without a backend. Keep this list small:
# an unknown tool must be added here (and tested) rather than fail at run time.
KNOWN_TOOLS = {
    "bun",
    "dart",
    "dotnet",
    "elixir",
    "erlang",
    "gcc",
    "ghc",
    "go",
    "gxx",
    "java",
    "julia",
    "kotlin",
    "lua",
    "node",
    "perl",
    "php",
    "powershell",
    "python",
    "r-base",
    "ruby",
    "rust",
    "scala",
    "swift",
}
# Only the conda backend is allowed. asdf:/vfox: and other prefixes are
# rejected because the app does not pin or verify their plugins.
ALLOWED_BACKENDS = {"conda"}
CONDA_TOOLS = {"gcc", "gxx", "r-base"}
RUNTIME_VERSION = re.compile(
    r"^(?:latest|[0-9]+(?:\.[0-9]+){0,2}(?:[-+][0-9A-Za-z.]+)?)$"
)
CONDA_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

# Fields the registry entry mirrors from the manifest. The entry has no place
# for output, keyInput, questionInput, directories, directoryPicker or
# bootstrap, so those are not compared here.
MIRRORED_FIELDS = (
    "name",
    "description",
    "author",
    "extensions",
    "appliesTo",
    "permissions",
    "registry",
    "runtimes",
)


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


def mirrored_field_errors(entry: dict, manifest: dict, label: str) -> list[str]:
    errors = []
    for field in MIRRORED_FIELDS:
        if manifest.get(field) != entry.get(field):
            errors.append(
                f"{label}: manifest {field} {manifest.get(field)!r} does not match "
                f"registry {field} {entry.get(field)!r}"
            )
    if entry.get("folder") != entry.get("id"):
        errors.append(
            f"{label}: folder {entry.get('folder')!r} does not match id "
            f"{entry.get('id')!r}"
        )
    expected_readme = f"{README_BASE}/{entry.get('folder')}/README.md"
    if entry.get("readmeUrl") != expected_readme:
        errors.append(
            f"{label}: readmeUrl {entry.get('readmeUrl')!r} does not match "
            f"{expected_readme!r}"
        )
    return errors


def runtime_errors(runtime: dict, settings: dict[str, dict], label: str) -> list[str]:
    errors = []
    tool = runtime.get("tool", "")
    version = runtime.get("version", "")
    if not tool:
        return [f"{label}: runtime needs a tool"]

    if ":" in tool:
        backend, _, name = tool.partition(":")
        if backend not in ALLOWED_BACKENDS:
            errors.append(
                f"{label}: runtime backend {backend!r} is not allowed; use conda: "
                f"(asdf: and vfox: are rejected)"
            )
        elif name not in CONDA_TOOLS:
            errors.append(
                f"{label}: unknown conda tool {name!r}; known conda tools: "
                f"{', '.join(sorted(CONDA_TOOLS))}"
            )
        if not CONDA_VERSION.match(version):
            errors.append(
                f"{label}: conda runtime {tool!r} needs a pinned version such as "
                f"16.2.0, not {version!r}"
            )
    elif tool not in KNOWN_TOOLS:
        errors.append(
            f"{label}: unknown mise tool {tool!r}; add it to KNOWN_TOOLS after "
            f"testing it"
        )

    if not RUNTIME_VERSION.match(version):
        errors.append(f"{label}: runtime version {version!r} is not a valid version")

    setting_key = runtime.get("setting")
    if not setting_key:
        return errors
    setting = settings.get(setting_key)
    if setting is None:
        return errors + [
            f"{label}: runtime setting {setting_key!r} is not a settings field"
        ]
    default = setting.get("default")
    if not isinstance(default, str) or not default:
        errors.append(f"{label}: runtime setting {setting_key!r} needs a default")
        return errors
    if setting.get("type") != "select":
        errors.append(
            f"{label}: runtime setting {setting_key!r} must be a select field"
        )
    options = setting.get("options") or []
    if default not in options:
        errors.append(
            f"{label}: runtime setting {setting_key!r} default {default!r} is not "
            f"in its options"
        )
    if version != default:
        errors.append(
            f"{label}: runtime version {version!r} does not match setting "
            f"{setting_key!r} default {default!r}"
        )
    return errors


def bootstrap_errors(manifest: dict, label: str) -> list[str]:
    runtimes = manifest.get("runtimes") or []
    bootstrap = manifest.get("bootstrap") or {}
    errors = []
    if runtimes and not (
        isinstance(bootstrap.get("mise"), str) and bootstrap["mise"].strip()
    ):
        errors.append(f"{label}: managed runtimes need a non-empty bootstrap.mise")
    if not runtimes and bootstrap:
        errors.append(
            f"{label}: bootstrap is declared without a managed runtime"
        )
    return errors


def smoke_errors(
    languages: dict, entries: list[dict]
) -> list[str]:
    errors = []
    by_id = {entry.get("id"): entry for entry in entries}
    declared_smoke = dict(languages.get("smoke") or {})
    for entry in languages["generated"]:
        declared_smoke[entry["id"]] = entry.get("smoke")
    for adapter_id, smoke in sorted(declared_smoke.items()):
        label = f"scripts/languages.json: smoke for {adapter_id!r}"
        if adapter_id not in by_id:
            errors.append(f"{label}: adapter is not in registry.json")
            continue
        if not isinstance(smoke, dict):
            errors.append(f"{label}: needs a source and expected output")
            continue
        for key in ("source", "expected"):
            value = smoke.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label}: needs a non-empty {key!r}")
    for entry in entries:
        adapter_id = entry.get("id")
        if adapter_id in declared_smoke:
            continue
        if entry.get("runtimes"):
            errors.append(
                f"scripts/languages.json: runnable adapter {adapter_id!r} has no "
                f"smoke metadata"
            )
    return errors


def find_luac() -> str | None:
    for name in ("luac", "luac5.4", "luac5.3", "luac5.2", "luac5.1"):
        found = shutil.which(name)
        if found:
            return found
    return None


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

    languages = load(ROOT / "scripts" / "languages.json")
    generated = {item["id"] for item in languages["generated"]}
    classified = generated | set(languages["manual"])
    for adapter_id in ids:
        if adapter_id not in classified:
            errors.append(
                f"registry entry {adapter_id}: not listed in scripts/languages.json "
                f"(add it under generated or manual)"
            )
    for adapter_id in sorted(generated):
        if adapter_id not in ids:
            errors.append(
                f"scripts/languages.json: generated adapter {adapter_id!r} is "
                f"not in registry.json"
            )
    for adapter_id in sorted(set(languages["manual"]) - set(ids)):
        errors.append(
            f"scripts/languages.json: manual adapter {adapter_id!r} is not in "
            f"registry.json"
        )
    for folder in sorted(ROOT.iterdir()):
        if not folder.is_dir() or not (folder / "manifest.json").is_file():
            continue
        if folder.name not in ids:
            errors.append(
                f"adapter folder {folder.name!r} has a manifest.json but is not "
                f"listed in registry.json"
            )
    errors.extend(smoke_errors(languages, entries))

    adapter_lua_paths: list[Path] = []
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
        errors.extend(mirrored_field_errors(entry, manifest, label))
        errors.extend(bootstrap_errors(manifest, label))
        if manifest.get("id") != entry["id"]:
            errors.append(
                f"{label}: manifest id {manifest.get('id')!r} does not match"
            )
        if manifest.get("version") != entry.get("version"):
            errors.append(
                f"{label}: manifest version {manifest.get('version')!r} does not "
                f"match registry version {entry.get('version')!r}"
            )

        adapter_path = folder / "adapter.lua"
        adapter_lua_paths.append(adapter_path)
        if not adapter_path.is_file():
            errors.append(f"{label}: missing adapter.lua")
        declared_files = {
            declared["path"] if isinstance(declared, dict) else declared
            for declared in entry.get("files", [])
        }
        if "adapter.lua" not in declared_files:
            errors.append(f"{label}: adapter.lua is not listed in files")

        for declared in entry.get("files", []):
            name = declared["path"] if isinstance(declared, dict) else declared
            path = folder / name
            if not path.is_file():
                errors.append(f"{label}: missing declared file {name!r}")
                continue
            if not isinstance(declared, dict) or "sha256" not in declared:
                errors.append(
                    f"{label}: file {name!r} needs a sha256 checksum "
                    f"(run python scripts/update_checksums.py)"
                )
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != declared["sha256"].lower():
                errors.append(
                    f"{label}: file {name!r} does not match its sha256 checksum "
                    f"(run python scripts/update_checksums.py)"
                )

        settings = {field["key"]: field for field in manifest.get("settings", [])}
        for runtime in manifest.get("runtimes", []):
            errors.extend(runtime_errors(runtime, settings, label))
            packages = runtime.get("packages") or {}
            if packages.get("setting") and packages["setting"] not in settings:
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
        else:
            documented = VERSION_LINE.search(readme.read_text(encoding="utf-8"))
            if not documented:
                errors.append(
                    f"{label}: README.md needs a '- **Version:** <version>' line"
                )
            elif documented.group(1) != manifest.get("version"):
                errors.append(
                    f"{label}: README.md says version {documented.group(1)!r} but "
                    f"manifest says {manifest.get('version')!r}"
                )

    luac = find_luac()
    if luac:
        for path in adapter_lua_paths:
            if not path.is_file():
                continue
            result = subprocess.run(
                [luac, "-p", str(path)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                errors.append(f"{path.relative_to(ROOT)}: luac -p failed: {detail}")
    else:
        print(
            "warning: luac was not found; skipped the adapter.lua syntax check. "
            "Install Lua 5.x (for example the lua5.4 package) to enable it.",
            file=sys.stderr,
        )

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"\n{len(errors)} validation error(s).", file=sys.stderr)
        return 1
    syntax = "luac -p passed" if luac else "luac -p skipped (luac not installed)"
    print(
        f"Validated {len(entries)} adapters and registry.json against their schemas; "
        f"{syntax}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
