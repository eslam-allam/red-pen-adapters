# Logisim

Runs Logisim's truth-table mode and compares the generated table with the key.

- **Version:** 4.1.0
- **Works on:** files
- **File extensions:** .circ
- **Permissions:** subprocess

## How it works

Runs the configured Logisim executable in truth-table mode and compares the generated rows with the **Key truth table** field. The key table starts with one input column and one output column. Add as many inputs and outputs as the circuit needs, then fill every output bit.

Set the Logisim executable in the adapter settings. The app runs it through the adapter host API; the adapter never starts a shell.

Runtime versions are managed by the app through mise; the adapter does not download or expose a mise path.

## Settings

- **Logisim executable:** The path to logisim-evolution or logisim.
