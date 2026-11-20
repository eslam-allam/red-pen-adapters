# Elixir

Runs an Elixir script.

- **Version:** 2.5.0
- **Works on:** files, questions
- **File extensions:** .exs, .ex
- **Permissions:** subprocess

## How it works

Runs the submitted Elixir code through the requested runtime version. Printed output is compared with the **Expected output** key field.

Runtime versions are managed by the app through mise; the adapter does not download or expose a mise path.

## Settings

- **Runtime version:** The runtime to install with mise. `latest` installs the newest supported release on first use. Default: `latest`.
