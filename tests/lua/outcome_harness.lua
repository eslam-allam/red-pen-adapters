-- Smoke harness for the adapter outcome protocol.
--
-- Usage:
--   lua tests/lua/outcome_harness.lua <adapter.lua> <example|language|logisim> <scenario>
--
-- The harness stubs the adapter API, runs the adapter once, and fails unless
-- the adapter made exactly one app.result call with the status, code, stage
-- and payload the scenario expects.
local adapter_path = arg[1]
local adapter_kind = arg[2]
local scenario = arg[3]
if not adapter_path or not adapter_kind or not scenario then
  io.stderr:write("usage: lua outcome_harness.lua <adapter.lua> <kind> <scenario>\n")
  os.exit(2)
end

local calls = {}
local queue = {}
local queue_index = 0

local function process_result(code, stdout, stderr)
  return { code = code, stdout = stdout or "", stderr = stderr or "" }
end

local function next_process()
  queue_index = queue_index + 1
  local value = queue[queue_index]
  if value == nil then
    error("the adapter started a process the scenario did not queue")
  end
  if value == "launch-error" then
    error("simulated launch failure")
  end
  return value
end

local file_path = "/tmp/redpen-outcome-submission.txt"
local file_content = "alpha\nbeta\n"

local expected = "hello"
local expected_table = "# red-pen header: A\tB\tY\n0 0 0\n0 1 0\n1 0 0\n1 1 1"
local stdout = "hello\n"
local logisim_stdout = "A B Y\n0 0 0\n0 1 0\n1 0 0\n1 1 1"
local request_context = {
  maxPoints = 5,
  expected = expected,
  values = { expected = expected },
  questionValues = {},
}

if adapter_kind == "example" then
  file_content = "alpha\nbeta\n"
  request_context = {
    maxPoints = 5,
    expected = "2",
    values = { expectedLines = "2" },
    questionValues = {},
  }
elseif adapter_kind == "logisim" then
  request_context = {
    maxPoints = 5,
    values = { table = expected_table },
    questionValues = { circuit = "main" },
  }
  stdout = logisim_stdout
elseif adapter_kind ~= "language" then
  io.stderr:write("unknown adapter kind: " .. adapter_kind .. "\n")
  os.exit(2)
end

if scenario == "missing-input" then
  file_path = ""
elseif scenario == "missing-key" then
  if adapter_kind == "example" then
    request_context.values = {}
    request_context.expected = nil
  elseif adapter_kind == "logisim" then
    request_context.values.table = ""
  else
    request_context.values = {}
    request_context.expected = ""
  end
end

local mode = scenario == "previewed" and "preview" or "grade"
if mode == "preview" then
  request_context = nil
end

if scenario == "graded" or scenario == "previewed" or scenario == "read-error"
  or (scenario == "missing-key" and adapter_kind ~= "example") then
  queue = { process_result(0, stdout), process_result(0, stdout) }
elseif scenario == "missing-key" then
  queue = {}
elseif scenario == "timeout" then
  queue = { process_result(-1, "", "timed out") }
elseif scenario == "failed-exit" then
  queue = { process_result(1, "", "boom") }
elseif scenario == "launch-failure" then
  queue = { "launch-error" }
elseif scenario == "missing-input" then
  queue = {}
else
  io.stderr:write("unknown scenario: " .. scenario .. "\n")
  os.exit(2)
end

app = {
  read_file = function(path)
    if scenario == "read-error" then
      error("simulated read failure")
    end
    return file_content
  end,
  write_file = function(path, data) return true end,
  temp_dir = function() return "/tmp/redpen-outcome-temp" end,
  run_runtime = function(tool, version, program, args, stdin)
    return next_process()
  end,
  run_command = function(program, args, stdin)
    return next_process()
  end,
  log = function(message) end,
  result = function(value)
    calls[#calls + 1] = value
  end,
}

request = {
  version = 1,
  mode = mode,
  filePath = file_path,
  fileName = "submission.txt",
  extension = "txt",
  os = { platform = "linux", family = "unix", arch = "x86_64" },
  permissions = { "subprocess" },
  settings = { programPath = "/fake/logisim", pythonVersion = "3.13" },
  context = request_context,
  runtime = { tool = "fake", version = "1.0", program = "/fake/runtime" },
}

manifest = {
  runtimes = { { tool = "fake", version = "1.0" } },
}

local chunk, load_error = loadfile(adapter_path)
if not chunk then
  io.stderr:write("could not load " .. adapter_path .. ": " .. tostring(load_error) .. "\n")
  os.exit(2)
end
local ran, run_error = pcall(chunk)
if not ran then
  io.stderr:write(adapter_path .. ": adapter error: " .. tostring(run_error) .. "\n")
  os.exit(1)
end

local function fail(message)
  io.stderr:write(adapter_path .. " [" .. scenario .. "]: " .. message .. "\n")
  os.exit(1)
end

if #calls ~= 1 then
  fail("expected exactly one app.result call, got " .. tostring(#calls))
end
local result = calls[1]

local expected_status = ({
  graded = "graded",
  previewed = "previewed",
  ["missing-key"] = "declined",
  ["missing-input"] = "declined",
  timeout = "timeout",
  ["failed-exit"] = "failed",
  ["launch-failure"] = "failed",
  ["read-error"] = "failed",
})[scenario]
if result.status ~= expected_status then
  fail(
    "expected status " .. expected_status
      .. ", got " .. tostring(result.status)
      .. " (code=" .. tostring(result.code)
      .. ", message=" .. tostring(result.message)
      .. ", detail=" .. tostring(result.detail) .. ")"
  )
end

if scenario == "graded" then
  if result.score ~= 5 then
    fail("expected score 5, got " .. tostring(result.score))
  end
  if type(result.comment) ~= "string" or result.comment == "" then
    fail("graded result has no comment")
  end
  if type(result.rationale) ~= "string" or result.rationale == "" then
    fail("graded result has no rationale")
  end
  local expected_kind = adapter_kind == "logisim" and "tableDiff" or "diff"
  if type(result.output) ~= "table" or result.output.kind ~= expected_kind then
    fail("expected a " .. expected_kind .. " output")
  end
elseif scenario == "previewed" then
  if type(result.text) ~= "string" or result.text == "" then
    fail("previewed result has no text")
  end
elseif scenario == "missing-key" then
  if result.code ~= "missing-key" then
    fail("expected code missing-key, got " .. tostring(result.code))
  end
elseif scenario == "missing-input" then
  if result.code ~= "missing-input" then
    fail("expected code missing-input, got " .. tostring(result.code))
  end
elseif scenario == "timeout" then
  if result.stage ~= "runtime" then
    fail("expected stage runtime, got " .. tostring(result.stage))
  end
elseif scenario == "failed-exit" or scenario == "launch-failure" then
  if result.code ~= "program-error" then
    fail("expected code program-error, got " .. tostring(result.code))
  end
elseif scenario == "read-error" then
  if result.code ~= "read-error" then
    fail("expected code read-error, got " .. tostring(result.code))
  end
end
