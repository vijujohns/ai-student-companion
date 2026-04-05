param(
    [switch]$Start,
    [switch]$Stop,
    [switch]$Interactive,
    [switch]$DebugMode,
    [switch]$Background,
    [switch]$SkipReindex,
    [switch]$FullReindex,
    [switch]$IncrementalReindex,
    [ValidateSet('incremental', 'full', 'skip')]
    [string]$ReindexMode,
    [switch]$ForceKillExisting,
    [switch]$NoLogWindow,
    [switch]$Help,
    [int]$TailLines = 500
)

$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$backendDir = Join-Path $repoRoot "v3\backend"
$frontendDir = Join-Path $repoRoot "v3\frontend"
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$logsDir = Join-Path $repoRoot "v3\logs"
$backendLog = Join-Path $logsDir "backend-dev.log"
$frontendLog = Join-Path $logsDir "frontend-dev.log"
$combinedLog = Join-Path $logsDir "dev-console.log"
$debugLog = Join-Path $logsDir "debug.log"
$stateFile = Join-Path $logsDir "dev-run-state.json"

function Show-Usage {
    Write-Host "Usage:" -ForegroundColor Cyan
    Write-Host "  .\start-dev.ps1                                  # interactive launcher"
    Write-Host "  .\start-dev.ps1 -Start -DebugMode -ReindexMode full"
    Write-Host "  .\start-dev.ps1 -Start -Background -ReindexMode incremental"
    Write-Host "  .\start-dev.ps1 -Start -SkipReindex"
    Write-Host "  .\start-dev.ps1 -Stop"
    Write-Host ""
    Write-Host "What it does:" -ForegroundColor Cyan
    Write-Host "  - checks ports 3000 and 8000"
    Write-Host "  - asks before killing existing processes"
    Write-Host "  - prompts for debug/background and reindex mode"
    Write-Host "  - opens a live log window with tail 500"
    Write-Host "  - can stop the application gracefully"
    Write-Host ""
    Write-Host "Key options:" -ForegroundColor Cyan
    Write-Host "  -Start             Start the app immediately"
    Write-Host "  -Stop              Stop the running app and close launcher windows"
    Write-Host "  -DebugMode         Enable backend debug logging"
    Write-Host "  -Background        Start backend/frontend minimized in the background"
    Write-Host "  -ReindexMode       Choose: incremental, full, or skip"
    Write-Host "  -FullReindex       Force a fresh rebuild of every indexed file"
    Write-Host "  -IncrementalReindex Only index new/changed/unindexed files"
    Write-Host "  -SkipReindex       Skip backend startup reindex entirely"
    Write-Host "  -ForceKillExisting Kill existing listeners on ports 3000/8000 without prompting"
    Write-Host "  -NoLogWindow       Do not open the live log tail window"
    Write-Host "  -TailLines 500     Number of log lines to show in the log window"
}

function Ensure-Paths {
    if (-not (Test-Path $pythonExe)) {
        throw "Python virtual environment not found at '$pythonExe'."
    }
    if (-not (Test-Path (Join-Path $backendDir "run.py"))) {
        throw "Backend entrypoint not found at '$backendDir\run.py'."
    }
    if (-not (Test-Path (Join-Path $frontendDir "package.json"))) {
        throw "Frontend package.json not found at '$frontendDir\package.json'."
    }

    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
}

function Escape-PSLiteral {
    param([string]$Value)
    return $Value.Replace("'", "''")
}

function Read-YesNo {
    param(
        [string]$Prompt,
        [bool]$Default = $true
    )

    $suffix = if ($Default) { "[Y/n]" } else { "[y/N]" }
    while ($true) {
        $answer = Read-Host "$Prompt $suffix"
        if ([string]::IsNullOrWhiteSpace($answer)) {
            return $Default
        }

        switch ($answer.Trim().ToLowerInvariant()) {
            "y" { return $true }
            "yes" { return $true }
            "n" { return $false }
            "no" { return $false }
            default { Write-Host "Please enter Y or N." -ForegroundColor Yellow }
        }
    }
}

