# F#

Runs an F# script with dotnet fsi.

- **Version:** 2.1.0
- **Works on:** files, questions
- **File extensions:** .fsx, .fs
- **Permissions:** subprocess

## How it works

Runs the submitted F# code through the requested runtime version. Printed output is compared with the **Expected output** key field.

Runtime versions are managed by the app through mise; the adapter does not download or expose a mise path.

## Settings

- **Runtime version:** The language version to install with mise, for example 22.11.0 or 3.3. It is downloaded on first use. Default: `latest`.
