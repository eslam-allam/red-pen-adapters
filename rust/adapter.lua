-- Generic language adapter: the app runs it in its embedded Lua runtime.
local settings = request.settings or {}
local context = request.context or {}
local values = context.values or {}
local expected = values.expected or context.expected or ""
local max_points = tonumber(context.maxPoints) or 0
local version = (request.runtime and request.runtime.version) or settings.runtimeVersion or "latest"
local file = request.filePath
local language = manifest.language or ""

local function normalise(text)
  if not text then return "" end
  local lines = {}
  for line in (text:gsub("\r\n", "\n") .. "\n"):gmatch("(.-)\n") do
    lines[#lines + 1] = (line:gsub("%s+$", ""))
  end
  while #lines > 0 and lines[#lines] == "" do table.remove(lines) end
  return table.concat(lines, "\n"):match("^%s*(.-)%s*$")
end

local function fail(message, text)
  app.result({ score = 0, comment = message, rationale = message, text = text or "" })
end

local commands = {
  javascript = { "node", { file } },
  typescript = { "npx", { "--yes", "tsx", file } },
  ruby = { "ruby", { file } },
  php = { "php", { file } },
  go = { "go", { "run", file } },
  java = { "java", { file } },
  kotlin = { "kotlinc", { "-script", file } },
  csharp = { "dotnet", { "script", file } },
  fsharp = { "dotnet", { "fsi", file } },
  swift = { "swift", { file } },
  lua = { "lua", { file } },
  r = { "Rscript", { file } },
  julia = { "julia", { file } },
  haskell = { "runghc", { file } },
  elixir = { "elixir", { file } },
  erlang = { "escript", { file } },
  dart = { "dart", { "run", file } },
  scala = { "scala", { file } },
  perl = { "perl", { file } },
  bash = { "bash", { file } },
  powershell = { "pwsh", { "-NoLogo", "-NonInteractive", "-File", file } },
}

local function run(program, args)
  return app.run_runtime(manifest.miseTool or language, version, program, args or {}, "")
end

local output
if language == "rust" or language == "c" or language == "cpp" then
  local binary = app.temp_dir() .. "/program"
  if app.temp_dir():match("\\$") then binary = binary .. ".exe" end
  local compiler = language == "rust" and "rustc" or (language == "c" and "gcc" or "g++")
  local build = run(compiler, { file, "-o", binary })
  if build.code ~= 0 then
    fail("The program did not compile.\n\n" .. (build.stderr or ""), build.stdout)
    return
  end
  output = app.run_command(binary, {}, "")
else
  local spec = commands[language]
  if not spec then
    fail("No command is configured for " .. language .. ".")
    return
  end
  output = run(spec[1], spec[2])
end

if output.code ~= 0 then
  fail("The program stopped with an error.\n\n" .. (output.stderr or ""), output.stdout)
  return
end
if request.mode == "preview" then
  app.result({ text = output.stdout or "", rationale = "Program ran successfully." })
  return
end
if normalise(expected) == "" then
  fail("The key has no expected output to compare with.", output.stdout)
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
