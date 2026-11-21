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

-- A failed run, missing key or timeout leaves the question unmarked. It must
-- never return score = 0: that would silently record a wrong answer.
local function fail(message, detail, text)
  local rationale = message
  if detail and detail ~= "" then rationale = message .. "\n\n" .. detail end
  app.result({
    error = rationale,
    comment = message,
    rationale = rationale,
    text = text or "",
  })
end

local function run(program, args)
  return app.run_runtime(tool, version, program, args or {}, "")
end

local question = context.questionValues or {}
local input_file = (question.inputFile or ""):match("^%s*(.-)%s*$")

local args = { "run", file }
if input_file ~= "" then args[#args + 1] = input_file end
local started, output = pcall(run, "dart", args)
if not started then
  fail("The program could not be started or timed out.", tostring(output), "")
  return
end

if output.code ~= 0 then
  fail("The program stopped with an error.", output.stderr, output.stdout)
  return
end
if request.mode == "preview" then
  app.result({ text = output.stdout or "", rationale = "Program ran successfully." })
  return
end
if normalise(expected) == "" then
  fail("The key has no expected output to compare with.", nil, output.stdout)
  return
end
local same = normalise(output.stdout) == normalise(expected)
app.result({
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
