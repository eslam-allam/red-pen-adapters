# Red Pen adapter registry

The official registry for Red Pen adapters. Every adapter is a folder with a
`manifest.json` and its code. `registry.json` is the master index that points
at those folders, in the same spirit as the Noctalia plugin registry.

The app downloads the listed files from the folder and runs them directly; no
ZIP packaging is needed. Language runtimes are installed by the app, not by
the adapter.

## Registry format

```json
{
  "schema": 5,
  "name": "Red Pen official adapter registry",
  "adapters": [
    {
      "id": "python",
      "name": "Python",
      "version": "2.2.0",
      "description": "Runs Python code and compares its output with the key.",
      "author": "Red Pen",
      "appliesTo": ["file", "question"],
      "output": { "kind": "diff", "label": "Program output" },
      "permissions": ["subprocess"],
      "runtimes": [
        {
          "tool": "python",
          "setting": "pythonVersion",
          "version": "3.12",
          "packages": { "setting": "packages", "installer": "pip" }
        }
      ],
      "folder": "python",
      "files": ["manifest.json", "adapter.lua"]
    }
  ]
}
```

Each folder contains `manifest.json` and the adapter's Lua script. The registry
entry lists both files, and the app resolves them relative to `registry.json`.

The entry mirrors the manifest. The app refuses an install whose manifest asks
for a permission, folder grant, folder picker or runtime the entry did not
list, so keep the two files in step.

## Adapter scripts

Every adapter is a Lua script named `adapter.lua`. The app runs it in its
embedded Lua runtime; there is no command line, process runtime or built-in
handler in a manifest.

The script returns one result table through `app.result`:

```lua
app.result({
  score = 2.5,
  comment = "Student-facing comment",
  rationale = "Grader-only explanation",
  text = "Preview text shown when the attachment is opened",
  output = {
    kind = "diff",
    title = "Program output",
    expected = expected,
    actual = output.stdout,
  },
})
```

The manifest declares what output the script may return:

```json
"output": { "kind": "diff", "label": "Program output" }
```

`kind` is one of `none`, `text`, `table`, `diff`, `image` or `json`. The app
rejects any other kind, and rejects output from an adapter that declares
`none`. The grading panel shows the output in an overlay; tables highlight
mismatched rows and cells, and diffs compare expected and actual line by
line. See `lua/red-pen-api.lua` for the full Lua API and the output shapes.

## Permissions

Adapters declare only what they need outside their sandbox:

| Permission | Meaning |
| --- | --- |
| `network` | Make network requests from the adapter or the student's program. |
| `subprocess` | Start another program. |
| `environment` | Read the parent environment. |

The official adapters declare only `subprocess`. Add `network` back only when
the student's own program needs to make network requests; runtime and package
downloads are handled by the app, not by the adapter.

### Windows registry

An adapter that needs a per-user registry key declares it in the manifest:

```json
"registry": ["HKCU\\Software\\JavaSoft\\Prefs"]
```

The key must be under `HKCU` or `HKLM`. The app creates a missing `HKCU` key
and opens it to the adapter's AppContainer. Grants are per key, so a program
that writes nested keys (Java preferences, for example) must list each one.
Other platforms ignore the list.
setup never need it.

The submitted file, the adapter folder and the adapter temp folder need no
permission. Other folders are declared with `directories`:

```json
"directories": ["user-home:r", "user-documents:r", "/opt/course-data:rw"]
```

Each entry is `<folder>[:r|:ro|:rw]`; the folder may be an absolute path or one
of `user-home`, `user-documents`, `user-downloads`, `user-desktop`,
`user-pictures`, `user-videos`, `user-audio`, `temp`.

An adapter that needs a folder the instructor chooses declares a picker:

```json
"directoryPicker": { "mode": "rw", "label": "Test-case folder" }
```

The folder is chosen in the Key step (question adapters) or Settings (file
adapters) and passed to the adapter as `grantedDirectory`.

## Runtimes and packages

Language runtimes are declared in the manifest, and the app installs them with
mise using its own network access. The adapter therefore does not declare
`network` just to download a runtime.

```json
"runtimes": [
  { "tool": "python", "setting": "pythonVersion", "version": "3.12" }
]
```

- `tool` is the mise tool (`python`, `node`, `gcc`, `go`, `java`, …).
- `setting` names a settings field that selects the version. When it is empty,
  `version` is used. Changing the setting makes the app install the new
  version before the next run; no `network` permission is involved.
