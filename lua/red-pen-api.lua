---@meta

-- Definitions for the Red Pen adapter runtime. Point lua-language-server at
-- this folder (the repository's .luarc.json does that already) so `request`,
-- `manifest`, `result` and `app` are typed, and so `io`, `os`, `package` and
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

---@class RedPenRuntime
---@field tool string
---@field version string
--- The interpreter of the app-managed environment, when the app prepared one
--- (a Python venv with the packages from the settings, for example).
---@field program? string

---@class RedPenRequest
---@field version integer
---@field mode "preview"|"grade"
---@field filePath string
---@field fileName string
---@field extension string
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
---@field settings? table[]
---@field keyInput? table[]
---@field [string] any

---@type RedPenManifest
manifest = nil

---@class RedPenResult
---@field score? number
---@field comment? string
---@field rationale? string
---@field text? string
---@field outputPath? string
---@field error? string

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
---@field run_runtime fun(tool: string, version: string, program: string, args?: string[], stdin?: string): RedPenProcess
--- Runs a program directly inside the sandbox.
---@field run_command fun(program: string, args?: string[], stdin?: string): RedPenProcess
---@field log fun(message: string)

---@type RedPenApp
app = nil

--- Set this to the table the adapter returns: text and/or score/comment.
---@type RedPenResult|nil
result = nil

-- Unavailable in the embedded adapter runtime: io, os, package, debug,
-- load, loadfile and dofile. Use `app` for files and processes instead.
