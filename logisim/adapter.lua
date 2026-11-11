local settings = request.settings or {}
local context = request.context or {}
local values = context.values or {}
local expected = values.table or context.expected or ""
local max_points = tonumber(context.maxPoints) or 0
local program = settings.programPath
if not program or program == "" then program = "logisim-evolution" end

local function rows(text)
  local out = {}
  if not text then return out end
  for raw in (text:gsub("\r\n", "\n") .. "\n"):gmatch("(.-)\n") do
    local line = raw:gsub("|", " ")
    line = line:gsub("%s+", " "):match("^%s*(.-)%s*$")
    local lower = line:lower()
    if line ~= "" and line:sub(1, 1) ~= "#" and not lower:find("truth table", 1, true) and not line:match("^[%-|+= ]+$") then
      -- Logisim prints a pin-name header before the rows. Only lines made of
      -- binary cells are table rows; names and warnings are not.
      if line:match("^[01%s]+$") then
        out[#out + 1] = line:upper()
      end
    end
  end
  return out
end

local output = app.run_command(program, { "-tty", "table", request.filePath }, "")
if output.code ~= 0 then
  result = { error = (output.stderr ~= "" and output.stderr) or "Logisim failed.", text = output.stdout or "" }
  return
end
if request.mode == "preview" then
  result = { text = output.stdout or "" }
  return
end
local actual = rows(output.stdout)
local wanted = rows(expected)
local same = #actual == #wanted
if same then
  for i = 1, #actual do
    if actual[i] ~= wanted[i] then same = false break end
  end
end
result = {
  score = same and max_points or 0,
  comment = same and "The generated truth table matches the key." or "The generated truth table differs from the key.",
  rationale = same and "Every truth-table row matched." or "One or more truth-table rows differed.",
  text = output.stdout or "",
}
