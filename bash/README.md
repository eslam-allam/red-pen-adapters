# Bash

Runs a Bash script with the `bash` already installed on the system.

- **Version:** 2.5.0
- **Works on:** files, questions
- **File extensions:** .sh, .bash
- **Permissions:** subprocess

## How it works

The adapter starts the system `bash` through `app.run_command`; it does not download or manage a Bash runtime. Printed output is compared with the **Expected output** key field.

The version is whatever `bash` the operating system provides. On Linux and macOS that is normally a recent Bash; on Windows it is the Bash that ships with Git Bash or WSL.

## Windows

Bash is not bundled on Windows. Install Git Bash (so that `bash` is on `PATH`) or enable WSL, then try again. If `bash` cannot be started, the adapter returns an error without a score; it never downloads a managed Bash as a fallback.

## Settings

This adapter has no settings.
