# Python

Runs Python code from a submitted .py file or from the answer text, and compares what it prints with the key answer.

- **Version:** 2.1.0
- **Works on:** files, questions
- **File extensions:** .py
- **Permissions:** subprocess

## How it works

Runs the submitted Python file, or the Python answer text, in a managed virtual environment created by the app. The requested Python version is installed by mise.

The **Packages** setting accepts one package per line. Printed output is compared with the **Expected output** key field.

Runtime versions are managed by the app through mise; the adapter does not download or expose a mise path.

## Settings

- **Python version:** Red Pen downloads this version before the first run and keeps it in its cache. Default: `3.12`.
- **Packages:** One package per line, for example numpy or pandas==2.2. Red Pen installs them into a managed environment before the program runs.
