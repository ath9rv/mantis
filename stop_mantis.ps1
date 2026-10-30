$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pidPath = Join-Path $root '.mantis-runtime\server.pid'
if (-not (Test-Path -LiteralPath $pidPath)) {
    Write-Host 'No MANTIS server is recorded as running.'
    exit 0
}

$serverPid = [int](Get-Content -Raw -LiteralPath $pidPath)
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid" -ErrorAction SilentlyContinue
if (-not $process) {
    Remove-Item -LiteralPath $pidPath -Force
    Write-Host 'The recorded MANTIS server has already stopped.'
    exit 0
}

$expectedPython = [IO.Path]::GetFullPath((Join-Path $root '.venv\Scripts\python.exe'))
$actualPython = [IO.Path]::GetFullPath($process.ExecutablePath)
if ($actualPython -ne $expectedPython -or $process.CommandLine -notlike '*mantis.api.app:app*') {
    throw 'The recorded process does not match this MANTIS workspace; it was left untouched.'
}

Stop-Process -Id $serverPid
Remove-Item -LiteralPath $pidPath -Force
Write-Host 'MANTIS stopped.'
