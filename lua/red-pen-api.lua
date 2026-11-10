---@meta

---@class RedPenContext
---@field expected string
---@field maxPoints number
---@field label string
---@field questionId string
---@field values table<string, string>

---@class RedPenRequest
---@field version integer
---@field mode "preview" | "grade"
---@field filePath string
---@field fileName string
---@field extension string
---@field context RedPenContext
---@field settings table<string, string>
---@field permissions string[]

---@class RedPenResult
---@field score number|nil
---@field comment string|nil
---@field rationale string|nil
---@field text string|nil
---@field error string|nil

---@class RedPenProcess
---@field stdout string
---@field stderr string
---@field code integer

---@class RedPenApp
---@field read_file fun(path: string): string
---@field write_file fun(path: string, data: string): boolean
---@field temp_dir fun(): string
---@field run_runtime fun(tool: string, version: string, program: string, args: string[]|nil, stdin: string|nil): RedPenProcess
---@field run_command fun(program: string, args: string[]|nil, stdin: string|nil): RedPenProcess
---@field log fun(message: string)

---@type RedPenApp
app = {}

---@type RedPenRequest
request = {}

---@type table
manifest = {}

---@type RedPenResult
result = {}
