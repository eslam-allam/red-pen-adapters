# Registry format (schema 7, manifest 5, API 2)

A registry is a folder of adapters plus one signed index. The app downloads
`registry.json`, verifies its signature, then downloads only the files the
signed index lists and checks their SHA-256 digests.

## Layout

```
registry.json
registry.json.minisig        created by the signing workflow
registry.config.json
schemas/
  manifest.schema.json       copied from the app contract
  registry.schema.json       copied from the app contract
  mirror-fields.json         copied from the app contract
  source.json                app commit and SHA-256 of each copied file
lua/
  red-pen-api.lua            copied from the app contract (documentation)
keys/
<adapter-id>/
  manifest.json
  adapter.lua
  README.md
  assets/                    optional, referenced by README only
```

Official adapter folders publish exactly `manifest.json` and `adapter.lua`.
`scripts/update.py` lists both with their SHA-256 digests. `README.md` and
`assets/**` are fetched for display only, and other files such as
`lua/red-pen-api.lua` are documentation for adapter authors and are not
installed. Keep secrets, tests, and build output out of adapter folders.

Do not edit the copied contract files by hand. A schema or API change belongs
in the app contract first, then `schemas/source.json` is refreshed with the new
app commit and the new digests.

## registry.json

```json
{
  "$schema": "./schemas/registry.schema.json",
  "schema": 7,
  "kind": "red-pen-adapters",
  "registryId": "red-pen-official",
  "publisher": "Red Pen",
  "sequence": 2,
  "issuedAt": "2026-11-20T21:00:00Z",
  "expiresAt": "2027-05-19T21:00:00Z",
  "adapters": []
}
```

| Field | Rules |
| --- | --- |
| `schema` | Exactly `7`. |
| `kind` | Exactly `red-pen-adapters`. |
| `registryId` | Globally unique lowercase slug, `^[a-z0-9][a-z0-9._-]{0,127}$`, no slashes. Official is `red-pen-official`; community is `red-pen-community`; third-party registries may not use those reserved ids. Must match `registry.config.json` and the signature's trusted comment. |
| `publisher` | Non-empty display-name string, at most 256 characters, no control characters. The app parses this as a string, not an object. |
| `sequence` | Integer `>= 1`, strictly increasing. The workflow tags `registry-v<sequence>`. |
| `issuedAt` | RFC 3339 UTC, seconds precision, `YYYY-MM-DDTHH:MM:SSZ`. |
| `expiresAt` | UTC, later than `issuedAt`; at most 366 days later. Verification refuses an expired registry. |
| `adapters` | Array of entries. An empty array is valid and installs nothing. |

There is no root `name`, `description`, or `homepage` in schema 7. Use
`publisher` for the human-readable publisher; a legacy document that still has
a root `name` is rejected.

`sequence`, `issuedAt`, and `expiresAt` are owned by the signer. Do not bump
them by hand in a pull request; the signing workflow sets them.

## Adapter entry

```json
{
  "apiVersion": 2,
  "id": "python",
  "name": "Python",
  "version": "2.5.0",
  "description": "Runs Python code.",
  "author": "Red Pen",
  "appliesTo": ["file", "question"],
  "permissions": ["subprocess"],
  "extensions": ["py"],
  "settings": [{ "key": "pythonVersion", "label": "Python version", "type": "select", "options": ["3.13"], "default": "3.13" }],
  "keyInput": [{ "key": "expected", "label": "Expected output", "type": "textarea" }],
  "questionInput": [{ "key": "inputFile", "label": "Input file", "type": "path" }],
  "output": { "kinds": ["diff"], "label": "Program output" },
  "runtimes": [{ "tool": "python", "setting": "pythonVersion", "version": "3.13" }],
  "bootstrap": { "mise": "latest" },
  "folder": "python",
  "files": [
    { "path": "manifest.json", "sha256": "..." },
    { "path": "adapter.lua", "sha256": "..." }
  ],
  "readmeUrl": "https://raw.githubusercontent.com/eslam-allam/red-pen-adapters/main/python/README.md"
}
```

`apiVersion` is exactly `2`. Every entry also mirrors the manifest fields listed
in `schemas/mirror-fields.json`:

`name`, `description`, `author`, `icon`, `homepage`, `extensions`, `appliesTo`,
`permissions`, `registry`, `runtimes`, `bootstrap`, `settings`, `keyInput`,
`questionInput`, `output`, `directories`, and `directoryPicker`.

`scripts/update.py` copies them and `scripts/validate.py` refuses a mismatch.
Never edit only one side.

`files` must be objects with `path` and lowercase `sha256`. Bare file strings
are rejected because the signed index has to authenticate every byte. The
official validator requires `sha256` for every file. Paths are relative, use
`/`, and may not contain `..`, an absolute path, a backslash, a colon, or
control characters. `manifest.json` and `adapter.lua` are required.

`readmeUrl` must be
`<readmeBaseUrl>/<adapter-id>/README.md`. The README may reference
`assets/...`; assets are fetched for display but are not installed.

## manifest.json

