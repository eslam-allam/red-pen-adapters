# TypeScript

Runs TypeScript with tsx.

- **Version:** 2.0.0
- **Works on:** files, questions
- **File extensions:** .ts, .tsx, .mts, .cts
- **Permissions:** files:read, network, subprocess

## How it works

Runs the submitted TypeScript through `tsx` using the requested Node.js version. Printed output is compared with the **Expected output** key field.

Runtime versions are managed by the app through mise; the adapter does not download or expose a mise path.

## Settings

- **Runtime version:** The language version to install with mise, for example 22.11.0 or 3.3. It is downloaded on first use. Default: `latest`.
- **Runtime executable:** The runtime that runs this language. Leave empty to use PATH.
- **Seconds before stopping:** How long the submitted program may run. Default: `15`.
