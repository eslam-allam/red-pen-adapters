# C#

Runs a single C# file with the .NET SDK.

- **Version:** 2.5.0
- **Works on:** files, questions
- **File extensions:** .cs
- **Permissions:** subprocess

## How it works

The app installs the .NET SDK through mise as `dotnet@10.0` on first use; 10.0 currently resolves to SDK 10.0.404. The adapter runs:

```sh
dotnet run --file program.cs -p:PublishAot=false -- <input>
```

`PublishAot=false` keeps file-based apps on the fast JIT path instead of trying an ahead-of-time publish. Printed output is compared with the **Expected output** key field.

## Settings

- **Runtime version:** The .NET SDK line to install. `10.0` resolves to the 10.0.4xx SDK (10.0.404 at the time of writing); `11.0` is offered for testing. Default: `10.0`.
