$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location -LiteralPath $root

$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pythonLauncher) {
    $systemPython = (Get-Command py).Source
    $pythonArgs = @('-3', '-m', 'venv', (Join-Path $root '.venv'))
    $versionOutput = & $systemPython -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($LASTEXITCODE -ne 0 -or $versionOutput -notmatch '^\d+\.\d+$') { $pythonLauncher = $null }
}
if (-not $pythonLauncher) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) { throw 'Python 3.10 or newer is required. Install Python from python.org, then run this launcher again.' }
    $systemPython = $pythonCommand.Source
    $pythonArgs = @('-m', 'venv', (Join-Path $root '.venv'))
    $versionOutput = & $systemPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0 -or $versionOutput -notmatch '^\d+\.\d+$') { throw 'Python could not start. Install Python 3.10 or newer and try again.' }
}

$version = [version]"$versionOutput.0"
if ($version -lt [version]'3.10.0') { throw "Python 3.10 or newer is required; found $versionOutput." }

$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host 'Preparing the isolated MANTIS environment...'
    & $systemPython @pythonArgs
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
}

$requirementsHash = (Get-FileHash -LiteralPath (Join-Path $root 'requirements.txt') -Algorithm SHA256).Hash
$installedHashFile = Join-Path $root '.venv\requirements.sha256'
$installedHash = if (Test-Path -LiteralPath $installedHashFile) { (Get-Content -Raw -LiteralPath $installedHashFile).Trim() } else { '' }
if ($requirementsHash -ne $installedHash) {
    Write-Host 'Installing or updating MANTIS dependencies (first run only, or after requirements change)...'
    & $venvPython -m pip install --disable-pip-version-check -r (Join-Path $root 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the Python/pip output and network connection, then run the launcher again.' }
    Set-Content -LiteralPath $installedHashFile -Value $requirementsHash -NoNewline
}

$port = 8000
$baseUrl = "http://127.0.0.1:$port"
$healthUrl = "$baseUrl/api/health"
try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($health.status -eq 'ok') {
        Write-Host "MANTIS is already running at $baseUrl"
        Start-Process $baseUrl
        exit 0
    }
} catch { }

$listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) { throw "Port $port is already in use by another application. Close it or change the port in start_mantis.ps1." }

$runtimeDir = Join-Path $root '.mantis-runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$stdoutPath = Join-Path $runtimeDir 'server-out.log'
$stderrPath = Join-Path $runtimeDir 'server-error.log'
$pidPath = Join-Path $runtimeDir 'server.pid'
$server = Start-Process -FilePath $venvPython `
    -ArgumentList @('-m', 'uvicorn', 'mantis.api.app:app', '--host', '127.0.0.1', '--port', "$port") `
    -WorkingDirectory $root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
Set-Content -LiteralPath $pidPath -Value $server.Id -NoNewline

Write-Host 'Starting the local MANTIS server and checking readiness...'
$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    if ($server.HasExited) { break }
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        if ($health.status -eq 'ok') { $ready = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 500
}

if (-not $ready) {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue }
    $details = if (Test-Path -LiteralPath $stderrPath) { Get-Content -Raw -LiteralPath $stderrPath } else { '' }
    throw "MANTIS did not become ready. Server output: $details"
}

Write-Host "MANTIS is ready at $baseUrl"
Write-Host 'Use stop_mantis.bat to stop the local server.'
Start-Process $baseUrl