- `version` is the version used when the setting is empty.

For a runtime with packages, the app creates a managed environment (a Python
venv for `pip`) and installs the packages named in the settings:

```json
"packages": { "setting": "packages", "installer": "pip" }
```

`request.runtime.version` is the concrete installed version, not `latest`.
Use it when calling `run_runtime`; the sandbox has no network for mise to
resolve `latest`:

```lua
local version = (request.runtime and request.runtime.version)
  or settings.runtimeVersion
  or "latest"
```

The environment is passed to the adapter as `request.runtime`:

```lua
local runner = request.runtime and request.runtime.program
if runner then
  output = app.run_command(runner, { request.filePath }, "")
else
  output = app.run_runtime("python", request.runtime.version, "python", { request.filePath }, "")
end
```

The app installs only wheels (`pip --only-binary=:all:`) and refuses package
lines that look like options, URLs or paths. Package installation runs outside
the adapter sandbox, before the student's code starts.

## Logisim

The Logisim adapter runs `logisim-evolution -tty table <circuit>` (or
`logisim`) and compares the generated truth table with the `table` key input.
Set the `programPath` setting to the Logisim executable, or put
`logisim-evolution`/`logisim` on `PATH`. It uses no runtime download.

Name the key table's input and output columns after the circuit's pins. When
the key has a `# red-pen header:` line, the adapter matches the generated
table's columns by name, so the same circuit is accepted even if its pins are
listed in a different order. Without a header the columns are compared by
position. The adapter returns a `table` output that shows the circuit's table
and highlights every row or cell that differs from the key.

## Language pack

The language adapters run a submitted file or a question answer with the
language's runtime and compare the printed output with the `expected` key
field. They declare their supported extensions and work on both files and
questions.

Included: JavaScript, TypeScript, Ruby, PHP, Go, Rust, C, C++, Java, Kotlin,
C#, F#, Swift, Lua, R, Julia, Haskell, Elixir, Erlang, Dart, Scala, Perl,
Bash, PowerShell, and Python.

Every language adapter declares its mise runtime in `runtimes`; the app
downloads it. No adapter declares `network`. TypeScript runs through Bun's
built-in TypeScript/TSX support, so it does not download `tsx` at run time.

## Lua editor support

The repository's `.luarc.json` configures LuaLS for adapter authors:

- `lua/red-pen-api.lua` defines `request`, `manifest`, `app`, the process result
  type, `app.result`, and the output shapes an adapter may return.
- `runtime.builtin` disables `io`, `os`, `package` and `debug`, so the editor
  reports those libraries as unavailable. It also documents that `load`,
  `loadfile` and `dofile` are absent at runtime.
- `workspace.library` points to `lua`, so completion works when the repository
  is opened as a workspace.

Adapters get a per-run temp folder from `app.temp_dir()` and can read/write
inside their sandbox without a permission. Use `app.read_file`,
`app.write_file`, `app.run_runtime` and `app.run_command`; the standard
libraries that would bypass the sandbox are not present.

## JSON schemas

Two JSON Schemas describe the registry and adapter manifests:

- `schemas/registry.schema.json` — the root `registry.json`
- `schemas/manifest.schema.json` — each adapter folder's `manifest.json`

Every JSON file includes a `$schema` reference, so editors with JSON language
support get completion, hover docs, and error squiggles while writing manifests
or registry entries. `.vscode/settings.json` wires the schemas to the matching
file patterns.

The schemas document:

- permissions, targets, folder grants, folder pickers, and runtimes
- the declared `output` kind and the shapes it may return
- Windows registry keys an adapter declares with `registry`
- the operating system passed to adapters as `request.os`
- adapter key and settings field types
- truth-table column sections, row sections, and safe formulas such as
  `2 ^ inputs`
- per-section `fill: "binary"` or `fill: "none"` to choose whether the table
  editor prefills that section, and optional `names` for fixed headings
- registry file entries, including their optional SHA-256 checksums

Run local validation before publishing:

```sh
python -m pip install jsonschema
python scripts/validate.py
```

The script validates both schemas and checks cross-file consistency: folder
contents, manifest/registry version and id agreement, runtime settings, and
formula variables. The same validation runs in GitHub Actions on pushes and
pull requests.
