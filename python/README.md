# Python (uv)

Runs Python code from a submitted .py file or from the answer text, and compares what it prints with the key answer.

- **Version:** 2.0.0
- **Works on:** files, questions
- **File extensions:** .py
- **Permissions:** files:read, network, subprocess

## How it works

Runs the submitted Python file, or the Python answer text, in a temporary virtual environment created by the app. The requested Python version is installed by mise.

The **Packages** setting accepts one package per line. Printed output is compared with the **Expected output** key field.

Runtime versions are managed by the app through mise; the adapter does not download or expose a mise path.

## Settings

- **Python version:** uv downloads this version on first use and keeps it in its cache. Default: `3.12`.
- **Packages:** One package per line, for example numpy or pandas==2.2. It is installed into the run environment automatically.
- **Seconds before stopping:** How long the submitted program may run. Default: `10`.
