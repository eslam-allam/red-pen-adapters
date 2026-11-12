---@meta

-- Definitions for the Red Pen adapter runtime. Point lua-language-server at
-- this folder (the repository's .luarc.json does that already) so `request`,
-- `manifest` and `app` are typed, and so `io`, `os`, `package` and
-- `debug` are reported as unavailable.

---@class RedPenFieldContext
---@field section? string
---@field part? string
---@field preceding? string
---@field tableLabel? string
---@field rowLabel? string
---@field colLabel? string

---@class RedPenContext
---@field maxPoints number
---@field label string
---@field questionId string
---@field expected? string
---@field values table<string, string>
--- Values for the adapter's per-question `questionInput` fields.
---@field questionValues table<string, string>

---@class RedPenRuntime
---@field tool string
---@field version string
--- The interpreter of the app-managed environment, when the app prepared one
--- (a Python venv with the packages from the settings, for example).
---@field program? string

---@class RedPenOs
--- The platform name, e.g. "windows", "linux" or "macos".
---@field platform string
--- "windows" or "unix".
---@field family "windows"|"unix"
--- The CPU architecture, e.g. "x86_64" or "aarch64".
---@field arch string

---@class RedPenRequest
---@field version integer
---@field mode "preview"|"grade"
---@field filePath string
---@field fileName string
---@field extension string
--- The operating system, so an adapter can pick the right command.
---@field os RedPenOs
---@field permissions string[]
---@field settings table<string, string>
---@field context? RedPenContext
--- The folder the instructor chose for this run, when the manifest declares a
--- `directoryPicker`.
---@field grantedDirectory? string
--- The runtime the app prepared for this run.
---@field runtime? RedPenRuntime

---@type RedPenRequest
request = nil

---@class RedPenManifest
---@field id string
---@field name string
---@field version string
---@field language? string
--- The mise tool that supplies this adapter's language runtime.
---@field miseTool? string
---@field extensions string[]
---@field permissions string[]
--- Per-user registry keys the adapter needs on Windows.
---@field registry? string[]
---@field settings? table[]
---@field keyInput? table[]
---@field [string] any

---@type RedPenManifest
manifest = nil

---@class RedPenResult
---@field score? number
---@field comment? string
---@field rationale? string
--- Preview text shown when the attachment is opened.
---@field text? string
---@field outputPath? string
---@field error? string
--- The outputs declared by the manifest. Return one object for one kind, or
--- a list whose kinds match the manifest exactly and in the same order.
---@field output? RedPenOutput|RedPenOutput[]

---@class RedPenTableOutput
---@field kind "table"
---@field title? string
---@field columns string[]
---@field rows string[][]
---@field mismatchedRows? integer[] Zero-based row indexes.
---@field mismatchedCells? { row: integer, column: integer }[] Zero-based cells.

---@class RedPenTableDiffOutput
---@field kind "tableDiff"
---@field title? string
---@field columns string[]
--- The correct values, shown on the left in green.
---@field expectedRows string[][]
--- The student's values, shown on the right in red.
---@field actualRows string[][]
---@field mismatchedRows? integer[] Zero-based row indexes.
---@field mismatchedCells? { row: integer, column: integer }[] Zero-based cells.
---@field expectedLabel? string
---@field actualLabel? string

---@class RedPenDiffOutput
---@field kind "diff"
---@field title? string
---@field expected string
---@field actual string
---@field expectedLabel? string
---@field actualLabel? string

---@class RedPenTextOutput
---@field kind "text"
---@field title? string
---@field text string

---@class RedPenImageOutput
---@field kind "image"
---@field title? string
--- A base64 image data URI.
---@field src string
---@field alt? string

---@class RedPenJsonOutput
---@field kind "json"
---@field title? string
---@field value any

---@alias RedPenOutput RedPenTableOutput|RedPenTableDiffOutput|RedPenDiffOutput|RedPenTextOutput|RedPenImageOutput|RedPenJsonOutput

---@class RedPenProcess
---@field stdout string
---@field stderr string
---@field code integer

---@class RedPenApp
--- Reads the submitted file, the adapter folder, its temp folder, or a folder
--- the manifest granted. `files:read` is not needed for sandbox-internal
--- paths.
---@field read_file fun(path: string): string
--- Writes inside the adapter temp folder or a read-write folder grant.
---@field write_file fun(path: string, data: string): boolean
---@field temp_dir fun(): string
--- Runs a program from a runtime the manifest declared. The runtime is
--- installed by the app; the adapter does not download it.
---@field run_runtime fun(tool: string, version: string, program: string, args: string[]|nil, stdin: string|nil): RedPenProcess
--- Runs a program directly inside the sandbox.
---@field run_command fun(program: string, args: string[]|nil, stdin: string|nil): RedPenProcess
--- Returns the adapter's result. Call this once, at the end of the script.
---@field result fun(value: RedPenResult)
---@field log fun(message: string)

---@type RedPenApp
app = nil

-- Unavailable in the embedded adapter runtime: io, os, package, debug,
-- load, loadfile and dofile. Use `app` for files and processes instead.
