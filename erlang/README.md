# Erlang

Runs an Erlang script with escript.

- **Version:** 2.3.0
- **Works on:** files, questions
- **File extensions:** .erl
- **Permissions:** subprocess

## How it works

Runs the submitted Erlang code through the requested runtime version. Printed output is compared with the **Expected output** key field.

Runtime versions are managed by the app through mise; the adapter does not download or expose a mise path.

## Settings

- **Runtime version:** The language version to install with mise, for example 22.11.0 or 3.3. It is downloaded on first use. Default: `latest`.