`schemas/manifest.schema.json` is the app-facing manifest schema. The app
supports manifest `schema: 5` and API `apiVersion: 2`; both are required.

`output` is required and declares `kinds` from `none`, `text`, `table`,
`tableDiff`, `diff`, `image`, and `json`. `settings` and `keyInput` are
required arrays; `questionInput` is optional. All fields use the v2 field types
and shapes.

Permissions are limited to `network` and `subprocess`. Legacy values such as
`environment`, `files:read`, `files:write`, and `directories` are rejected. Use
`directories`/`directoryPicker` for folder grants instead.

There is no `language` or `miseTool` field. A managed runtime is declared in
`runtimes`, and its primary tool is `runtimes[0].tool` (an empty string when no
runtime is declared). Generated language adapters use that rule:

```lua
local runtime = (manifest.runtimes or {})[1] or {}
local tool = runtime.tool or ""
local version = (request.runtime and request.runtime.version) or runtime.version or "latest"
```

The app rejects a manifest that still carries `language` or `miseTool`.

Runtime rules enforced by the validator:

- a `runtimes[].setting` must name a settings field;
- a `runtimes[].packages.setting` must name a settings field;
- `runtimes[].setting` must be a select field whose default is one of its
  options, and `runtimes[].version` must equal that default;
- only known mise tools and the `conda:` backend prefix are allowed; `asdf:`
  and `vfox:` are rejected;
- conda tools are limited to `gcc`, `gxx`, and `r-base` and must use a pinned
  `X.Y.Z` version;
- Python options are limited to 3.8 through 3.15, with 3.13 as the default;
- an adapter with managed runtimes must declare a non-empty `bootstrap.mise`;
- `bootstrap.mise`/`bootstrap.uv` must be `latest` or the pinned version the
  app supports (`2026.11.11` and `0.13.9`); arbitrary strings are rejected;
- every runnable adapter needs smoke metadata in `scripts/languages.json`.

## Adapter result protocol

An adapter reports its outcome by calling `app.result` exactly once. Every run
ends in one of five statuses. The old `{ error = ... }` table and a score
without a status are no longer accepted.

| Status | When | Fields |
| --- | --- | --- |
| `graded` | The adapter compared the submission with the key. | `score`, `comment`; optional `rationale`, `text`, `output`, `outputPath` |
| `previewed` | The app asked for a preview (`request.mode == "preview"`). | `text`; optional `output`, `outputPath` |
| `declined` | The adapter cannot run because the key or an input is missing. | `code` (`missing-key` or `missing-input`), `message`; optional `detail` |
| `failed` | The adapter or a program it started failed. | `code` (for example `program-error`), `message`; optional `detail` |
| `timeout` | A program run by the adapter exceeded its limit. | `stage` (`runtime` or `script`), `message`; optional `detail` |

```lua
-- A completed comparison.
app.result({
  status = "graded",
  score = 2.5,
  comment = "Program output matches the key.",
  rationale = "Printed output matched the expected answer.",
  text = output.stdout,
  output = { kind = "diff", expected = expected, actual = output.stdout },
})

-- Preview mode.
app.result({ status = "previewed", text = output.stdout })

-- The key is missing: leave the question unmarked.
app.result({
  status = "declined",
  code = "missing-key",
  message = "The key has no expected output to compare with.",
})

-- A program that exited non-zero or could not start.
app.result({
  status = "failed",
  code = "program-error",
  message = "The program stopped with an error.",
  detail = output.stderr,
})

-- A program that exceeded its time limit.
app.result({
  status = "timeout",
  stage = "runtime",
  message = "The program timed out.",
})
```

Use `declined` with `code = "missing-input"` when the submitted file or a
required question input is absent. Use `failed` with code `program-error` when
a process exits non-zero or cannot start, and `timeout` with stage `runtime`
when a process reports `code == -1`.

A failure, timeout, or decline must never return `score = 0`: that records a
wrong answer. Leave the question unmarked instead. Only a completed comparison
returns `score` with `status = "graded"`. Call `app.result` once; a missing or
second call is an adapter error.

## Deterministic JSON

`registry.json` and `registry.config.json` are written with:

- UTF-8, no BOM;
- keys sorted lexicographically;
- two-space indentation;
- LF line endings only;
- exactly one trailing newline.

Use `python scripts/registry.py format registry.json registry.config.json` and
check it with `--check`. `python scripts/update.py --check` also fails when the
index does not match the adapter folders. There is no JCS canonicalisation: the
bytes on disk are the bytes that are signed.

## Updating an adapter

1. Edit the manifest and adapter files.
2. Bump `manifest.version` and the README `- **Version:**` line.
3. Run `python scripts/update.py` to refresh mirrored fields and checksums.
4. Run `python scripts/validate.py`.
5. Commit the adapter, `registry.json`, and any README changes in one pull
   request.

The signing workflow revalidates, bumps `sequence`, refreshes the timestamps,
signs, tags, and publishes.

## Schema 7 only

This registry publishes schema 7 only. There is no schema-6 fallback and no
dual format. An app that cannot verify schema 7 must refuse the registry rather
than silently treat it as schema 6.
