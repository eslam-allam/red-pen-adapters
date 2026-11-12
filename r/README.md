# R

Runs an R script.

- **Version:** 2.4.0
- **Works on:** files, questions
- **File extensions:** .r
- **Permissions:** subprocess

## How it works

Runs the submitted R code through the requested runtime version. Printed output is compared with the **Expected output** key field.

Runtime versions are managed by the app through mise; the adapter does not download or expose a mise path.

## Settings

- **Runtime version:** The language version to install with mise, for example 22.11.0 or 3.3. It is downloaded on first use. Default: `latest`.
