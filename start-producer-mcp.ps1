$ErrorActionPreference = 'Stop'
$env:ABLETON_PRODUCER_HOME = Join-Path $PSScriptRoot '.producer'
$producerPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $producerPython)) {
    throw 'Create the Python 3 virtual environment and install .[producer] as described in PRODUCER.md.'
}
& $producerPython -m MCP_Server.server
exit $LASTEXITCODE
