#!/usr/bin/env python3
"""Sign registry.json with minisign, or run a throwaway test-key dry run.

Production signing is normally performed by the pinned signer repository in a
protected GitHub environment. This script is the local/CI-safe reference
implementation and the test-key dry-run used by pull requests.

The password is read from MINISIGN_PASSWORD and fed to minisign through a
pseudo-terminal with echo disabled. minisign's PTY output is discarded because
some versions echo KDF or password material. The signature is verified against
the committed public key before it replaces the previous sidecar.
"""

from __future__ import annotations

import argparse
import os
import pty
import secrets
import select
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import termios
import time
from datetime import timedelta
from pathlib import Path
from typing import Optional, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import registry as registry_lib  # noqa: E402
import verify as verify_lib  # noqa: E402


class SigningError(ValueError):
    pass


def _password_bytes(password: str) -> bytes:
    if not password:
        raise SigningError("an empty minisign password is not allowed")
    if any(character in password for character in ("\n", "\r", "\x00")):
        raise SigningError("the minisign password contains a forbidden character")
    encoded = password.encode("utf-8")
    if len(encoded) > 1024:
        raise SigningError("the minisign password is too long")
    return encoded


def _safe_environment() -> dict[str, str]:
    keep = ("PATH", "HOME", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL", "TZ")
    return {name: os.environ[name] for name in keep if name in os.environ}


def _run_pty(command: Sequence[str], password: str, prompts: int, timeout: int = 300) -> None:
    if not hasattr(pty, "openpty"):  # pragma: no cover - Windows
        raise SigningError("password-based minisign signing needs a POSIX PTY")
    master, slave = pty.openpty()
    try:
        attributes = termios.tcgetattr(slave)
        attributes[3] &= ~(
            termios.ECHO | termios.ECHOE | termios.ECHOK | termios.ECHONL
        )
        termios.tcsetattr(slave, termios.TCSANOW, attributes)
        process = subprocess.Popen(
            list(command),
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
            start_new_session=True,
            env=_safe_environment(),
        )
    except BaseException:
        os.close(master)
        os.close(slave)
        raise
    os.close(slave)

    sent = 0
    pending = b""
    deadline = time.monotonic() + timeout
    try:
        while True:
            if process.poll() is not None:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _kill_group(process)
                raise SigningError(f"minisign timed out after {timeout}s")
            ready, _, _ = select.select([master], [], [], min(0.25, remaining))
            if not ready:
                continue
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            pending = (pending + chunk.lower())[-512:]
            if sent < prompts and (
                b"password" in pending or b"passphrase" in pending
            ):
                os.write(master, _password_bytes(password) + b"\n")
                sent += 1
                pending = b""
                time.sleep(0.05)
        code = process.wait(timeout=5)
    except BaseException:
        if process.poll() is None:
            _kill_group(process)
        raise
    finally:
        try:
            os.close(master)
        except OSError:
            pass
    if code != 0:
        raise SigningError(f"minisign exited with status {code}")
    if sent == 0:
        raise SigningError("minisign did not request a password")


def _kill_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            process.kill()
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:  # pragma: no cover
        pass


def generate_key(secret: Path, public: Path, password: str, *, force: bool = False) -> None:
    command = [registry_lib.find_minisign(), "-G", "-p", str(public), "-s", str(secret)]
    if force:
        command.insert(2, "-f")
    _run_pty(command, password, prompts=2)
    os.chmod(secret, 0o600)
    if not public.is_file():
        raise SigningError("minisign did not create the public key")


def sign_file(
    secret: Path,
    message: Path,
    signature: Path,
    trusted_comment: str,
    password: str,
) -> None:
    if (
        not trusted_comment
        or len(trusted_comment) > 1024
        or any(character in trusted_comment for character in ("\n", "\r", "\x00"))
    ):
        raise SigningError("invalid trusted comment")
    _run_pty(
        [
            registry_lib.find_minisign(),
            "-S",
            "-q",
            "-s",
            str(secret),
            "-m",
            str(message),
            "-x",
            str(signature),
            "-t",
            trusted_comment,
        ],
        password,
        prompts=1,
    )
    if not signature.is_file() or signature.stat().st_size == 0:
        raise SigningError("minisign did not write a signature")


def _inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(registry_lib.ROOT.resolve())
        return True
    except ValueError:
        return False


def sign_registry(
    registry_path: Path,
    signature_path: Path,
    secret_key_path: Path,
    public_key_path: Path,
    config_path: Path,
    password: str,
) -> dict:
    if _inside_repo(secret_key_path):
        raise SigningError("refusing to use a secret key stored inside the repository")
    if secret_key_path.is_symlink():
        raise SigningError("refusing to use a symlinked secret key")
    if secret_key_path.is_file() and stat.S_IMODE(secret_key_path.stat().st_mode) & 0o077:
        raise SigningError("secret key file must not be group/world accessible")
    registry = registry_lib.load_canonical(registry_path)
    config = registry_lib.load_json(config_path)
    if not isinstance(registry, dict) or not isinstance(config, dict):
        raise SigningError("registry and config must be JSON objects")
    registry_id, sequence = registry_lib.registry_identity(registry)
    if config.get("registryId") != registry_id:
        raise SigningError("registry.config.json registryId does not match registry.json")
    expires_at = registry_lib.parse_timestamp(registry.get("expiresAt"), "expiresAt")
    if expires_at <= registry_lib.utc_now():
        raise SigningError("registry has expired; prepare a new sequence first")
    comment = registry_lib.trusted_comment(registry_id, sequence)

    signature_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{signature_path.name}.", suffix=".tmp", dir=str(signature_path.parent)
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        sign_file(secret_key_path, registry_path, temporary, comment, password)
        result = verify_lib.verify(
            registry_path,
            temporary,
            public_key_path,
            config_path=config_path,
        )
        os.replace(temporary, signature_path)
        return result
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def test_key_dry_run(registry_path: Path, config_path: Path) -> dict:
    config = registry_lib.load_json(config_path)
    registry = registry_lib.load_json(registry_path)
    if not isinstance(config, dict) or not isinstance(registry, dict):
        raise SigningError("registry and config must be JSON objects")
    registry_id, sequence = registry_lib.registry_identity(registry)
    if config.get("registryId") != registry_id:
        raise SigningError("registry.config.json registryId does not match registry.json")
    signing = config.get("signing") or {}
    days = signing.get("expiresInDays", 180)
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 366:
        raise SigningError("signing.expiresInDays is invalid")
    now = registry_lib.utc_now()
    prepared = dict(registry)
    prepared["sequence"] = sequence + 1
    prepared["issuedAt"] = registry_lib.format_timestamp(now)
    prepared["expiresAt"] = registry_lib.format_timestamp(now + timedelta(days=days))

    password = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="redpen-sign-dry-run-") as directory:
        root = Path(directory)
        os.chmod(root, 0o700)
        secret = root / "test.key"
        public = root / "test.pub"
        message = root / "registry.test.json"
        signature = root / "registry.test.json.minisig"
        generate_key(secret, public, password, force=True)
        message.write_bytes(registry_lib.canonical_bytes(prepared))
        result = sign_registry(
            message, signature, secret, public, config_path, password
        )
        tampered = root / "registry.tampered.json"
        tampered.write_bytes(message.read_bytes() + b" ")
        tamper_rejected = False
        try:
            verify_lib.verify(tampered, signature, public, config_path=config_path)
        except Exception:
            tamper_rejected = True
        if not tamper_rejected:
            raise SigningError("a tampered registry still verified")
        return {
            "testKey": True,
            "registryId": result["registryId"],
            "sequence": result["sequence"],
            "keyId": result["keyId"],
            "fingerprint": result["fingerprint"],
            "registrySha256": result["registrySha256"],
            "signatureSha256": result["signatureSha256"],
            "tamperRejected": True,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sign a Red Pen registry.")
    parser.add_argument("--registry", default="registry.json")
    parser.add_argument("--sig", default="registry.json.minisig")
    parser.add_argument("--secret-key")
    parser.add_argument("--public-key")
    parser.add_argument("--config", default="registry.config.json")
    parser.add_argument("--password-env", default="MINISIGN_PASSWORD")
    parser.add_argument(
        "--test-key",
        action="store_true",
        help="generate a throwaway encrypted key and run the full round trip",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.test_key:
            result = test_key_dry_run(Path(args.registry), Path(args.config))
            print(
                f"Test-key dry run passed: {result['registryId']} "
                f"sequence {result['sequence']}, key {result['keyId']}, "
                "tamper rejected."
            )
            return 0
        if not args.secret_key or not args.public_key:
            print("error: --secret-key and --public-key are required", file=sys.stderr)
            return 2
        password = os.environ.get(args.password_env, "")
        if not password:
            print(f"error: {args.password_env} is empty or missing", file=sys.stderr)
            return 2
        result = sign_registry(
            Path(args.registry),
            Path(args.sig),
            Path(args.secret_key),
            Path(args.public_key),
            Path(args.config),
            password,
        )
        print(
            f"Signed {result['registryId']} sequence {result['sequence']} "
            f"with key {result['keyId']}."
        )
        return 0
    except (SigningError, registry_lib.RegistryToolError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
