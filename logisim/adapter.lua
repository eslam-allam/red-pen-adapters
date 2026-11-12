local settings = request.settings or {}
local context = request.context or {}
local values = context.values or {}
local expected = values.table or context.expected or ""
local max_points = tonumber(context.maxPoints) or 0
local program = settings.programPath
if not program or program == "" then program = "logisim-evolution" end

local function trim(text)
  return (text:gsub("^%s*(.-)%s*$", "%1"))
end

local function tab_cells(text)
  local out = {}
  for raw in (text .. "\t"):gmatch("(.-)\t") do
    out[#out + 1] = trim(raw)
  end
  return out
end

local function word_cells(text)
  local out = {}
  for word in text:gmatch("%S+") do
    out[#out + 1] = word
  end
  return out
end

-- Returns the column names and the binary rows of either a key table or
-- Logisim's table output. Key tables may start with a `# red-pen header:`
-- line; Logisim prints its pin names as the first non-binary line.
local function parse_table(text)
  local headers = {}
  local rows = {}
  if not text then return headers, rows end
  for raw in (text:gsub("\r\n", "\n") .. "\n"):gmatch("(.-)\n") do
    local header_line = trim(raw)
    local header_lower = header_line:lower()
    if header_line ~= "" and header_lower:sub(1, 17) == "# red-pen header:" then
      headers = tab_cells(header_line:sub(18))
    elseif header_line ~= "" then
      local line = trim((raw:gsub("|", " "):gsub("%s+", " ")))
      local lower = line:lower()
      if line:sub(1, 1) ~= "#"
        and not lower:find("truth table", 1, true)
        and not line:match("^[%-|+= ]+$") then
        if line:match("^[01 ]+$") then
          rows[#rows + 1] = word_cells(line)
        elseif #headers == 0 then
          local names = word_cells(line)
          if #names >= 2 then headers = names end
        end
      end
    end
  end
  return headers, rows
end

-- Columns are matched by name when the key names them, so reordering the
-- inputs or outputs does not change the result. Without a key header the old
-- positional comparison is kept.
local function compare(actual_headers, actual, wanted_headers, wanted)
  if #actual ~= #wanted then return false, "row count" end
  local order = nil
  if #wanted_headers > 0 then
    if #actual_headers == 0 then return false, "names" end
    if #actual_headers ~= #wanted_headers then return false, "names" end
    local by_name = {}
    for index, name in ipairs(actual_headers) do
      local key = name:upper()
      if by_name[key] then return false, "names" end
      by_name[key] = index
    end
    order = {}
    for index, name in ipairs(wanted_headers) do
      local at = by_name[name:upper()]
      if not at then return false, "names" end
      order[index] = at
    end
  end
  for row = 1, #wanted do
    if #actual[row] ~= #wanted[row] then return false, "columns" end
    for column = 1, #wanted[row] do
      local value = order and actual[row][order[column]] or actual[row][column]
      if value ~= wanted[row][column] then return false, "row" end
    end
  end
  return true
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

local actual_headers, actual = parse_table(output.stdout)
local wanted_headers, wanted = parse_table(expected)
local same, reason = compare(actual_headers, actual, wanted_headers, wanted)
if same then
  result = {
    score = max_points,
    comment = "The generated truth table matches the key.",
    rationale = #wanted_headers > 0
      and "Every row matched after the columns were matched by name."
      or "Every truth-table row matched.",
    text = output.stdout or "",
  }
  return
end
local comment = "The generated truth table differs from the key."
local rationale = "One or more truth-table rows differed."
if reason == "names" then
  comment = "The circuit's column names do not match the key."
  rationale = "Match the input and output names in the key to the names in the circuit."
elseif reason == "row count" then
  rationale = "The circuit produced a different number of truth-table rows."
elseif reason == "columns" then
  rationale = "A truth-table row has a different number of cells."
end
result = {
  score = 0,
  comment = comment,
  rationale = rationale,
  text = output.stdout or "",
}
