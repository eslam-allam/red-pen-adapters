#!/usr/bin/env python3
"""Shared registry format helpers for the Red Pen adapter template.

This module is deliberately dependency-free. ``validate.py`` adds jsonschema;
everything here works on a stock Python 3.8+ interpreter.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Union

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = 7
MANIFEST_SCHEMA = 5
API_VERSION = 2
KIND = "red-pen-adapters"
CONTRACT_FILES = (
    "schemas/manifest.schema.json",
    "schemas/registry.schema.json",
    "schemas/mirror-fields.json",
    "lua/red-pen-api.lua",
)
REGISTRY_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
TIER_REGISTRY_IDS = {"official": "red-pen-official", "community": "red-pen-community"}
RESERVED_REGISTRY_IDS = frozenset(TIER_REGISTRY_IDS.values())
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
MAX_SEQUENCE = 2147483647
MAX_EXPIRES_DAYS = 366
CLOCK_SKEW = timedelta(minutes=5)
SIGNATURE_LIMIT = 16 * 1024
ADAPTER_METADATA_DIRS = {
    ".git",
    ".github",
    ".vscode",
    "docs",
    "keys",
    "schemas",
    "scripts",
    "tests",
}
SKIP_ADAPTER_FILES = {"README.md", ".DS_Store"}


class RegistryToolError(ValueError):
    """A file is malformed or a local tool is missing."""


@dataclass(frozen=True)
class PublicKeyInfo:
    key_id: str
    fingerprint: str
    algorithm: str
    base64: str
    raw: bytes


def canonical_text(value: Any) -> str:
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise RegistryToolError(f"value cannot be encoded as JSON: {exc}") from exc
    return rendered + "\n"


def canonical_bytes(value: Any) -> bytes:
    return canonical_text(value).encode("utf-8")


def loads_strict(data: bytes, label: str = "document") -> Any:
    if data.startswith(b"\xef\xbb\xbf"):
        raise RegistryToolError(f"{label}: UTF-8 BOM is not allowed")
    if b"\r" in data:
        raise RegistryToolError(f"{label}: CRLF is not allowed; use LF")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RegistryToolError(f"{label}: not valid UTF-8: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RegistryToolError(f"{label}: invalid JSON: {exc}") from exc


def check_canonical_bytes(data: bytes, label: str = "document") -> Any:
    value = loads_strict(data, label)
    if data != canonical_bytes(value):
        raise RegistryToolError(
            f"{label}: not deterministic JSON (sorted keys, two-space indent, "
            "LF, one trailing newline); run python scripts/registry.py format"
        )
    return value


def load_json(path: Union[str, Path]) -> Any:
    return loads_strict(Path(path).read_bytes(), str(path))


def load_canonical(path: Union[str, Path]) -> Any:
    return check_canonical_bytes(Path(path).read_bytes(), str(path))


def load_mirrored_fields(root: Union[str, Path] = ROOT) -> tuple[str, ...]:
    """Load the manifest fields a schema 7 registry entry must mirror."""

    path = Path(root) / "schemas" / "mirror-fields.json"
    if not path.is_file():
        raise RegistryToolError(
            f"{path}: missing mirror-fields.json; copy it from the app contract"
        )
    try:
        value = load_json(path)
    except RegistryToolError as exc:
        raise RegistryToolError(f"{path}: {exc}") from exc
    fields = value.get("fields") if isinstance(value, dict) else None
    if not isinstance(fields, list) or not fields:
        raise RegistryToolError(f"{path}: fields must be a non-empty array")
    if any(not isinstance(field, str) or not field for field in fields):
        raise RegistryToolError(f"{path}: every mirrored field must be a non-empty string")
    if len(fields) != len(set(fields)):
        raise RegistryToolError(f"{path}: duplicate mirrored field")
    return tuple(fields)


def load_contract_source(root: Union[str, Path] = ROOT) -> dict[str, Any]:
    path = Path(root) / "schemas" / "source.json"
    if not path.is_file():
        raise RegistryToolError(
            f"{path}: missing source.json; copy it with the generated contract files"
        )
    try:
        value = load_json(path)
    except RegistryToolError as exc:
        raise RegistryToolError(f"{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RegistryToolError(f"{path}: must be an object")
    return value


def contract_source_errors(root: Union[str, Path] = ROOT) -> list[str]:
    """Check the copied contract files still match schemas/source.json."""

    try:
        source = load_contract_source(root)
    except RegistryToolError as exc:
        return [str(exc)]
    errors: list[str] = []
    commit = source.get("appCommit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        errors.append("schemas/source.json: appCommit must be a full lowercase SHA")
    files = source.get("files")
    if not isinstance(files, dict) or not files:
        errors.append("schemas/source.json: files must be a non-empty object")
    else:
        for relative in CONTRACT_FILES:
            if relative not in files:
                errors.append(f"schemas/source.json: files must include {relative!r}")
        for relative, digest in sorted(files.items()):
            if not isinstance(relative, str) or not safe_relative_path(relative):
                errors.append(f"schemas/source.json: unsafe file path {relative!r}")
                continue
            if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                errors.append(
                    f"schemas/source.json: {relative!r} needs a lowercase SHA-256"
                )
                continue
            path = Path(root) / relative
            if not path.is_file():
                errors.append(f"schemas/source.json: copied file {relative!r} is missing")
            elif sha256_file(path) != digest:
                errors.append(
                    f"schemas/source.json: {relative!r} does not match its SHA-256"
                )
    return errors


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Union[str, Path]) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Union[str, Path], data: bytes, mode: int = 0o644) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
    except BaseException:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise


def parse_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not TIMESTAMP.fullmatch(value):
        raise RegistryToolError(
            f"{label} must be an RFC 3339 UTC timestamp like 2026-01-31T12:00:00Z"
        )
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise RegistryToolError(f"{label} is not a real date: {value}") from exc


def format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def trusted_comment(registry_id: str, sequence: int) -> str:
    if not REGISTRY_ID.fullmatch(registry_id):
        raise RegistryToolError("invalid registryId for a trusted comment")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise RegistryToolError("invalid sequence for a trusted comment")
    return f"registryId={registry_id} sequence={sequence}"


def parse_trusted_comment(comment: str) -> tuple[str, int]:
    match = re.fullmatch(
        r"registryId=([a-z0-9][a-z0-9._-]{0,127}) sequence=(\d+)", comment
    )
    if not match:
        raise RegistryToolError(
            "trusted comment must be exactly 'registryId=<id> sequence=<n>'"
        )
    sequence = int(match.group(2))
    if sequence < 1:
        raise RegistryToolError("trusted comment sequence must be positive")
    return match.group(1), sequence


def parse_public_key(data: Union[bytes, str], label: str = "public key") -> PublicKeyInfo:
    exact = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    try:
        text = exact.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RegistryToolError(f"{label}: not valid UTF-8") from exc

    candidates: list[bytes] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("untrusted comment:"):
            continue
        try:
            decoded = base64.b64decode(stripped, validate=True)
        except (binascii.Error, ValueError):
            continue
        if len(decoded) == 42 and decoded.startswith(b"Ed"):
            candidates.append(decoded)
    if not candidates:
        raise RegistryToolError(f"{label}: no minisign Ed25519 public key found")
    if len(set(candidates)) > 1:
        raise RegistryToolError(f"{label}: contains more than one public key")
    raw = candidates[0]
    return PublicKeyInfo(
        key_id=raw[2:10][::-1].hex().upper(),
        fingerprint=hashlib.sha256(exact).hexdigest(),
        algorithm=raw[:2].decode("ascii"),
        base64=base64.b64encode(raw).decode("ascii"),
        raw=raw,
    )


def read_public_key(path: Union[str, Path]) -> PublicKeyInfo:
    return parse_public_key(Path(path).read_bytes(), str(path))


def read_signature(path: Union[str, Path]) -> tuple[str, str]:
    signature_path = Path(path)
    if not signature_path.is_file():
        raise RegistryToolError(f"signature file is missing: {signature_path}")
    if signature_path.stat().st_size > SIGNATURE_LIMIT:
        raise RegistryToolError("signature file is larger than the 16 KiB limit")
    try:
        lines = signature_path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise RegistryToolError("signature file is not UTF-8 text") from exc
    if len(lines) != 4:
        raise RegistryToolError(
            "signature file must contain an untrusted comment, signature, "
            "trusted comment, and global signature"
        )
    if not lines[0].startswith("untrusted comment: "):
        raise RegistryToolError("signature file has no untrusted comment")
    if not lines[2].startswith("trusted comment: "):
        raise RegistryToolError("signature file has no trusted comment")
    return lines[0], lines[2][len("trusted comment: ") :]


def find_minisign(explicit: Optional[str] = None) -> str:
    candidate = explicit or os.environ.get("MINISIGN_BIN") or _which("minisign")
    if not candidate:
        raise RegistryToolError(
            "minisign was not found; install minisign 0.12 or set MINISIGN_BIN"
        )
    path = Path(candidate)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise RegistryToolError(f"minisign binary is not executable: {candidate}")
    return str(path)


def _which(name: str) -> Optional[str]:
    from shutil import which

    return which(name)


def safe_environment() -> dict[str, str]:
    """A minimal child environment that never includes MINISIGN_PASSWORD."""

    keep = ("PATH", "HOME", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL", "TZ")
    return {name: os.environ[name] for name in keep if name in os.environ}


def verify_signature(
    registry_path: Union[str, Path],
    signature_path: Union[str, Path],
    public_key_path: Union[str, Path],
    *,
    minisign_bin: Optional[str] = None,
) -> PublicKeyInfo:
    key = read_public_key(public_key_path)
    registry = load_canonical(registry_path)
    if not isinstance(registry, dict):
        raise RegistryToolError("registry must be a JSON object")
    registry_id = registry.get("registryId")
    sequence = registry.get("sequence")
    if not isinstance(registry_id, str) or not isinstance(sequence, int):
        raise RegistryToolError("registry has no registryId/sequence")
    _, comment = read_signature(signature_path)
    comment_id, comment_sequence = parse_trusted_comment(comment)
    expected = trusted_comment(registry_id, sequence)
    if comment != expected or comment_id != registry_id or comment_sequence != sequence:
        raise RegistryToolError(
            "signature trusted comment does not match the registry id/sequence"
        )
    result = subprocess.run(
        [
            find_minisign(minisign_bin),
            "-V",
            "-q",
            "-p",
            str(public_key_path),
            "-m",
            str(registry_path),
            "-x",
            str(signature_path),
        ],
        check=False,
        capture_output=True,
        timeout=60,
        env=safe_environment(),
    )
    if result.returncode != 0:
        raise RegistryToolError("minisign verification failed")
    return key


def registry_identity(registry: dict) -> tuple[str, int]:
    registry_id = registry.get("registryId")
    sequence = registry.get("sequence")
    if not isinstance(registry_id, str) or not REGISTRY_ID.fullmatch(registry_id):
        raise RegistryToolError("registryId is missing or invalid")
    if (
        not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 1 <= sequence <= MAX_SEQUENCE
    ):
        raise RegistryToolError("sequence is missing or invalid")
    return registry_id, sequence


def adapter_folders(root: Union[str, Path] = ROOT) -> list[str]:
    base = Path(root)
    found = []
    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name in ADAPTER_METADATA_DIRS:
            continue
        if (child / "manifest.json").is_file():
            found.append(child.name)
    return found


def adapter_runtime_files(folder: Path) -> list[str]:
    """Every file the app should download, relative to the adapter folder."""

    files: list[str] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(folder)
        if relative.parts and relative.parts[0] == "assets":
            continue
        if str(relative) in SKIP_ADAPTER_FILES:
            continue
        if any(part.startswith(".") for part in relative.parts):
            continue
        files.append(relative.as_posix())
    return files


def safe_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if value.startswith("/") or "\\" in value or ":" in value:
        return False
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def iter_signature_candidates(root: Path) -> Iterable[Path]:
    return [root / "registry.json.minisig"]


def _ci_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if "\n" in text or "\r" in text:
        raise RegistryToolError("CI output values must be single-line")
    return text


def expected_registry_id(tier: str) -> Optional[str]:
    return TIER_REGISTRY_IDS.get(tier)


def ci_config(config: dict) -> dict[str, str]:
    signing = config.get("signing") or {}
    registry_id = config.get("registryId")
    if not isinstance(registry_id, str) or not REGISTRY_ID.fullmatch(registry_id):
        raise RegistryToolError("registry.config.json: invalid registryId")
    tier = config.get("tier")
    expected_id = expected_registry_id(tier)
    if expected_id is not None and registry_id != expected_id:
        raise RegistryToolError(
            f"{tier} registries must use registryId {expected_id!r}"
        )
    if tier == "third-party" and registry_id in RESERVED_REGISTRY_IDS:
        raise RegistryToolError(
            f"third-party registries may not use reserved registryId {registry_id!r}"
        )
    environment = signing.get("environment") or ""
    if tier in ("official", "community") and signing.get("enabled"):
        expected = f"registry-signing-{tier}"
        if environment != expected:
            raise RegistryToolError(
                f"{tier} registries must use the protected environment {expected}"
            )
    return {
        "enabled": _ci_value(bool(signing.get("enabled"))),
        "tier": _ci_value(tier),
        "environment": _ci_value(environment),
        "registry_id": registry_id,
        "key_file": _ci_value(signing.get("keyFile")),
        "signer_repository": _ci_value(signing.get("signerRepository")),
        "signer_commit": _ci_value(signing.get("signerCommit")),
        "require_signature": _ci_value(bool(config.get("requireSignature"))),
        "expires_days": _ci_value(signing.get("expiresInDays")),
    }


def command_format(args) -> int:
    paths = [Path(item) for item in args.paths]
    changed = 0
    for path in paths:
        value = load_json(path)
        expected = canonical_bytes(value)
        current = path.read_bytes()
        if current == expected:
            continue
        changed += 1
        if args.check:
            print(f"not canonical: {path}", file=sys.stderr)
        else:
            atomic_write(path, expected)
            print(f"formatted: {path}")
    if args.check and changed:
        return 1
    if not args.check:
        print(f"Formatted {changed} file(s).")
    return 0


def command_hash(args) -> int:
    for path in args.paths:
        print(f"{sha256_file(path)}  {path}")
    return 0


def command_ci_config(args) -> int:
    config = load_json(args.config)
    values = ci_config(config)
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as handle:
            for name, value in values.items():
                handle.write(f"{name}={value}\n")
    else:
        print(json.dumps(values, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Red Pen registry format helpers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fmt = subparsers.add_parser(
        "format", help="rewrite JSON files in deterministic format"
    )
    fmt.add_argument("--check", action="store_true")
    fmt.add_argument("paths", nargs="+")
    fmt.set_defaults(func=command_format)

    digest = subparsers.add_parser("hash", help="print SHA-256 digests")
    digest.add_argument("paths", nargs="+")
    digest.set_defaults(func=command_hash)

    ci = subparsers.add_parser("ci-config", help="emit signing settings for CI")
    ci.add_argument("--config", default="registry.config.json")
    ci.add_argument("--github-output")
    ci.set_defaults(func=command_ci_config)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except RegistryToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
