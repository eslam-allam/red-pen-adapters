local settings = request.settings or {}
local context = request.context or {}
local values = context.values or {}
local expected = values.expected or context.expected or ""
local max_points = tonumber(context.maxPoints) or 0
local version = settings.pythonVersion or "3.12"
local packages = {}
local raw = settings.packages or ""
for item in tostring(raw):gsub(",", "\n"):gmatch("[^\n]+") do
  local clean = item:match("^%s*(.-)%s*$")
  if clean ~= "" then packages[#packages + 1] = clean end
end

local function normalise(text)
  if not text then return "" end
  local lines = {}
  for line in (text:gsub("\r\n", "\n") .. "\n"):gmatch("(.-)\n") do
    lines[#lines + 1] = (line:gsub("%s+$", ""))
  end
  while #lines > 0 and lines[#lines] == "" do table.remove(lines) end
  return table.concat(lines, "\n"):match("^%s*(.-)%s*$")
end

local dir = app.temp_dir()
local windows = package.config:sub(1, 1) == "\\"
local venv = dir .. (windows and "\\venv" or "/venv")
local python = venv .. (windows and "\\Scripts\\python.exe" or "/bin/python")
local made = app.run_runtime("python", version, "python", { "-m", "venv", venv }, "")
local runner = python
if made.code ~= 0 then
  runner = nil
end
if runner and #packages > 0 then
  local args = { "-m", "pip", "install", "--disable-pip-version-check", "--no-input" }
  for _, package in ipairs(packages) do args[#args + 1] = package end
  local installed = app.run_command(runner, args, "")
  if installed.code ~= 0 then
    result = { score = 0, comment = "A package could not be installed.\n\n" .. (installed.stderr or ""), rationale = "Package installation failed.", text = "" }
    return
  end
end
local output
if runner then
  output = app.run_command(runner, { request.filePath }, "")
else
  output = app.run_runtime("python", version, "python", { request.filePath }, "")
end
if output.code ~= 0 then
  result = { score = 0, comment = "The program stopped with an error.\n\n" .. (output.stderr or ""), rationale = "Python exited with an error.", text = output.stdout or "" }
  return
end
if request.mode == "preview" then
  result = { text = output.stdout or "", rationale = "Python ran successfully." }
  return
end
if normalise(expected) == "" then
  result = { score = 0, comment = "The key has no expected output to compare with.", rationale = "No expected output.", text = output.stdout or "" }
  return
end
local same = normalise(output.stdout) == normalise(expected)
result = {
  score = same and max_points or 0,
  comment = same and "The output matches the expected answer." or "The output does not match the expected answer.",
  rationale = same and "Printed output matched the key." or "Printed output differed from the key.",
  text = output.stdout or "",
}