function Read-LauncherAction {
    while ($true) {
        $choice = Read-Host "Choose action: [S]tart, S[t]op, or [Q]uit"
        switch ($choice.Trim().ToLowerInvariant()) {
            "" { return "start" }
            "s" { return "start" }
            "start" { return "start" }
            "t" { return "stop" }
            "stop" { return "stop" }
            "q" { return "quit" }
            "quit" { return "quit" }
            default { Write-Host "Please choose Start, Stop, or Quit." -ForegroundColor Yellow }
        }
    }
}

function Resolve-ReindexMode {
    if ($SkipReindex) {
        return "skip"
    }
    if ($FullReindex) {
        return "full"
    }
    if ($IncrementalReindex) {
        return "incremental"
    }
    if ($ReindexMode) {
        return $ReindexMode.ToLowerInvariant()
    }
    return "skip"
}

function Read-ReindexModeChoice {
    while ($true) {
        Write-Host "Reindex mode options:" -ForegroundColor Cyan
        Write-Host "  [1] Full rebuild      - clear old index data and reindex every file"
        Write-Host "  [2] Incremental sync  - index only new/changed/unindexed files"
        Write-Host "  [3] Skip on startup   - do not run backend reindex now (default)"

        $choice = Read-Host "Choose reindex mode [1/2/3]"
        switch ($choice.Trim().ToLowerInvariant()) {
            "" { return "skip" }
            "1" { return "full" }
            "full" { return "full" }
            "2" { return "incremental" }
            "incremental" { return "incremental" }
            "3" { return "skip" }
            "skip" { return "skip" }
            default { Write-Host "Please choose 1, 2, or 3." -ForegroundColor Yellow }
        }
    }
}

function Get-PortOwners {
    param([int[]]$Ports)

    $results = @()
    foreach ($port in $Ports) {
        $pids = @()
        try {
            $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
                Select-Object -ExpandProperty OwningProcess -Unique
        } catch {
            $netstatLines = netstat -ano -p tcp | Select-String -Pattern ":$port\s+.*LISTENING\s+(\d+)$"
            foreach ($line in $netstatLines) {
                if ($line.Matches.Count -gt 0) {
                    $pids += [int]$line.Matches[0].Groups[1].Value
                }
            }
        }

        foreach ($pidValue in ($pids | Sort-Object -Unique)) {
            if (-not $pidValue) {
                continue
            }

            $processName = "<unknown>"
            try {
                $processName = (Get-Process -Id ([int]$pidValue) -ErrorAction Stop).ProcessName
            } catch {
            }

            $results += [PSCustomObject]@{
                Port        = [int]$port
                Pid         = [int]$pidValue
                ProcessName = $processName
            }
        }
    }

    return $results | Sort-Object Port, Pid -Unique
}

function Get-TrackedPids {
    $pids = @()
    if (Test-Path $stateFile) {
        try {
            $state = Get-Content -Path $stateFile -Raw | ConvertFrom-Json
            foreach ($value in @($state.backendPid, $state.frontendPid, $state.logPid)) {
                if ($null -ne $value -and "$value".Trim()) {
                    $pids += [int]$value
                }
            }
        } catch {
            Write-Host "Ignoring unreadable launcher state file at '$stateFile'." -ForegroundColor Yellow
        }
    }

    return $pids | Sort-Object -Unique
}

function Get-LauncherShellPids {
    $pids = @()
    $shells = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" -ErrorAction SilentlyContinue
    foreach ($shell in $shells) {
        $commandLine = [string]$shell.CommandLine
        if (-not $commandLine) {
            continue
        }

        $isManagedLauncherWindow =
            ($commandLine -match [regex]::Escape($repoRoot)) -and
            ($commandLine -match 'run\.py|npm run dev -- --host 0\.0\.0\.0 --port 3000 --strictPort|backend-dev\.log|frontend-dev\.log|debug\.log|dev-console\.log')

        if ($isManagedLauncherWindow -and [int]$shell.ProcessId -ne $PID) {
            $pids += [int]$shell.ProcessId
        }
    }

    return $pids | Sort-Object -Unique
}

