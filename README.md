# Red Pen adapter registry

The official registry for Red Pen adapters. The app reads `registry.json`,
lets the user review the permissions an adapter declares, and installs the
adapter ZIP into its app-data folder.

## Registry format

```json
{
  "schema": 1,
  "name": "Red Pen official adapter registry",
  "adapters": [
    {
      "id": "logisim",
      "name": "Logisim",
      "version": "1.0.0",
      "description": "…",
      "permissions": ["files:read", "subprocess"],
      "downloadUrl": "https://…/logisim.zip",
      "sha256": "…"
    }
  ]
}
```

The ZIP contains `manifest.json` at its root and the adapter's own files.

## Logisim

The Logisim adapter needs Logisim Evolution on the machine. It uses the
`logisimBin` setting, then `LOGISIM_BIN`, then `logisim-evolution`, then
`logisim`. It runs `-tty table <circuit>` and compares the generated table with
the `table` key input.
