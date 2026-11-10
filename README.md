# Red Pen adapter registry

The official registry for Red Pen adapters. The app reads `registry.json`,
shows each adapter's declared permissions, and installs the adapter ZIP into
its app-data folder.

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
      "permissions": ["files:read", "subprocess"],
      "downloadUrl": "https://…/logisim.zip",
      "sha256": "…"
    }
  ]
}
```

The ZIP contains `manifest.json` at its root and, for a process adapter, the
adapter's own program.

## Logisim

The Logisim adapter is built into Red Pen, so its ZIP contains only the
manifest. It runs `logisim-evolution -tty table <circuit>` (or `logisim`) and
compares the generated truth table with the `table` key input. Set the
`programPath` setting to the Logisim executable, or set `LOGISIM_BIN`, or put
`logisim-evolution`/`logisim` on `PATH`. No Python or other interpreter is
required.
