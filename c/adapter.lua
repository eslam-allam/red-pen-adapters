-- Generated from scripts/templates/language_adapter.lua. Do not edit by hand.
-- Regenerate with: python scripts/generate.py
local settings = request.settings or {}
local context = request.context or {}
local values = context.values or {}
local expected = values.expected or context.expected or ""
local max_points = tonumber(context.maxPoints) or 0
local runtime = (manifest.runtimes or {})[1] or {}
local tool = runtime.tool or ""
local version = (request.runtime and request.runtime.version) or runtime.version or "latest"
local file = request.filePath

local function normalise(text)
  if not text then return "" end
  local lines = {}
  for line in (text:gsub("\r\n", "\n") .. "\n"):gmatch("(.-)\n") do
    lines[#lines + 1] = (line:gsub("%s+$", ""))
  end
  while #lines > 0 and lines[#lines] == "" do table.remove(lines) end
  return table.concat(lines, "\n"):match("^%s*(.-)%s*$")
end

local function detail_text(value)
  if value == nil then return "" end
  return tostring(value)
end

-- Every run ends with exactly one app.result call and an explicit status:
-- graded, previewed, declined, failed or timeout. A failure, timeout or
-- decline must never return score = 0: the app would record that as a wrong
-- answer instead of leaving the question for manual marking.
local function decline(code, message, detail)
  app.result({
    status = "declined",
    code = code,
    message = message,
    detail = detail_text(detail),
  })
end

local function fail(code, message, detail)
  app.result({
    status = "failed",
    code = code,
    message = message,
    detail = detail_text(detail),
  })
end

local function timeout(stage, message, detail)
  app.result({
    status = "timeout",
    stage = stage,
    message = message,
    detail = detail_text(detail),
  })
end

local function run(program, args)
  return app.run_runtime(tool, version, program, args or {}, "")
end

local question = context.questionValues or {}
local input_file = (question.inputFile or ""):match("^%s*(.-)%s*$")

if type(file) ~= "string" or file == "" then
  decline("missing-input", "There is no submitted file to run.")
  return
end

local binary = app.temp_dir() .. "/program"
if request.os and request.os.family == "windows" then binary = binary .. ".exe" end
local build_args = { file, "-o", binary }
if request.os and request.os.family == "windows" then
  build_args[#build_args + 1] = "-static"
end
local started, build = pcall(run, "gcc", build_args)
if not started then
  fail("program-error", "The compiler could not be started.", tostring(build))
  return
end
if build.code == -1 then
  timeout("runtime", "The compiler timed out.", build.stderr)
  return
end
if build.code ~= 0 then
  fail("program-error", "The program did not compile.", build.stderr)
  return
end
local args = {}
if input_file ~= "" then args[#args + 1] = input_file end
local ran, output = pcall(app.run_command, binary, args, "")
if not ran then
  fail("program-error", "The compiled program could not be started.", tostring(output))
  return
end

if output.code == -1 then
  timeout("runtime", "The program timed out.", output.stderr)
  return
end
if output.code ~= 0 then
  fail("program-error", "The program stopped with an error.", output.stderr)
  return
end
if request.mode == "preview" then
  app.result({
    status = "previewed",
    text = output.stdout or "",
  })
  return
end
if normalise(expected) == "" then
  decline(
    "missing-key",
    "The key has no expected output to compare with.",
    output.stdout
  )
  return
end
local same = normalise(output.stdout) == normalise(expected)
app.result({
  status = "graded",
  score = same and max_points or 0,
  comment = same and "The output matches the expected answer." or "The output does not match the expected answer.",
  rationale = same and "Printed output matched the key." or "Printed output differed from the key.",
  text = output.stdout or "",
  output = {
    kind = "diff",
    title = "Program output",
    expected = expected,
    actual = output.stdout or "",
    expectedLabel = "Expected",
    actualLabel = "Actual",
  },
})
