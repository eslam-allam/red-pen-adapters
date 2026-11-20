# R

Runs an R script.

- **Version:** 2.5.0
- **Works on:** files, questions
- **File extensions:** .r
- **Permissions:** subprocess

## How it works

The app installs R through mise's conda backend as `conda:r-base@4.6.2` on first use. The adapter runs the submission with that runtime's `Rscript` through `app.run_runtime`. Printed output is compared with the **Expected output** key field.

The equivalent manual command is:

```sh
mise x conda:r-base@4.6.2 -- Rscript program.r
```

## Settings

- **Runtime version:** R 4.6.2, installed with the app's conda backend on first use. Default: `4.6.2`.
