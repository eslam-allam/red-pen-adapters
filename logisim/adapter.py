#!/usr/bin/env python3
"""Run Logisim's truth-table mode and compare it with the key table."""

from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path


def rows(text: str) -> list[str]:
    out = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = " ".join(raw.replace("|", " ").split())
        if not line or "truth table" in line.lower():
            continue
        if all(ch in "-|+= " for ch in line):
            continue
        out.append(line.upper())
    return out


def main() -> int:
    request = json.load(sys.stdin)
    source = Path(str(request.get("filePath") or ""))
    if not source.is_file():
        print(json.dumps({"error": "The circuit file could not be found."}))
        return 0
    settings = request.get("settings") or {}
    context = request.get("context") or {}
    values = context.get("values") or {}
    expected = str(values.get("table") or context.get("expected") or "")
    max_points = float(context.get("maxPoints") or 0)
    configured = str(settings.get("programPath") or "").strip()
    binary = configured or os.environ.get("LOGISIM_BIN") or shutil.which("logisim-evolution") or shutil.which("logisim")
    if not binary:
        print(json.dumps({"error": "Logisim was not found. Set the Logisim executable in the adapter settings."}))
        return 0
    try:
        timeout = max(1.0, min(300.0, float(settings.get("timeout") or 20)))
    except (TypeError, ValueError):
        timeout = 20.0
    try:
        result = subprocess.run(
            [binary, "-tty", "table", str(source)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({"error": "Logisim did not finish in time."}))
        return 0
    except OSError as error:
        print(json.dumps({"error": f"Logisim could not be started: {error}"}))
        return 0
    table = result.stdout or ""
    if result.returncode != 0:
        print(json.dumps({"error": (result.stderr or "Logisim failed.")[-4000:], "text": table}))
        return 0
    if str(request.get("mode")) == "preview":
        print(json.dumps({"text": table}))
        return 0
    actual = rows(table)
    wanted = rows(expected)
    same = actual == wanted
    print(json.dumps({
        "score": max_points if same else 0.0,
        "comment": "The generated truth table matches the key." if same else "The generated truth table differs from the key.",
        "rationale": "Every truth-table row matched." if same else "One or more truth-table rows differed.",
        "text": table,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
