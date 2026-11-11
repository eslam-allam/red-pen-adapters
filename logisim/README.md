# Logisim

Runs Logisim's truth-table mode and compares the generated table with the key.

- **Version:** 4.1.0
- **Works on:** files
- **File extensions:** .circ
- **Permissions:** subprocess

## How it works

Runs the configured Logisim executable in truth-table mode and compares the generated rows with the **Key truth table** field. The key table lays out the four inputs (`A1 A0 B1 B0`) and four outputs (`P3 P2 P1 P0`).

Set the Logisim executable in the adapter settings. The app runs it through the adapter host API; the adapter never starts a shell.

Runtime versions are managed by the app through mise; the adapter does not download or expose a mise path.

## Settings

- **Logisim executable:** The path to logisim-evolution or logisim.
