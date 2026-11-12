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

-- Matches the circuit's columns to the key by name when both name their
-- columns. Returns the index of the actual column for each key column, or nil
-- when the names cannot be matched.
local function column_order(actual_headers, wanted_headers)
  if #wanted_headers == 0 or #actual_headers == 0 then return nil end
  if #actual_headers ~= #wanted_headers then return nil end
  local by_name = {}
  for index, name in ipairs(actual_headers) do
    local key = name:upper()
    if by_name[key] then return nil end
    by_name[key] = index
  end
  local order = {}
  for index, name in ipairs(wanted_headers) do
    local at = by_name[name:upper()]
    if not at then return nil end
    order[index] = at
  end
  return order
end

-- Builds the table shown to the instructor: the circuit's own values, with
-- every cell that differs from the key marked.
local function build_table(actual_headers, actual, wanted_headers, wanted)
  local order = column_order(actual_headers, wanted_headers)
  local names_mismatch = #wanted_headers > 0 and order == nil
  local columns = {}
  if order and #wanted_headers > 0 then
    columns = wanted_headers
  elseif #actual_headers > 0 then
    columns = actual_headers
  elseif #wanted_headers > 0 then
    columns = wanted_headers
  else
    local width = 0
    for _, row in ipairs(wanted) do width = math.max(width, #row) end
    for _, row in ipairs(actual) do width = math.max(width, #row) end
    for index = 1, width do columns[index] = tostring(index) end
  end

  local rows = {}
  local mismatched_rows = {}
  local mismatched_cells = {}
  local row_count = math.max(#actual, #wanted)
  for row_index = 1, row_count do
    local actual_row = actual[row_index]
    local wanted_row = wanted[row_index]
    local cells = {}
    for column_index = 1, #columns do
      local value = "—"
      if actual_row then
        local at = order and order[column_index] or column_index
        if actual_row[at] ~= nil then value = actual_row[at] end
      end
      cells[column_index] = value
    end
    if names_mismatch or not actual_row or not wanted_row then
      mismatched_rows[#mismatched_rows + 1] = row_index - 1
    else
      for column_index = 1, #columns do
        local at = order and order[column_index] or column_index
        local actual_value = actual_row[at]
        local wanted_value = wanted_row[column_index]
        if actual_value ~= wanted_value then
          mismatched_cells[#mismatched_cells + 1] = {
            row = row_index - 1,
            column = column_index - 1,
          }
        end
      end
    end
    rows[#rows + 1] = cells
  end
  return columns, rows, mismatched_rows, mismatched_cells
end

local output = app.run_command(program, { "-tty", "table", request.filePath }, "")
if output.code ~= 0 then
  app.result({ error = (output.stderr ~= "" and output.stderr) or "Logisim failed.", text = output.stdout or "" })
  return
end
if request.mode == "preview" then
  app.result({ text = output.stdout or "" })
  return
end

local actual_headers, actual = parse_table(output.stdout)
local wanted_headers, wanted = parse_table(expected)
if #wanted == 0 then
  app.result({
    score = 0,
    comment = "The key has no truth-table rows.",
    rationale = "Fill every output cell in the key table before grading.",
    text = output.stdout or "",
  })
  return
end
local order = column_order(actual_headers, wanted_headers)
local same = #actual == #wanted
if same then
  for row = 1, #wanted do
    if #actual[row] ~= #wanted[row] then
      same = false
      break
    end
    for column = 1, #wanted[row] do
      local value = order and actual[row][order[column]] or actual[row][column]
      if value ~= wanted[row][column] then
        same = false
        break
      end
    end
    if not same then break end
  end
end
-- A key with headers cannot be compared when the circuit's names are
-- different, even if the values happen to line up by position.
if #wanted_headers > 0 and order == nil then same = false end

local columns, rows, mismatched_rows, mismatched_cells =
  build_table(actual_headers, actual, wanted_headers, wanted)
local table_output = {
  kind = "table",
  title = "Truth table",
  columns = columns,
  rows = rows,
  mismatchedRows = mismatched_rows,
  mismatchedCells = mismatched_cells,
}

if same then
  app.result({
    score = max_points,
    comment = "The generated truth table matches the key.",
    rationale = #wanted_headers > 0
      and "Every row matched after the columns were matched by name."
      or "Every truth-table row matched.",
    text = output.stdout or "",
    output = table_output,
  })
  return
end
local comment = "The generated truth table differs from the key."
local rationale = "One or more truth-table rows differed."
if #wanted_headers > 0 and order == nil then
  comment = "The circuit's column names do not match the key."
  rationale = "Match the input and output names in the key to the names in the circuit."
elseif #actual ~= #wanted then
  rationale = "The circuit produced a different number of truth-table rows."
elseif #mismatched_cells > 0 then
  rationale = "The highlighted cells do not match the key."
end
app.result({
  score = 0,
  comment = comment,
  rationale = rationale,
  text = output.stdout or "",
  output = table_output,
})
