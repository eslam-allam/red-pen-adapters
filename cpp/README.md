# C++

Compiles and runs a C++ program.

- **Version:** 2.5.0
- **Works on:** files, questions
- **File extensions:** .cpp, .cc, .cxx
- **Permissions:** subprocess

## How it works

The app installs G++ through mise's conda backend as `conda:gxx@16.2.0` on first use. The adapter compiles the submission with that G++ through `app.run_runtime`, then runs the binary in the run's temporary folder. Printed output is compared with the **Expected output** key field.

## Windows

The adapter adds `-static` on Windows so the produced executable does not need MinGW runtime DLLs beside it. The equivalent manual command is:

```sh
mise x conda:gxx@16.2.0 -- g++ program.cpp -o program.exe -static
```

If the conda backend is unavailable, the documented fallback is Zig's C++ compiler:

```sh
mise x zig@0.17.1 -- zig c++ program.cpp -o program
```

The adapter does not switch compilers automatically; it reports the failure instead of silently building with a different toolchain.

## Settings

- **Runtime version:** G++ 16.2.0, installed with the app's conda backend on first use. Default: `16.2.0`.
