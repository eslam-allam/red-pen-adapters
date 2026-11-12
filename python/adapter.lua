local settings = request.settings or {}
local context = request.context or {}
local values = context.values or {}
local expected = values.expected or context.expected or ""
local max_points = tonumber(context.maxPoints) or 0
local version = settings.pythonVersion or "3.12"
-- The app downloads the Python runtime and any packages from the settings,
-- then hands the adapter the prepared interpreter. The adapter never needs
-- network access or runs pip itself.
local runtime = request.runtime or {}
local runner = runtime.program

local function normalise(text)
  if not text then return "" end
  local lines = {}
  for line in (text:gsub("\r\n", "\n") .. "\n"):gmatch("(.-)\n") do
    lines[#lines + 1] = (line:gsub("%s+$", ""))
  end
  while #lines > 0 and lines[#lines] == "" do table.remove(lines) end
  return table.concat(lines, "\n"):match("^%s*(.-)%s*$")
end

local output
if runner and runner ~= "" then
  output = app.run_command(runner, { request.filePath }, "")
else
  output = app.run_runtime("python", runtime.version or version, "python", { request.filePath }, "")
end
if output.code ~= 0 then
  app.result({ score = 0, comment = "The program stopped with an error.\n\n" .. (output.stderr or ""), rationale = "Python exited with an error.", text = output.stdout or "" })
  return
end
if request.mode == "preview" then
  app.result({ text = output.stdout or "", rationale = "Python ran successfully." })
  return
end
if normalise(expected) == "" then
  app.result({ score = 0, comment = "The key has no expected output to compare with.", rationale = "No expected output.", text = output.stdout or "" })
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
