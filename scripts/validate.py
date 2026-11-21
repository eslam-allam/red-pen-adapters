#!/usr/bin/env python3
"""Validate the registry, configuration, manifests, files, and signature.

JSON Schema catches structure. These checks catch what a schema cannot:
stale registry files, wrong folders, missing checksums, mismatched manifests,
expired signing metadata, a missing/invalid signature, and runtime settings
that would send the app to an unknown tool.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import registry as registry_lib  # noqa: E402

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - exercised by the error path
    Draft202012Validator = None  # type: ignore[assignment]
    FormatChecker = None  # type: ignore[assignment]

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
FORMULA_NUMBER = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
VERSION_LINE = re.compile(r"^-\s+\*\*Version:\*\*\s+(\S+)\s*$", re.MULTILINE)
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
# The registry must not offer a Python version that Red Pen has not tested.
# Extend this set together with the Python manifest when a new release ships.
PYTHON_SUPPORTED = {f"3.{minor}" for minor in range(8, 16)}

def load(path: Path) -> Any:
    return registry_lib.load_json(path)


def schema_errors(instance: Any, schema: dict, label: str) -> list[str]:
    if Draft202012Validator is None:
        return [
            "jsonschema is not installed; run: python -m pip install jsonschema"
        ]
    errors = []
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(
        validator.iter_errors(instance),
        key=lambda item: tuple(str(part) for part in item.path),
    ):
        location = "/".join(str(part) for part in error.absolute_path) or "(root)"
        errors.append(f"{label} at {location}: {error.message}")
    return errors


def unique_keys(items: list[dict], label: str) -> list[str]:
    seen: set[str] = set()
    errors = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = item.get("key", "")
        if key in seen:
            errors.append(f"{label}: duplicate key {key!r}")
        seen.add(key)
    return errors


def formula_names(value: Any) -> list[str]:
    if isinstance(value, (int, float)) or not isinstance(value, str):
        return []
    return [name for name in IDENTIFIER.findall(value) if not FORMULA_NUMBER.match(name)]


def formula_errors(field: dict, label: str) -> list[str]:
    table = field.get("table")
    if not isinstance(table, dict):
        return []
    sections = table.get("columns") or []
    if not sections:
        sections = [{"key": "inputs"}, {"key": "outputs"}] + (
            table.get("rowSections") or []
        )
    sections = [
        section
        for section in sections
        if isinstance(section, dict) and isinstance(section.get("key"), str)
    ]
    known = {section["key"] for section in sections}
    known.add("rowCount")
    formulas: list[tuple[str, Any]] = []
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
    field_type = field.get("type")
    options = field.get("options") or []
    if field_type in {"select", "multiselect"} and not options:
        errors.append(f"{label}: {field_type} field needs options")
    if "default" in field and options and field["default"] not in options:
        errors.append(f"{label}: default {field['default']!r} is not in options")
    return errors


def runtime_errors(runtime: dict, settings: dict[str, dict], label: str) -> list[str]:
    errors = []
    tool = runtime.get("tool", "")
    version = runtime.get("version", "")
    if not isinstance(tool, str) or not tool:
        return [f"{label}: runtime needs a tool"]
    if not isinstance(version, str):
        version = ""

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
    if setting_key:
        setting = settings.get(setting_key)
        if setting is None:
            errors.append(
                f"{label}: runtime setting {setting_key!r} is not a settings field"
            )
        else:
            default = setting.get("default")
            if not isinstance(default, str) or not default:
                errors.append(
                    f"{label}: runtime setting {setting_key!r} needs a default"
                )
            else:
                if setting.get("type") != "select":
                    errors.append(
                        f"{label}: runtime setting {setting_key!r} must be a select field"
                    )
                options = setting.get("options") or []
                if default not in options:
                    errors.append(
                        f"{label}: runtime setting {setting_key!r} default "
                        f"{default!r} is not in its options"
                    )
                if version != default:
                    errors.append(
                        f"{label}: runtime version {version!r} does not match setting "
                        f"{setting_key!r} default {default!r}"
                    )

    packages = runtime.get("packages") or {}
    if isinstance(packages, dict) and packages.get("setting"):
        if packages["setting"] not in settings:
            errors.append(
                f"{label}: package setting {packages['setting']!r} is not a "
                "settings field"
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
        errors.append(f"{label}: bootstrap is declared without a managed runtime")
    return errors


def generated_tool_errors(
    manifest: dict, generated_ids: set[str], label: str
) -> list[str]:
    """Generated adapters must use the v2 primary runtime tool.

    They call ``app.run_runtime(manifest.runtimes[0].tool, ...)``. The legacy
    ``language``/``miseTool`` hints no longer exist, and a generated adapter
    with a runtime must name that primary tool.
    """
    if manifest.get("id") not in generated_ids:
        return []
    errors = []
    for legacy in ("language", "miseTool"):
        if legacy in manifest:
            errors.append(
                f"{label}: legacy {legacy!r} is not allowed; declare runtimes[0].tool"
            )
    runtimes = manifest.get("runtimes") or []
    if runtimes:
        primary = runtimes[0] if isinstance(runtimes[0], dict) else {}
        tool = primary.get("tool")
        if not isinstance(tool, str) or not tool.strip():
            errors.append(
                f"{label}: generated adapter needs a primary runtime tool in "
                "runtimes[0].tool"
            )
    return errors


def python_runtime_errors(
    manifest: dict, settings: dict[str, dict], label: str
) -> list[str]:
    """Keep the Python option list inside the versions Phase 0 supports."""
    if manifest.get("id") != "python":
        return []
    field = settings.get("pythonVersion")
    if field is None:
        return []
    options = field.get("options") or []
    unsupported = sorted(
        {option for option in options if option not in PYTHON_SUPPORTED}
    )
    if unsupported:
        return [
            f"{label}: Python options {', '.join(unsupported)} are outside the "
            f"supported set "
            f"{', '.join(sorted(PYTHON_SUPPORTED, key=lambda v: int(v.split('.')[1])))}"
        ]
    return []


def find_luac() -> Optional[str]:
    for name in ("luac", "luac5.4", "luac5.3", "luac5.2", "luac5.1"):
        found = shutil.which(name)
        if found:
            return found
    return None


def validate_config(
    root: Path,
    config: dict,
    config_schema: dict,
    registry: dict,
    errors: list[str],
) -> tuple[bool, Optional[Path]]:
    errors.extend(schema_errors(config, config_schema, "registry.config.json"))
    try:
        registry_lib.load_canonical(root / "registry.config.json")
    except registry_lib.RegistryToolError as exc:
        errors.append(str(exc))

    if config.get("registryId") != registry.get("registryId"):
        errors.append(
            f"registry.config.json registryId {config.get('registryId')!r} does not "
            f"match registry.json {registry.get('registryId')!r}"
        )
    if config.get("publisher") != registry.get("publisher"):
        errors.append(
            f"registry.config.json publisher {config.get('publisher')!r} does not "
            f"match registry.json {registry.get('publisher')!r}"
        )

    expected_base = (
        f"https://raw.githubusercontent.com/{config.get('repository')}/main"
    )
    if config.get("readmeBaseUrl") != expected_base:
        errors.append(
            f"registry.config.json readmeBaseUrl must be {expected_base!r} "
            "(no trailing slash)"
        )

    signing = config.get("signing") or {}
    tier = config.get("tier")
    expected_id = registry_lib.expected_registry_id(tier)
    if expected_id is not None and config.get("registryId") != expected_id:
        errors.append(
            f"{tier} registries must use registryId {expected_id!r}"
        )
    if (
        tier == "third-party"
        and config.get("registryId") in registry_lib.RESERVED_REGISTRY_IDS
    ):
        errors.append(
            "third-party registries may not use a reserved official/community registryId"
        )
    key_path: Optional[Path] = None
    key_file = signing.get("keyFile")
    if key_file:
        key_path = root / key_file
        if not key_path.is_file():
            errors.append(f"signing key file is missing: {key_file}")
            key_path = None
        else:
            try:
                registry_lib.read_public_key(key_path)
            except registry_lib.RegistryToolError as exc:
                errors.append(f"{key_file}: {exc}")
                key_path = None

    if tier in ("official", "community"):
        expected_environment = f"registry-signing-{tier}"
        if config.get("requireSignature") is not True:
            errors.append(f"{tier} registries must set requireSignature: true")
        if signing.get("enabled") is not True:
            errors.append(f"{tier} registries must set signing.enabled: true")
        if signing.get("environment") != expected_environment:
            errors.append(
                f"{tier} registries must use the protected environment "
                f"{expected_environment!r}"
            )

    if tier in ("official", "community") and signing.get("signerRepository") != "eslam-allam/red-pen-registry-signing":
        errors.append(
            f"{tier} registries must use the expected signer repository "
            "'eslam-allam/red-pen-registry-signing'"
        )
    if signing.get("signerRepository") == config.get("repository"):
        errors.append("signing.signerRepository must be a separate repository")
    if signing.get("enabled"):
        if not signing.get("environment"):
            errors.append("signing.enabled requires signing.environment")
        if not key_file:
            errors.append("signing.enabled requires signing.keyFile")

    if config.get("requireSignature") and key_path is None:
        errors.append("requireSignature needs a valid signing.keyFile")
    return bool(config.get("requireSignature")), key_path


def validate_registry_metadata(
    registry: dict,
    config: dict,
    errors: list[str],
    *,
    allow_expired: bool,
    now: datetime,
) -> None:
    if registry.get("schema") != registry_lib.SCHEMA:
        errors.append(f"registry.json schema must be {registry_lib.SCHEMA}")
    if registry.get("kind") != registry_lib.KIND:
        errors.append(f"registry.json kind must be {registry_lib.KIND!r}")
    if "name" in registry:
        errors.append(
            "registry.json root name is not allowed in schema 7; use publisher"
        )
    try:
        registry_id, sequence = registry_lib.registry_identity(registry)
    except registry_lib.RegistryToolError as exc:
        errors.append(f"registry.json: {exc}")
        return
    if registry_id != config.get("registryId"):
        errors.append("registry.json registryId does not match registry.config.json")
    if sequence < 1:
        errors.append("registry.json sequence must be positive")
    publisher = registry.get("publisher")
    if not isinstance(publisher, str):
        errors.append("registry.json publisher must be a string")
    elif not publisher.strip():
        errors.append("registry.json publisher must not be empty")
    elif len(publisher) > 256:
        errors.append("registry.json publisher must be at most 256 characters")
    elif any(ord(character) < 0x20 or ord(character) == 0x7F for character in publisher):
        errors.append("registry.json publisher must not contain control characters")
    try:
        issued_at = registry_lib.parse_timestamp(registry.get("issuedAt"), "issuedAt")
        expires_at = registry_lib.parse_timestamp(registry.get("expiresAt"), "expiresAt")
    except registry_lib.RegistryToolError as exc:
        errors.append(f"registry.json: {exc}")
        return
    if expires_at <= issued_at:
        errors.append("registry.json expiresAt must be later than issuedAt")
    if expires_at - issued_at > timedelta(days=registry_lib.MAX_EXPIRES_DAYS):
        errors.append(
            f"registry.json lifetime must not exceed {registry_lib.MAX_EXPIRES_DAYS} days"
        )
    if issued_at > now + registry_lib.CLOCK_SKEW:
        errors.append("registry.json issuedAt is in the future")
    if not allow_expired and expires_at <= now:
        errors.append("registry.json has expired; re-sign it with a new sequence")


def validate_entry(
    root: Path,
    entry: dict,
    manifest_schema: dict,
    errors: list[str],
    *,
    readme_base: str,
    mirrored_fields: tuple[str, ...],
    generated_ids: set[str],
    check_luac: bool,
) -> None:
    adapter_id = entry.get("id")
    label = f"adapter {adapter_id!r}"
    folder_name = entry.get("folder")
    if folder_name != adapter_id:
        errors.append(f"{label}: folder must equal id")
    if (
        not isinstance(folder_name, str)
        or folder_name in ("", ".", "..")
        or "/" in folder_name
        or "\\" in folder_name
    ):
        errors.append(f"{label}: unsafe folder name {folder_name!r}")
        return
    folder = root / folder_name
    if not folder.is_dir():
        errors.append(f"{label}: missing folder {folder_name!r}")
        return
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        errors.append(f"{label}: missing manifest.json")
        return
    try:
        manifest = load(manifest_path)
    except registry_lib.RegistryToolError as exc:
        errors.append(f"{label}/manifest.json: {exc}")
        return
    if not isinstance(manifest, dict):
        errors.append(f"{label}/manifest.json: must be an object")
        return
    errors.extend(schema_errors(manifest, manifest_schema, f"{label}/manifest.json"))
    if manifest.get("schema") != registry_lib.MANIFEST_SCHEMA:
        errors.append(
            f"{label}: manifest schema must be {registry_lib.MANIFEST_SCHEMA}"
        )
    if (
        manifest.get("apiVersion") != registry_lib.API_VERSION
        or entry.get("apiVersion") != registry_lib.API_VERSION
        or manifest.get("apiVersion") != entry.get("apiVersion")
    ):
        errors.append(
            f"{label}: manifest and registry entry apiVersion must both be "
            f"{registry_lib.API_VERSION}"
        )
    if manifest.get("id") != adapter_id:
        errors.append(f"{label}: manifest id {manifest.get('id')!r} does not match")
    if manifest.get("version") != entry.get("version"):
        errors.append(
            f"{label}: manifest version {manifest.get('version')!r} does not match "
            f"registry version {entry.get('version')!r}"
        )
    for field in mirrored_fields:
        if manifest.get(field) != entry.get(field):
            errors.append(
                f"{label}: manifest {field} {manifest.get(field)!r} does not match "
                f"registry {field} {entry.get(field)!r}"
            )
    errors.extend(bootstrap_errors(manifest, label))

    files = entry.get("files")
    if not isinstance(files, list) or not files:
        errors.append(f"{label}: files must be a non-empty array")
    else:
        seen: set[str] = set()
        for declared in files:
            if not isinstance(declared, dict):
                errors.append(f"{label}: every file must be an object with sha256")
                continue
            name = declared.get("path")
            digest = declared.get("sha256")
            if not registry_lib.safe_relative_path(name):
                errors.append(f"{label}: unsafe file path {name!r}")
                continue
            if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                errors.append(
                    f"{label}: file {name!r} needs a lowercase sha256 "
                    "(run python scripts/update.py)"
                )
                continue
            if name in seen:
                errors.append(f"{label}: duplicate file {name!r}")
            seen.add(name)
            path = folder / name
            if not path.is_file():
                errors.append(f"{label}: missing declared file {name!r}")
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != actual:
                errors.append(
                    f"{label}: file {name!r} does not match its sha256 "
                    "(run python scripts/update.py)"
                )
        for required in ("manifest.json", "adapter.lua"):
            if required not in seen:
                errors.append(f"{label}: files must include {required!r}")
    if not (folder / "adapter.lua").is_file():
        errors.append(f"{label}: missing adapter.lua")
    elif check_luac:
        luac = find_luac()
        if luac is None:
            errors.append(
                f"{label}: luac was not found; install Lua 5.x or run without --luac"
            )
        else:
            result = subprocess.run(
                [luac, "-p", str(folder / "adapter.lua")],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append(
                    f"{label}: luac rejected adapter.lua: "
                    f"{(result.stderr or result.stdout).strip()}"
                )

    readme_url = entry.get("readmeUrl")
    expected_readme = f"{readme_base}/{adapter_id}/README.md"
    readme = folder / "README.md"
    if not readme.is_file():
        errors.append(f"{label}: missing README.md")
    else:
        match = VERSION_LINE.search(readme.read_text(encoding="utf-8"))
        if not match:
            errors.append(f"{label}: README.md needs '- **Version:** <version>'")
        elif match.group(1) != manifest.get("version"):
            errors.append(
                f"{label}: README.md says version {match.group(1)!r} but manifest "
                f"says {manifest.get('version')!r}"
            )
    if readme_url != expected_readme:
        errors.append(
            f"{label}: readmeUrl must be {expected_readme!r}, got {readme_url!r}"
        )

    settings_list = manifest.get("settings")
    key_input = manifest.get("keyInput")
    runtimes = manifest.get("runtimes")
    if not isinstance(settings_list, list):
        settings_list = []
    if not isinstance(key_input, list):
        key_input = []
    if not isinstance(runtimes, list):
        runtimes = []
    settings = {
        field.get("key"): field
        for field in settings_list
        if isinstance(field, dict)
    }
    errors.extend(unique_keys(key_input, f"{label} keyInput"))
    errors.extend(unique_keys(settings_list, f"{label} settings"))
    for field in key_input + settings_list:
        if isinstance(field, dict):
            errors.extend(field_errors(field, f"{label} field {field.get('key')}"))
    errors.extend(generated_tool_errors(manifest, generated_ids, label))
    errors.extend(python_runtime_errors(manifest, settings, label))
    for runtime in runtimes:
        if isinstance(runtime, dict):
            errors.extend(runtime_errors(runtime, settings, f"{label} runtime"))


def validate_release_metadata(
    root: Path,
    registry: dict,
    config: dict,
    errors: list[str],
) -> None:
    release_path = root / "release.json"
    if not release_path.is_file():
        return
    try:
        release = load(release_path)
    except registry_lib.RegistryToolError as exc:
        errors.append(str(exc))
        return
    if not isinstance(release, dict):
        errors.append("release.json must be an object")
        return
    try:
        registry_id, sequence = registry_lib.registry_identity(registry)
    except registry_lib.RegistryToolError:
        return
    expected_tag = f"registry-v{sequence}"
    checks = {
        "registryId": registry_id,
        "sequence": sequence,
        "tag": expected_tag,
        "tier": config.get("tier"),
        "signerCommit": (config.get("signing") or {}).get("signerCommit"),
        "issuedAt": registry.get("issuedAt"),
        "expiresAt": registry.get("expiresAt"),
    }
    for field, expected in checks.items():
        if release.get(field) != expected:
            errors.append(
                f"release.json {field} {release.get(field)!r} does not match "
                f"{expected!r}"
            )
    if release.get("registrySha256") != registry_lib.sha256_file(root / "registry.json"):
        errors.append("release.json registrySha256 does not match registry.json")
    signature_path = root / "registry.json.minisig"
    if not signature_path.is_file():
        errors.append("release.json exists but registry.json.minisig is missing")
    elif release.get("signatureSha256") != registry_lib.sha256_file(signature_path):
        errors.append("release.json signatureSha256 does not match registry.json.minisig")
    key_id = release.get("keyId")
    fingerprint = release.get("publicKeyFingerprint")
    if not isinstance(key_id, str) or not re.fullmatch(r"[0-9A-F]{16}", key_id):
        errors.append("release.json keyId is not an uppercase 16-character hex key id")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        errors.append("release.json publicKeyFingerprint is not a SHA-256 hex digest")
    key_file = (config.get("signing") or {}).get("keyFile")
    if key_file:
        try:
            key = registry_lib.read_public_key(root / key_file)
        except (registry_lib.RegistryToolError, OSError) as exc:
            errors.append(f"release.json cannot check the signing key: {exc}")
        else:
            if release.get("keyId") != key.key_id:
                errors.append("release.json keyId does not match signing.keyFile")
            if release.get("publicKeyFingerprint") != key.fingerprint:
                errors.append(
                    "release.json publicKeyFingerprint does not match signing.keyFile"
                )


def validate_languages(
    root: Path, ids: list[str], errors: list[str]
) -> tuple[Optional[dict], set[str]]:
    """Official repository check: every adapter is classified in languages.json."""

    path = root / "scripts" / "languages.json"
    if not path.is_file():
        return None, set()
    try:
        languages = load(path)
    except registry_lib.RegistryToolError as exc:
        errors.append(f"scripts/languages.json: {exc}")
        return None, set()
    if not isinstance(languages, dict):
        errors.append("scripts/languages.json must be an object")
        return None, set()
    generated_items = languages.get("generated")
    manual_items = languages.get("manual")
    if not isinstance(generated_items, list) or not isinstance(manual_items, list):
        errors.append("scripts/languages.json needs generated and manual arrays")
        return None, set()
    generated = {
        item.get("id") for item in generated_items if isinstance(item, dict)
    }
    manual = {item for item in manual_items if isinstance(item, str)}
    classified = generated | manual
    for adapter_id in ids:
        if adapter_id not in classified:
            errors.append(
                f"registry entry {adapter_id}: not listed in scripts/languages.json "
                "(add it under generated or manual)"
            )
    for adapter_id in sorted(generated):
        if adapter_id not in ids:
            errors.append(
                f"scripts/languages.json: generated adapter {adapter_id!r} is not "
                "in registry.json"
            )
    for adapter_id in sorted(manual - set(ids)):
        errors.append(
            f"scripts/languages.json: manual adapter {adapter_id!r} is not in "
            "registry.json"
        )
    return languages, generated


def smoke_errors(languages: dict, entries: list[dict]) -> list[str]:
    errors = []
    by_id = {entry.get("id"): entry for entry in entries}
    declared_smoke = dict(languages.get("smoke") or {})
    for entry in languages.get("generated") or []:
        if isinstance(entry, dict):
            declared_smoke[entry.get("id")] = entry.get("smoke")
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


def collect_errors(
    root: Path,
    *,
    require_signature: Optional[bool] = None,
    verify_present: bool = False,
    allow_expired: bool = False,
    skip_release: bool = False,
    check_luac: bool = False,
    now: Optional[datetime] = None,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if Draft202012Validator is None:
        return (
            [
                "jsonschema is not installed; run: "
                "python -m pip install jsonschema"
            ],
            {},
        )
    root = root.resolve()
    registry_schema = load(root / "schemas" / "registry.schema.json")
    manifest_schema = load(root / "schemas" / "manifest.schema.json")
    config_schema = load(root / "schemas" / "registry.config.schema.json")
    registry_path = root / "registry.json"
    config_path = root / "registry.config.json"
    try:
        registry = load(registry_path)
        config = load(config_path)
    except (registry_lib.RegistryToolError, FileNotFoundError) as exc:
        return ([str(exc)], {})
    if not isinstance(registry, dict) or not isinstance(config, dict):
        return (["registry.json and registry.config.json must be objects"], {})

    try:
        registry_lib.load_canonical(registry_path)
    except registry_lib.RegistryToolError as exc:
        errors.append(str(exc))

    errors.extend(schema_errors(registry, registry_schema, "registry.json"))
    errors.extend(registry_lib.contract_source_errors(root))
    try:
        mirrored_fields = registry_lib.load_mirrored_fields(root)
    except registry_lib.RegistryToolError as exc:
        errors.append(str(exc))
        mirrored_fields = ()
    _, key_path = validate_config(
        root, config, config_schema, registry, errors
    )
    current = (now or registry_lib.utc_now()).astimezone(timezone.utc)
    validate_registry_metadata(
        registry, config, errors, allow_expired=allow_expired, now=current
    )

    entries = registry.get("adapters") or []
    if isinstance(entries, list):
        ids = [entry.get("id") for entry in entries if isinstance(entry, dict)]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            errors.append(f"registry.json: duplicate adapter ids: {', '.join(duplicates)}")
        languages, generated = validate_languages(root, ids, errors)
        discovered = set(registry_lib.adapter_folders(root))
        registered = {entry.get("folder") for entry in entries if isinstance(entry, dict)}
        for missing in sorted(discovered - registered):
            errors.append(f"adapter folder {missing!r} is missing from registry.json")
        for extra in sorted(item for item in registered - discovered if item):
            errors.append(f"registry entry {extra!r} has no adapter folder")
        if languages is not None:
            errors.extend(
                smoke_errors(
                    languages,
                    [entry for entry in entries if isinstance(entry, dict)],
                )
            )
        for entry in entries:
            if isinstance(entry, dict):
                validate_entry(
                    root,
                    entry,
                    manifest_schema,
                    errors,
                    readme_base=str(config.get("readmeBaseUrl")),
                    mirrored_fields=mirrored_fields,
                    generated_ids=generated,
                    check_luac=check_luac,
                )

    signature_path = root / "registry.json.minisig"
    signature_required = bool(require_signature)
    signature_info: dict[str, Any] = {}
    if signature_required or (verify_present and signature_path.is_file()):
        if key_path is None:
            errors.append(
                "a signature is required, but no valid signing.keyFile is configured"
            )
        elif not signature_path.is_file():
            errors.append("registry.json.minisig is required but missing")
        else:
            try:
                key = registry_lib.verify_signature(
                    registry_path, signature_path, key_path
                )
                signature_info = {
                    "valid": True,
                    "keyId": key.key_id,
                    "fingerprint": key.fingerprint,
                }
            except registry_lib.RegistryToolError as exc:
                errors.append(f"signature: {exc}")

    if not skip_release:
        validate_release_metadata(root, registry, config, errors)

    return errors, {
        "adapters": len(entries) if isinstance(entries, list) else 0,
        "sequence": registry.get("sequence"),
        "registryId": registry.get("registryId"),
        "signature": signature_info,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the Red Pen adapter registry."
    )
    parser.add_argument("--root", default=str(registry_lib.ROOT))
    parser.add_argument(
        "--require-signature",
        action="store_true",
        help="fail when registry.json.minisig is missing or invalid",
    )
    parser.add_argument(
        "--skip-signature",
        action="store_true",
        help="accepted for compatibility; signatures are not checked by default",
    )
    parser.add_argument(
        "--verify-signature",
        action="store_true",
        help="verify registry.json.minisig when it is present",
    )
    parser.add_argument(
        "--allow-expired",
        action="store_true",
        help="accept an expired registry (not for releases)",
    )
    parser.add_argument(
        "--skip-release",
        action="store_true",
        help="skip release.json checks during pre-signing validation",
    )
    parser.add_argument(
        "--luac",
        action="store_true",
        help="run luac -p on every adapter.lua when luac is installed",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.require_signature and args.skip_signature:
        print("error: --require-signature and --skip-signature conflict", file=sys.stderr)
        return 2
    require_signature: Optional[bool] = None
    if args.require_signature:
        require_signature = True
    elif args.skip_signature:
        require_signature = False
    try:
        errors, summary = collect_errors(
            Path(args.root),
            require_signature=require_signature,
            verify_present=args.verify_signature,
            allow_expired=args.allow_expired,
            skip_release=args.skip_release,
            check_luac=args.luac,
        )
    except (registry_lib.RegistryToolError, FileNotFoundError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"\n{len(errors)} validation error(s).", file=sys.stderr)
        return 1
    signature = "signed" if summary.get("signature") else "unsigned"
    print(
        f"Validated {summary.get('adapters', 0)} adapter(s), "
        f"{summary.get('registryId')} sequence {summary.get('sequence')} ({signature})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
