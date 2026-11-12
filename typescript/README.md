# TypeScript

Runs TypeScript and TSX with Bun.

- **Version:** 2.4.0
- **Works on:** files, questions
- **File extensions:** .ts, .tsx, .mts, .cts
- **Permissions:** subprocess

## How it works

Runs the submitted TypeScript or TSX code with the app-managed Bun runtime. Printed output is compared with the **Expected output** key field.

Runtime versions are managed by the app through mise; the adapter does not download or expose a mise path. Bun runs TypeScript and TSX directly, so no package is fetched at run time.

## Settings

- **Runtime version:** The Bun version to install with mise, for example 1.4.4. It is downloaded on first use. Default: `latest`.
