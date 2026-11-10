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
      "appliesTo": ["file", "question"],
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


## Python (uv)

The Python adapter runs code supplied as a `.py` attachment or as the answer
to a question. It compares the program's printed output with the `expected`
key field. Choose the Python version and any packages in the adapter settings.

The adapter package asks the app to download the `uv` launcher into its own
folder on first install (`bootstrap.uv`). uv then downloads the requested
Python version on first use and keeps it in its cache. The adapter declares
`network` for that download and `subprocess` for running the student's code.