function Stop-ProcessesById {
    param([int[]]$ProcessIds)

    foreach ($processId in ($ProcessIds | Sort-Object -Unique)) {
        if (-not $processId) {
            continue
        }

        try {
            $proc = Get-Process -Id $processId -ErrorAction Stop
        } catch {
            continue
        }

        Write-Host "Closing $($proc.ProcessName) (PID $processId)..." -ForegroundColor Yellow
        $closed = $false

        try {
            if ($proc.MainWindowHandle -ne 0) {
                $null = $proc.CloseMainWindow()
                $closed = $proc.WaitForExit(8000)
            }
        } catch {
        }

        if (-not $closed) {
            try {
                Stop-Process -Id $processId -ErrorAction SilentlyContinue
                Wait-Process -Id $processId -Timeout 5 -ErrorAction SilentlyContinue
            } catch {
            }
        }

        try {
            $proc.Refresh()
            if (-not $proc.HasExited) {
                Write-Host "Force stopping PID $processId..." -ForegroundColor DarkYellow
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            }
        } catch {
        }
    }
}

function Stop-DevStack {
    Write-Host "Stopping AI Student Companion..." -ForegroundColor Green

    $trackedPids = Get-TrackedPids
    $launcherShellPids = Get-LauncherShellPids
    $portOwners = Get-PortOwners -Ports @(3000, 8000)
    $portPids = @($portOwners | Select-Object -ExpandProperty Pid)
    $allPids = @($trackedPids + $launcherShellPids + $portPids) | Where-Object { $_ } | Sort-Object -Unique

    if (-not $allPids -or $allPids.Count -eq 0) {
        Write-Host "No running launcher processes were found on ports 3000/8000." -ForegroundColor Yellow
        Remove-Item -Path $stateFile -Force -ErrorAction SilentlyContinue
        return
    }

    Stop-ProcessesById -ProcessIds $allPids
    Remove-Item -Path $stateFile -Force -ErrorAction SilentlyContinue

    Write-Host "Stop sequence finished." -ForegroundColor Green
}

function Start-DevStack {
    $selectedReindexMode = Resolve-ReindexMode
    $owners = Get-PortOwners -Ports @(3000, 8000)
    if ($owners -and $owners.Count -gt 0) {
        Write-Host "Detected existing listeners on ports 3000/8000:" -ForegroundColor Yellow
        ($owners | Format-Table Port, Pid, ProcessName -AutoSize | Out-String).TrimEnd() | Write-Host

        $shouldKill = $ForceKillExisting
        if (-not $ForceKillExisting) {
            $shouldKill = Read-YesNo -Prompt "Kill these processes before starting?" -Default $false
        }

        if (-not $shouldKill) {
            throw "Startup cancelled because ports 3000/8000 are still in use."
        }

        $relatedShellPids = Get-LauncherShellPids
        Stop-ProcessesById -ProcessIds (@($owners | Select-Object -ExpandProperty Pid) + $relatedShellPids)

        $portsCleared = $false
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            $remainingOwners = Get-PortOwners -Ports @(3000, 8000)
            if (-not $remainingOwners -or $remainingOwners.Count -eq 0) {
                $portsCleared = $true
                break
            }
            [System.Threading.Thread]::Sleep(500)
        }

        if (-not $portsCleared) {
            throw "Ports 3000/8000 are still busy after the stop attempt. Please close them manually and try again."
        }
    }

    $launchStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    @(
        "=== AI Student Companion launch: $launchStamp ===",
        "DebugMode=$DebugMode | Background=$Background | ReindexMode=$selectedReindexMode",
        "BackendCLI=run.py --reindex=$selectedReindexMode"
    ) | Set-Content -Path $combinedLog -Encoding UTF8
    "=== Backend launch: $launchStamp ===" | Set-Content -Path $backendLog -Encoding UTF8
    "=== Frontend launch: $launchStamp ===" | Set-Content -Path $frontendLog -Encoding UTF8

    $backendDirEsc = Escape-PSLiteral $backendDir
    $frontendDirEsc = Escape-PSLiteral $frontendDir
    $logsDirEsc = Escape-PSLiteral $logsDir
    $pythonExeEsc = Escape-PSLiteral $pythonExe
    $backendLogEsc = Escape-PSLiteral $backendLog
    $frontendLogEsc = Escape-PSLiteral $frontendLog
    $combinedLogEsc = Escape-PSLiteral $combinedLog
    $debugLogEsc = Escape-PSLiteral $debugLog

    $debugValue = if ($DebugMode) { "1" } else { "0" }
    $skipValue = if ($selectedReindexMode -eq 'skip') { "1" } else { "" }

    $backendCommand = @"
