# Logisim

Runs Logisim's truth-table mode and compares the generated table with the key.

- **Version:** 4.6.0
- **Works on:** files
- **File extensions:** .circ
- **Permissions:** subprocess
- **Windows registry:** `HKCU\Software\JavaSoft\Prefs`, `...\com`, `...\com\cburch`, `...\com\cburch\logisim`

## How it works

Runs the configured Logisim executable in truth-table mode and compares the generated rows with the **Key truth table** field. The key table declares one input section and one output section. Add as many inputs and outputs as the circuit needs. The number of rows follows `2 ^ inputs`, and every output bit must be filled. The input columns are prefilled with the binary counting sequence.

Name the input and output columns after the pins in the circuit (for example `A1 A0 B1 B0` and `P3 P2 P1 P0`). When the key names its columns, the adapter matches the circuit's columns by name, so reordering inputs or outputs does not change the result. Without a named header the adapter compares columns by position.

Set the Logisim executable in the adapter settings. The app runs it through the adapter host API; the adapter never starts a shell.

The result is one table-diff output: **Key** on the left with the correct answer and **Student** on the right with the circuit's generated table. Cells that differ are green in the key table and red in the student table. Missing or extra rows are highlighted as whole rows.

Runtime versions are managed by the app through mise; the adapter does not download or expose a mise path.

## Settings

- **Logisim executable:** The path to logisim-evolution or logisim.
