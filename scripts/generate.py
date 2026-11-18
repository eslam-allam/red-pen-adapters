#!/usr/bin/env python3
"""Render the language adapters from one template.

Every adapter is self-contained: the sandbox has no require, load, loadfile or
dofile, so the shared logic cannot live in a single file at runtime. This
script keeps the source in one place and writes one adapter.lua per language
folder. Python and Logisim are hand-written and listed under "manual".

Usage:
  python scripts/generate.py           # write the adapter.lua files
  python scripts/generate.py --check   # fail if any file is out of date
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "scripts" / "languages.json"
TEMPLATE = ROOT / "scripts" / "templates" / "language_adapter.lua"


def lua_string(value: str) -> str:
    return json.dumps(value)


def args_literal(args: list[str]) -> str:
    rendered = ["file" if arg == "{file}" else lua_string(arg) for arg in args]
    return "{ " + ", ".join(rendered) + " }"


def run_block(entry: dict) -> str:
    if entry["kind"] == "compiled":
        return "\n".join(
            [
                'local binary = app.temp_dir() .. "/program"',
                'if app.temp_dir():match("\\\\$") then binary = binary .. ".exe" end',
                f'local build = run({lua_string(entry["compiler"])}, {{ file, "-o", binary }})',
                "if build.code ~= 0 then",
                '  fail("The program did not compile.\\n\\n" .. (build.stderr or ""), build.stdout)',
                "  return",
                "end",
                "local args = {}",
                'if input_file ~= "" then args[#args + 1] = input_file end',
                'local output = app.run_command(binary, args, "")',
            ]
        )
    return "\n".join(
        [
            f"local args = {args_literal(entry['args'])}",
            'if input_file ~= "" then args[#args + 1] = input_file end',
            f"local output = run({lua_string(entry['program'])}, args)",
        ]
    )


def render(template: str, entry: dict) -> str:
    return template.replace("{{RUN}}", run_block(entry))


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    template = TEMPLATE.read_text(encoding="utf-8")
    check = "--check" in sys.argv[1:]
    generated = config["generated"]
    stale: list[Path] = []
    written = 0

    for entry in generated:
        target = ROOT / entry["id"] / "adapter.lua"
        rendered = render(template, entry)
        existing = target.read_text(encoding="utf-8") if target.is_file() else None
        if existing == rendered:
            continue
        if check:
            stale.append(target)
        else:
            target.write_text(rendered, encoding="utf-8", newline="\n")
            written += 1

    if check:
        if stale:
            for path in stale:
                print(f"out of date: {path.relative_to(ROOT)}", file=sys.stderr)
            print("Run python scripts/generate.py to update them.", file=sys.stderr)
            return 1
        print(f"Generated adapters match the template ({len(generated)} files).")
        return 0

    print(
        f"Wrote {written} adapter(s); "
        f"{len(generated) - written} already up to date."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
