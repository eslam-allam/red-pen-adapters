# Red Pen adapter registry

The official registry for Red Pen adapters. Every adapter is a folder with a
`manifest.json` and its code. `registry.json` is the master index that points
at those folders, in the same spirit as the Noctalia plugin registry.

The app downloads the listed files from the folder and runs them directly; no
ZIP packaging is needed. Adapters run on uv, which the app downloads on first
install, so the adapter itself needs no user-installed interpreter.

## Registry format

```json
{
  "schema": 2,
  "name": "Red Pen official adapter registry",
  "adapters": [
    {
      "id": "logisim",
      "name": "Logisim",
      "version": "2.0.0",
      "description": "…",
      "author": "Red Pen",
      "appliesTo": ["file", "question"],
      "permissions": ["files:read", "subprocess"],
      "folder": "logisim",
      "files": ["manifest.json", "adapter.py"]
    }
  ]
}
```

Each folder contains `manifest.json` and the adapter's program. The registry
entry lists both files, and the app resolves them relative to `registry.json`.

## Logisim

The Logisim adapter is a normal adapter folder now. It runs `logisim-evolution -tty table <circuit>` (or `logisim`) and
compares the generated truth table with the `table` key input. Set the
`programPath` setting to the Logisim executable, or set `LOGISIM_BIN`, or put
`logisim-evolution`/`logisim` on `PATH`. No Python or other interpreter is
required.


## Python (uv)

The Python adapter runs code supplied as a `.py` attachment or as the answer
to a question. It compares the program's printed output with the `expected`
key field. Choose the Python version and any packages in the adapter settings.

The adapter package asks the app to download the `uv` launcher into its own
folder on first install (`bootstrap.uv`). uv then downloads the requested
Python version on first use and keeps it in its cache. The adapter declares
`network` for that download and `subprocess` for running the student's code.

## Language pack

The language adapters run a submitted file or a question answer with the
language's runtime and compare the printed output with the `expected` key
field. They declare their supported extensions and work on both files and
questions.

Included: JavaScript, TypeScript, Ruby, PHP, Go, Rust, C, C++, Java, Kotlin,
C#, F#, Swift, Lua, R, Julia, Haskell, Elixir, Erlang, Dart, Scala, Perl,
Bash, and PowerShell. Python has its own uv adapter above.

Each adapter folder ships a small Python runner and asks the app to download
uv on first install. The runner then starts the target language. Set
`programPath` if the target runtime is not on PATH.

## Runtime paths

Language adapters do not download or bundle the language runtime. Each one
declares a `Runtime executable` setting, and an empty value means the runtime
is found on `PATH`. Python and Logisim keep using uv, which the app downloads
into their adapter folder on first install.

## Runtime versions

Language adapters download mise, which installs the requested language version
from the adapter's `Runtime version` setting. The runtime is cached by mise and
used only for that adapter. Python and Logisim still use uv for their launcher.


## Lua editor support

`lua/red-pen-api.lua` is a LuaLS `---@meta` stub for the adapter host API.
Editors using LuaLS get completion and type checking for `app`, `request`,
`manifest`, and `result` when the repository is opened as a workspace.
