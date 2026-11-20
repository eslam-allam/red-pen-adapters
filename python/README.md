# Python

Runs Python code from a submitted .py file or from the answer text, and compares what it prints with the key answer.

- **Version:** 2.5.0
- **Works on:** files, questions
- **File extensions:** .py
- **Permissions:** subprocess

## How it works

Runs the submitted Python file, or the Python answer text, in a managed virtual environment created by the app. The app installs the selected Python through mise and adds the requested packages before the run.

Printed output is compared with the **Expected output** key field.

## Version support

| Version | Status |
| --- | --- |
| 3.8, 3.9, 3.10 | End-of-life. Kept for old submissions, but they receive no security fixes. |
| 3.11 to 3.15 | Supported. **3.13** is the default. |

The registry offers Python 3.8-3.15 only. The validator rejects a manifest that offers 3.16, a free-threaded build such as `3.13t`/`3.14t`, or any other version outside that set. A hand-edited setting outside the list is unsupported and untested; reinstall or choose a listed version if a run fails. Some older versions have no prebuilt Python for Windows on ARM, 32-bit Windows, or musl-based Linux; the app reports the install failure instead of silently switching to another version.

## Settings

- **Python version:** The Python version to install before the first run. Python 3.8-3.10 are end-of-life; 3.13 is the default. Default: `3.13`.
- **Packages:** One package per line, for example numpy or pandas==2.2. Red Pen installs them into the managed environment before the program runs.