try { `$Host.UI.RawUI.WindowTitle = 'AI Student Companion Backend' } catch {}
`$ErrorActionPreference = 'Stop'
`$env:APP_ENV = 'development'
`$env:PYTHONIOENCODING = 'utf-8'
`$env:BACKEND_BIND_HOST = '0.0.0.0'
`$env:BACKEND_PORT = '8000'
`$env:DEBUG_LOGGING = '$debugValue'
`$env:DEBUG_LOG_FILE = '$debugLogEsc'
`$env:KB_REINDEX_MODE = '$selectedReindexMode'
if ('$skipValue') { `$env:SKIP_KB_REINDEX = '$skipValue' } else { Remove-Item Env:SKIP_KB_REINDEX -ErrorAction SilentlyContinue }
Set-Location '$backendDirEsc'
Start-Transcript -Path '$backendLogEsc' -Append | Out-Null
try {
    & '$pythonExeEsc' 'run.py' '--reindex=$selectedReindexMode'
} finally {
    try { Stop-Transcript | Out-Null } catch {}
}
"@

    $frontendCommand = @"
try { `$Host.UI.RawUI.WindowTitle = 'AI Student Companion Frontend' } catch {}
`$ErrorActionPreference = 'Stop'
`$env:BROWSER = 'none'
Set-Location '$frontendDirEsc'
Start-Transcript -Path '$frontendLogEsc' -Append | Out-Null
try {
    npm run dev -- --host 0.0.0.0 --port 3000 --strictPort
} finally {
    try { Stop-Transcript | Out-Null } catch {}
}
"@

    $logCommand = @"
try { `$Host.UI.RawUI.WindowTitle = 'AI Student Companion Logs' } catch {}
Set-Location '$logsDirEsc'
Write-Host 'Showing the latest $TailLines log lines. Press Ctrl+C or close this window when done.' -ForegroundColor Cyan
Get-Content -LiteralPath @('$backendLogEsc', '$frontendLogEsc', '$debugLogEsc') -Tail $TailLines -Wait
"@

    $windowStyle = if ($Background) { "Minimized" } else { "Normal" }
    $backendEncoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($backendCommand))
    $frontendEncoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($frontendCommand))
    $logEncoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($logCommand))

    $backendArgs = if ($Background) {
        @('-NoLogo', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $backendEncoded)
    } else {
        @('-NoLogo', '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $backendEncoded)
    }
    $frontendArgs = if ($Background) {
        @('-NoLogo', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $frontendEncoded)
    } else {
        @('-NoLogo', '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $frontendEncoded)
    }

    Write-Host "Starting AI Student Companion..." -ForegroundColor Green
    Write-Host "  Frontend -> http://127.0.0.1:3000"
    Write-Host "  Backend  -> http://127.0.0.1:8000"
    Write-Host "  Debug mode    -> $(if ($DebugMode) { 'ON' } else { 'OFF' })"
    Write-Host "  Background    -> $(if ($Background) { 'ON (minimized)' } else { 'OFF' })"
    Write-Host "  Reindex mode  -> $selectedReindexMode"
    Write-Host ""

    $backendProc = Start-Process -FilePath "powershell.exe" -ArgumentList $backendArgs -WorkingDirectory $backendDir -WindowStyle $windowStyle -PassThru
    $frontendProc = Start-Process -FilePath "powershell.exe" -ArgumentList $frontendArgs -WorkingDirectory $frontendDir -WindowStyle $windowStyle -PassThru

    $logProc = $null
    if (-not $NoLogWindow) {
        $logProc = Start-Process -FilePath "powershell.exe" -ArgumentList @('-NoLogo', '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $logEncoded) -WorkingDirectory $logsDir -WindowStyle Normal -PassThru
    }

    [ordered]@{
        startedAt = (Get-Date).ToString('o')
        backendPid = $backendProc.Id
        frontendPid = $frontendProc.Id
        logPid = if ($logProc) { $logProc.Id } else { $null }
        debugMode = [bool]$DebugMode
        background = [bool]$Background
        skipReindex = [bool]($selectedReindexMode -eq 'skip')
        reindexMode = $selectedReindexMode
        backendLog = $backendLog
        frontendLog = $frontendLog
        combinedLog = $combinedLog
    } | ConvertTo-Json | Set-Content -Path $stateFile -Encoding UTF8

    Write-Host "Backend PID : $($backendProc.Id)" -ForegroundColor Cyan
    Write-Host "Frontend PID: $($frontendProc.Id)" -ForegroundColor Cyan
    if ($logProc) {
        Write-Host "Log window PID: $($logProc.Id)" -ForegroundColor Cyan
    }

    if ($Background) {
        Write-Host "Services were started in background mode (minimized windows)." -ForegroundColor Yellow
    } else {
        Write-Host "Backend, frontend, and log windows were opened." -ForegroundColor Yellow
    }
}

if ($Help) {
    Show-Usage
    exit 0
}

Ensure-Paths

$explicitActionRequested = $PSBoundParameters.ContainsKey('Start') -or $PSBoundParameters.ContainsKey('Stop') -or
    $PSBoundParameters.ContainsKey('DebugMode') -or $PSBoundParameters.ContainsKey('Background') -or
    $PSBoundParameters.ContainsKey('SkipReindex') -or $PSBoundParameters.ContainsKey('FullReindex') -or
    $PSBoundParameters.ContainsKey('IncrementalReindex') -or $PSBoundParameters.ContainsKey('ReindexMode') -or
    $PSBoundParameters.ContainsKey('ForceKillExisting') -or $PSBoundParameters.ContainsKey('NoLogWindow')

if (-not $explicitActionRequested) {
    $Interactive = $true
}

if ($Interactive) {
    Write-Host "AI Student Companion Launcher" -ForegroundColor Green
    Write-Host "Repository: $repoRoot" -ForegroundColor DarkGray
    Write-Host ""

    $action = Read-LauncherAction
    switch ($action) {
        "quit" { exit 0 }
        "stop" { $Stop = $true }
        default {
            $Start = $true
            $DebugMode = Read-YesNo -Prompt "Start in debug mode?" -Default $false
            $Background = Read-YesNo -Prompt "Run in background mode (minimized windows)?" -Default $false
            $ReindexMode = Read-ReindexModeChoice
            $SkipReindex = $ReindexMode -eq 'skip'
            $FullReindex = $ReindexMode -eq 'full'
            $IncrementalReindex = $ReindexMode -eq 'incremental'
        }
    }
}

if ($Stop) {
    Stop-DevStack
    exit 0
}

if (-not $Start) {
    $Start = $true
}

Start-DevStack
