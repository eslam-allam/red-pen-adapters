#!/usr/bin/env python3
"""Logisim adapter for Red Pen.

Reads one JSON request on stdin and writes one JSON reply on stdout. The key
truth table arrives in context.values.table, and the optional executable
override in settings.logisimBin.
"""

import json
import os
import shutil
import subprocess
import sys


def logisim_binary(settings: dict) -> str | None:
    configured = (settings.get("logisimBin") or "").strip()
    if configured:
        return configured
    configured = (os.environ.get("LOGISIM_BIN") or "").strip()
    if configured:
        return configured
    for candidate in ("logisim-evolution", "logisim"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def generated_table(path: str, settings: dict) -> str:
    binary = logisim_binary(settings)
    if not binary:
        raise RuntimeError(
            "Logisim was not found. Set the Logisim executable in the adapter settings or LOGISIM_BIN."
        )
    result = subprocess.run(
        [binary, "-tty", "table", path],
        capture_output=True,
        text=True,
        timeout=50,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0 and not output.strip():
        raise RuntimeError(f"Logisim exited with {result.returncode}.")
    return output


def rows(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        line = " ".join(raw.strip().split())
        if not line:
            continue
        if "truth table" in line.lower():
            continue
        if set(line) <= {"-", "|", "+", "=", " "}:
            continue
        out.append(line.replace("|", " ").strip().upper())
    return out


def main() -> int:
    request = json.load(sys.stdin)
    path = request.get("filePath", "")
    mode = request.get("mode", "preview")
    context = request.get("context") or {}
    settings = request.get("settings") or {}
    try:
        table = generated_table(path, settings)
    except Exception as error:  # noqa: BLE001 - report the tool error to the app
        json.dump({"error": str(error)}, sys.stdout)
        return 0

    if mode != "grade":
        json.dump({"text": table}, sys.stdout)
        return 0

    values = context.get("values") or {}
    expected = (values.get("table") or context.get("expected") or "").strip()
    maximum = float(context.get("maxPoints") or 0)
    if not expected:
        json.dump(
            {
                "error": "This adapter question has no key truth table.",
                "text": table,
            },
            sys.stdout,
        )
        return 0

    expected_rows = rows(expected)
    actual_rows = rows(table)
    if not expected_rows:
        json.dump({"error": "The key truth table is empty."}, sys.stdout)
        return 0

    matched = sum(1 for row in expected_rows if row in actual_rows)
    score = maximum * matched / len(expected_rows)
    missing = [row for row in expected_rows if row not in actual_rows]
    extra = [row for row in actual_rows if row not in expected_rows]
    if matched == len(expected_rows):
        comment = "The generated truth table matches the key."
        rationale = "Every expected row is present."
    else:
        pieces = [f"{matched} of {len(expected_rows)} expected rows match."]
        if missing:
            pieces.append("Missing: " + "; ".join(missing[:4]))
        if extra:
            pieces.append("Extra: " + "; ".join(extra[:4]))
        comment = "The generated truth table differs from the key."
        rationale = " ".join(pieces)

    json.dump(
        {
            "score": round(score, 4),
            "comment": comment,
            "rationale": rationale,
            "text": table,
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
