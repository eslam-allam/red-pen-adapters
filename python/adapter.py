#!/usr/bin/env python3
"""Run a student's Python program and compare its output with the key.

The app starts this file with uv. uv supplies uv itself in the adapter folder,
so the same launcher works on Linux, macOS, and Windows.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def normalise(text: str) -> str:
    """Compare visible output, not trailing blank lines or CRLF noise."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).strip()


def uv_path() -> str:
    local = Path(__file__).resolve().parent / ("uv.exe" if os.name == "nt" else "uv")
    if local.is_file():
        return str(local)
    found = shutil.which("uv")
    return found or "uv"


def split_packages(value: object) -> list[str]:
    if isinstance(value, list):
        raw = [str(item) for item in value]
    else:
        raw = str(value or "").replace(",", "\n").split("\n")
    return [item.strip() for item in raw if item.strip()]


def main() -> int:
    try:
        request = json.load(sys.stdin)
    except Exception as error:  # noqa: BLE001 - the reply must always be JSON
        print(json.dumps({"error": f"The request was not valid JSON: {error}"}))
        return 0

    source = Path(str(request.get("filePath") or ""))
    if not source.is_file():
        print(json.dumps({"error": "The submitted code file could not be found."}))
        return 0

    settings = request.get("settings") or {}
    context = request.get("context") or {}
    values = context.get("values") or {}
    mode = str(request.get("mode") or "grade")
    expected = str(values.get("expected") or context.get("expected") or "")
    max_points = float(context.get("maxPoints") or 0)
    version = str(settings.get("pythonVersion") or "3.12").strip() or "3.12"
    packages = split_packages(settings.get("packages"))
    try:
        timeout = max(1.0, min(300.0, float(settings.get("timeout") or 10)))
    except (TypeError, ValueError):
        timeout = 10.0

    work = Path(tempfile.mkdtemp(prefix="red-pen-python-"))
    try:
        env = os.environ.copy()
        env["UV_CACHE_DIR"] = str(work / "cache")
        env["UV_PYTHON_INSTALL_DIR"] = str(work / "python")
        env["UV_NO_PROGRESS"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        command = [uv_path(), "run", "--no-project", "--python", version]
        for package in packages:
            command.extend(["--with", package])
        command.append(str(source))
        started = time.monotonic()
        try:
            result = subprocess.run(
                command,
                cwd=str(work),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            reply = {
                "score": 0.0,
                "comment": f"The program did not finish within {timeout:g} seconds.",
                "rationale": "Execution timed out.",
                "text": "",
            }
            print(json.dumps(reply))
            return 0
        elapsed = time.monotonic() - started
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        output = normalise(stdout)
        error_tail = normalise(stderr)
        if error_tail:
            error_tail = error_tail[-4000:]

        if result.returncode != 0:
            comment = "The program stopped with an error."
            if error_tail:
                comment = f"{comment}\n\n{error_tail}"
            reply = {
                "score": 0.0,
                "comment": comment,
                "rationale": f"The program exited with code {result.returncode}.",
                "text": stdout,
            }
            print(json.dumps(reply))
            return 0

        if mode == "preview":
            reply = {
                "text": stdout,
                "rationale": f"Ran in {elapsed:.2f}s.",
            }
            if error_tail:
                reply["text"] = f"{stdout}\n\n[stderr]\n{error_tail}"
            print(json.dumps(reply))
            return 0

        if not expected.strip():
            reply = {
                "score": 0.0,
                "comment": "The key has no expected output to compare with.",
                "rationale": "No expected output.",
                "text": stdout,
            }
            print(json.dumps(reply))
            return 0

        wanted = normalise(expected)
        same = output == wanted
        score = max_points if same else 0.0
        if same:
            comment = "The output matches the expected answer."
            rationale = f"Output matched after {elapsed:.2f}s."
        else:
            comment = "The output does not match the expected answer."
            rationale = "Printed output differed from the key."
        reply = {
            "score": score,
            "comment": comment,
            "rationale": rationale,
            "text": stdout,
        }
        print(json.dumps(reply))
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
