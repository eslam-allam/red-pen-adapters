#!/usr/bin/env python3
"""Run a student's program for one language adapter and compare its output."""

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
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).strip()


def manifest_of_self() -> dict:
    try:
        return json.loads((Path(__file__).resolve().parent / "manifest.json").read_text())
    except Exception:
        return {}


def split_packages(value: object) -> list[str]:
    if isinstance(value, list):
        raw = [str(item) for item in value]
    else:
        raw = str(value or "").replace(",", "\n").split("\n")
    return [item.strip() for item in raw if item.strip()]


def uv_beside_self() -> str:
    local = Path(__file__).resolve().parent / ("uv.exe" if os.name == "nt" else "uv")
    if local.is_file():
        return str(local)
    return shutil.which("uv") or "uv"


def build_command(language: str, program: str | None, source: Path, work: Path) -> list[str]:
    chosen = program or {
        "python": sys.executable,
        "javascript": "node",
        "typescript": "npx",
        "ruby": "ruby",
        "php": "php",
        "go": "go",
        "rust": "rustc",
        "c": "cc",
        "cpp": "c++",
        "java": "java",
        "kotlin": "kotlinc",
        "csharp": "dotnet",
        "fsharp": "dotnet",
        "swift": "swift",
        "lua": "lua",
        "r": "Rscript",
        "julia": "julia",
        "haskell": "runghc",
        "elixir": "elixir",
        "erlang": "escript",
        "dart": "dart",
        "scala": "scala",
        "perl": "perl",
        "bash": "bash",
        "powershell": "pwsh",
    }.get(language, "")
    if not chosen:
        raise RuntimeError(f"No runtime is configured for {language}.")
    if language == "typescript":
        return [chosen, "--yes", "tsx", str(source)]
    if language == "rust":
        out = work / ("program.exe" if os.name == "nt" else "program")
        return [chosen, str(source), "-o", str(out)]
    if language in {"c", "cpp"}:
        out = work / ("program.exe" if os.name == "nt" else "program")
        return [chosen, str(source), "-o", str(out)]
    if language == "go":
        return [chosen, "run", str(source)]
    if language == "java":
        return [chosen, str(source)]
    if language == "kotlin":
        return [chosen, "-script", str(source)]
    if language == "csharp":
        return [chosen, "script", str(source)]
    if language == "fsharp":
        return [chosen, "fsi", str(source)]
    if language == "dart":
        return [chosen, "run", str(source)]
    if language == "powershell":
        return [chosen, "-NoLogo", "-NonInteractive", "-File", str(source)]
    return [chosen, str(source)]


def compile_step(language: str, program: str | None, source: Path, work: Path) -> tuple[list[str] | None, Path | None]:
    if language not in {"rust", "c", "cpp"}:
        return None, None
    chosen = program or ("rustc" if language == "rust" else "cc" if language == "c" else "c++")
    out = work / ("program.exe" if os.name == "nt" else "program")
    return [chosen, str(source), "-o", str(out)], out


def main() -> int:
    try:
        request = json.load(sys.stdin)
    except Exception as error:
        print(json.dumps({"error": f"The request was not valid JSON: {error}"}))
        return 0
    manifest = manifest_of_self()
    language = str(manifest.get("language") or "python")
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
    program = str(settings.get("programPath") or "").strip() or None
    try:
        timeout = max(1.0, min(300.0, float(settings.get("timeout") or 15)))
    except (TypeError, ValueError):
        timeout = 15.0
    work = Path(tempfile.mkdtemp(prefix=f"red-pen-{language}-"))
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env.setdefault("GOCACHE", str(work / "gocache"))
        env.setdefault("GOPATH", str(work / "gopath"))
        env.setdefault("CARGO_HOME", str(work / "cargo"))
        env.setdefault("HOME", str(work))
        started = time.monotonic()
        compile_command, executable = compile_step(language, program, source, work)
        if compile_command:
            compiled = subprocess.run(
                compile_command, cwd=str(work), env=env, capture_output=True, text=True,
                timeout=timeout, check=False,
            )
            if compiled.returncode != 0:
                print(json.dumps({
                    "score": 0.0,
                    "comment": "The program did not compile.\n\n" + normalise(compiled.stderr)[-4000:],
                    "rationale": "Compilation failed.",
                    "text": compiled.stdout or "",
                }))
                return 0
            command = [str(executable)]
        else:
            command = build_command(language, program, source, work)
        try:
            result = subprocess.run(
                command, cwd=str(work), env=env, capture_output=True, text=True,
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            print(json.dumps({
                "score": 0.0,
                "comment": f"The program did not finish within {timeout:g} seconds.",
                "rationale": "Execution timed out.",
                "text": "",
            }))
            return 0
        elapsed = time.monotonic() - started
        stdout = result.stdout or ""
        stderr = normalise(result.stderr or "")[-4000:]
        if result.returncode != 0:
            comment = "The program stopped with an error."
            if stderr:
                comment += "\n\n" + stderr
            print(json.dumps({
                "score": 0.0, "comment": comment,
                "rationale": f"The program exited with code {result.returncode}.",
                "text": stdout,
            }))
            return 0
        if mode == "preview":
            text = stdout
            if stderr:
                text += "\n\n[stderr]\n" + stderr
            print(json.dumps({"text": text, "rationale": f"Ran in {elapsed:.2f}s."}))
            return 0
        if not expected.strip():
            print(json.dumps({
                "score": 0.0,
                "comment": "The key has no expected output to compare with.",
                "rationale": "No expected output.",
                "text": stdout,
            }))
            return 0
        same = normalise(stdout) == normalise(expected)
        print(json.dumps({
            "score": max_points if same else 0.0,
            "comment": "The output matches the expected answer." if same else "The output does not match the expected answer.",
            "rationale": f"Output {'matched' if same else 'differed'} after {elapsed:.2f}s.",
            "text": stdout,
        }))
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
