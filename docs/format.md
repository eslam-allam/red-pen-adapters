# Registry format (schema 6)

A registry is a folder of adapters plus one signed index. The app downloads
`registry.json`, verifies its signature, then downloads only the files the
signed index lists and checks their SHA-256 digests.

## Layout

```
registry.json
registry.json.minisig        created by the signing workflow
registry.config.json
schemas/
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

## registry.json

```json
{
  "$schema": "./schemas/registry.schema.json",
  "schema": 6,
  "kind": "red-pen-adapters",
  "registryId": "example-registry",
  "name": "Example Red Pen adapter registry",
  "description": "Optional summary",
  "publisher": "Example publisher",
  "sequence": 1,
  "issuedAt": "2026-11-20T21:00:00Z",
  "expiresAt": "2027-05-19T21:00:00Z",
  "adapters": []
}
```

| Field | Rules |
| --- | --- |
| `schema` | Exactly `6`. |
| `kind` | Exactly `red-pen-adapters`. |
| `registryId` | Globally unique lowercase slug, `^[a-z0-9][a-z0-9._-]{0,127}$`, no slashes. Official is `red-pen-official`; community is `red-pen-community`; third-party registries may not use those reserved ids. Must match `registry.config.json` and the signature's trusted comment. |
| `name` | Human-readable registry name. |
| `publisher` | Non-empty display-name string, at most 256 characters, no control characters. The app parses this as a string, not an object. |
| `sequence` | Integer `>= 1`, strictly increasing. The workflow tags `registry-v<sequence>`. |
| `issuedAt` | RFC 3339 UTC, seconds precision, `YYYY-MM-DDTHH:MM:SSZ`. |
| `expiresAt` | UTC, later than `issuedAt`; at most 366 days later. Verification refuses an expired registry. |
| `adapters` | Non-empty array of entries. |

`sequence`, `issuedAt`, and `expiresAt` are owned by the signer. Do not bump
them by hand in a pull request; the signing workflow sets them.

## Adapter entry

```json
{
  "id": "example",
  "name": "Example line counter",
  "version": "1.0.0",
  "description": "Counts non-empty lines.",
  "author": "Red Pen Template",
  "appliesTo": ["file"],
  "permissions": [],
  "extensions": ["txt", "md"],
  "bootstrap": { "mise": "latest" },
  "folder": "example",
  "files": [
    { "path": "adapter.lua", "sha256": "..." },
    { "path": "manifest.json", "sha256": "..." }
  ],
  "readmeUrl": "https://raw.githubusercontent.com/OWNER/REPO/main/example/README.md"
}
```

The entry mirrors the install-gating parts of `manifest.json`: `name`,
`version`, `description`, `author`, `icon`, `homepage`, `extensions`,
`appliesTo`, `permissions`, `registry`, `runtimes`, and `bootstrap`.
`scripts/update.py` copies them and `scripts/validate.py` refuses a mismatch.
Never edit only one side.

`files` must be objects with `path` and lowercase `sha256`. Bare file strings
are rejected in schema 6 because the signed index has to authenticate every
byte. Paths are relative, use `/`, and may not contain `..`, an absolute path, a
backslash, a colon, or control characters. `manifest.json` and `adapter.lua`
are required.

`readmeUrl` must be
`<readmeBaseUrl>/<adapter-id>/README.md`. The README may reference
`assets/...`; assets are fetched for display but are not installed.

## manifest.json

`schemas/manifest.schema.json` is the app-facing manifest schema. Keep using
the manifest schema version the app supports (currently `schema: 4`). The
registry entry does not repeat `output`, `keyInput`, `questionInput`,
`directories`, or `directoryPicker`; those live only in the manifest and are
covered by the manifest's SHA-256 entry. `bootstrap` **is** mirrored into the
entry so the signed index gates the mise/uv version the app will download.

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
- `bootstrap.mise`/`bootstrap.uv` must be `latest`, `null`, or a full SemVer
  2.0.0 pin (optional `v` prefix, prerelease, and build metadata); arbitrary
  strings are rejected;
- a generated adapter's `miseTool`/`language` must match its runtime tool;
- every runnable adapter needs smoke metadata in `scripts/languages.json`.

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

## Schema 6 only

This registry publishes schema 6 only. There is no schema-5 fallback and no
dual format. An app that cannot verify schema 6 must refuse the registry rather
than silently treat it as schema 5.
