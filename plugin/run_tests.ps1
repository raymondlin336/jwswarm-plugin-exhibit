# Runs the exhibit tests on Python 3.11 with the real openjiuwen framework, like WorkSwarm.
# Uses the AgentStudio venv by default; set EXHIBIT_PYTHON to use another 3.11 interpreter.
# Runs from a temporary folder so openjiuwen's logs/ folder doesn't land in the repo.
$ErrorActionPreference = 'Stop'

$python = $env:EXHIBIT_PYTHON
if (-not $python) { $python = Join-Path $env:USERPROFILE 'AgentStudio\run\venv\Scripts\python.exe' }
if (-not (Test-Path $python)) { throw "Python not found at $python. Set EXHIBIT_PYTHON to a Python 3.11 with openjiuwen installed." }

$tests = Join-Path $PSScriptRoot 'tests'
$work = Join-Path ([IO.Path]::GetTempPath()) 'exhibit-tests'
New-Item -ItemType Directory -Force $work | Out-Null

Push-Location $work
try {
    & $python -X utf8 -m unittest discover -s $tests -t $tests @args
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $code
