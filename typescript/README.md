# TypeScript

Runs TypeScript with tsx.

- **Version:** 2.1.0
- **Works on:** files, questions
- **File extensions:** .ts, .tsx, .mts, .cts
- **Permissions:** subprocess

## How it works

Runs the submitted TypeScript through `tsx` using the requested Node.js version. Printed output is compared with the **Expected output** key field.

Runtime versions are managed by the app through mise; the adapter does not download or expose a mise path.

## Settings

- **Runtime version:** The language version to install with mise, for example 22.11.0 or 3.3. It is downloaded on first use. Default: `latest`.
