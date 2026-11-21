#!/usr/bin/env python3
"""Verify the exact bytes of registry.json against its detached signature."""

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


def verify(
    registry_path: Path,
    signature_path: Path,
    public_key_path: Path,
    *,
    config_path: Optional[Path] = None,
    allow_expired: bool = False,
    minisign_bin: Optional[str] = None,
) -> dict:
    registry = registry_lib.load_canonical(registry_path)
    if not isinstance(registry, dict):
        raise registry_lib.RegistryToolError("registry.json must be an object")
    registry_id, sequence = registry_lib.registry_identity(registry)
    if config_path is not None:
        config = registry_lib.load_json(config_path)
        if not isinstance(config, dict):
            raise registry_lib.RegistryToolError("registry.config.json must be an object")
        if config.get("registryId") != registry_id:
            raise registry_lib.RegistryToolError(
                "registry.json registryId does not match registry.config.json"
            )
    issued_at = registry_lib.parse_timestamp(registry.get("issuedAt"), "issuedAt")
    expires_at = registry_lib.parse_timestamp(registry.get("expiresAt"), "expiresAt")
    if expires_at <= issued_at:
        raise registry_lib.RegistryToolError("expiresAt must be later than issuedAt")
    if not allow_expired and expires_at <= registry_lib.utc_now():
        raise registry_lib.RegistryToolError("registry signature has expired")
    key = registry_lib.verify_signature(
        registry_path,
        signature_path,
        public_key_path,
        minisign_bin=minisign_bin,
    )
    _, comment = registry_lib.read_signature(signature_path)
    return {
        "valid": True,
        "registryId": registry_id,
        "sequence": sequence,
        "issuedAt": registry.get("issuedAt"),
        "expiresAt": registry.get("expiresAt"),
        "registrySha256": registry_lib.sha256_file(registry_path),
        "signatureSha256": registry_lib.sha256_file(signature_path),
        "keyId": key.key_id,
        "fingerprint": key.fingerprint,
        "trustedComment": comment,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a signed registry.")
    parser.add_argument("--registry", default="registry.json")
    parser.add_argument("--sig", default="registry.json.minisig")
    parser.add_argument("--public-key")
    parser.add_argument("--config", default="registry.config.json")
    parser.add_argument("--allow-expired", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    public_key = args.public_key
    if not public_key and args.config and Path(args.config).is_file():
        config = registry_lib.load_json(args.config)
        public_key = (config.get("signing") or {}).get("keyFile")
    if not public_key:
        print("error: a public key is required", file=sys.stderr)
        return 2
    try:
        result = verify(
            Path(args.registry),
            Path(args.sig),
            Path(public_key),
            config_path=Path(args.config) if args.config else None,
            allow_expired=args.allow_expired,
        )
    except (registry_lib.RegistryToolError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"Verified {result['registryId']} sequence {result['sequence']} "
            f"with key {result['keyId']}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
