# PSKitTools.psm1
# PowerShell automation tools for PSKit MCP
# Loaded automatically into agent REPL sessions

#Requires -Version 7.0

# ─── File Operations ────────────────────────────────────────────

function Read-PSKitFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Path,
        [int]$MaxLines = 0
    )
    if (-not (Test-Path $Path)) {
        return @{ success = $false; error = "File not found: $Path" } | ConvertTo-Json -Compress
    }
    $content = Get-Content -Path $Path -Raw
    $lines = Get-Content -Path $Path
    if ($MaxLines -gt 0) { $lines = $lines | Select-Object -First $MaxLines }
    $numbered = for ($i = 0; $i -lt $lines.Count; $i++) {
        "{0,5}| {1}" -f ($i + 1), $lines[$i]
    }
    @{
        success = $true
        path = (Resolve-Path $Path).Path
        line_count = (Get-Content -Path $Path).Count
        content = ($numbered -join "`n")
    } | ConvertTo-Json -Compress
}

function Write-PSKitFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Path,
        [Parameter(Mandatory, Position = 1)]
        [string]$Content
    )
    $parent = Split-Path -Path $Path -Parent
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -Path $Path -Value $Content -Encoding UTF8
    @{ success = $true; path = (Resolve-Path $Path).Path; bytes = (Get-Item $Path).Length } | ConvertTo-Json -Compress
}

function Search-PSKitCode {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Pattern,
        [string]$Path = ".",
        [string]$Include = "*.*",
        [int]$MaxResults = 50,
        [int]$Context = 0
    )

    $rgCmd = Get-Command rg -ErrorAction SilentlyContinue
    if ($rgCmd) {
        $globs = if ($Include -and $Include -ne "*.*") { @("--glob", $Include) } else { @() }
        $ctxArgs = if ($Context -gt 0) { @("-C", $Context) } else { @() }
        $raw = & rg --json @ctxArgs @globs -- $Pattern $Path 2>$null |
            Where-Object { $_ } |
            ForEach-Object { try { $_ | ConvertFrom-Json } catch { $null } } |
            Where-Object { $_ -and $_.type -eq "match" } |
            Select-Object -First $MaxResults
        $results = @($raw | ForEach-Object {
            @{ file = $_.data.path.text; line = $_.data.line_number; text = ($_.data.lines.text -replace "`r`n|`r|`n", "").Trim() }
        })
        @{ success = $true; pattern = $Pattern; count = $results.Count; matches = $results; engine = "rg" } | ConvertTo-Json -Compress -Depth 3
    } else {
        $results = @(Get-ChildItem -Path $Path -Recurse -File -Include $Include -ErrorAction SilentlyContinue |
            Select-String -Pattern $Pattern -ErrorAction SilentlyContinue |
            Select-Object -First $MaxResults |
            ForEach-Object { @{ file = $_.Path; line = $_.LineNumber; text = $_.Line.Trim() } })
        @{ success = $true; pattern = $Pattern; count = $results.Count; matches = $results; engine = "select-string" } | ConvertTo-Json -Compress -Depth 3
    }
}

function Find-PSKitFiles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Pattern,
        [string]$Path = ".",
        [int]$MaxResults = 100
    )

    $rgCmd = Get-Command rg -ErrorAction SilentlyContinue
    if ($rgCmd) {
        # rg --files is significantly faster than Get-ChildItem -Recurse
        $globs = if ($Pattern -and $Pattern -ne "*") { @("--glob", $Pattern) } else { @() }
        $files = @(& rg --files @globs $Path 2>$null |
            Where-Object { $_ } |
            Select-Object -First $MaxResults |
            ForEach-Object {
                $f = Get-Item $_ -ErrorAction SilentlyContinue
                if ($f) { @{ name = $f.Name; path = $f.FullName; size = $f.Length; modified = $f.LastWriteTime.ToString("o") } }
            } | Where-Object { $_ })
        @{ success = $true; pattern = $Pattern; count = $files.Count; files = $files; engine = "rg" } | ConvertTo-Json -Compress -Depth 3
    } else {
        $files = @(Get-ChildItem -Path $Path -Recurse -File -Filter $Pattern -ErrorAction SilentlyContinue |
            Select-Object -First $MaxResults |
            ForEach-Object { @{ name = $_.Name; path = $_.FullName; size = $_.Length; modified = $_.LastWriteTime.ToString("o") } })
        @{ success = $true; pattern = $Pattern; count = $files.Count; files = $files; engine = "get-childitem" } | ConvertTo-Json -Compress -Depth 3
    }
}

# ─── Git Operations ─────────────────────────────────────────────

function Get-PSKitGitStatus {
    [CmdletBinding()]
    param()
    $status = git status --porcelain 2>&1
    $branch = git branch --show-current 2>&1
    $ahead_behind = git rev-list --left-right --count "HEAD...@{upstream}" 2>&1
    @{
        success = $true
        branch = $branch
        changes = ($status -split "`n" | Where-Object { $_ } | ForEach-Object {
            @{ status = $_.Substring(0, 2).Trim(); file = $_.Substring(3) }
        })
        ahead_behind = $ahead_behind
    } | ConvertTo-Json -Compress -Depth 3
}

function Get-PSKitGitDiff {
    [CmdletBinding()]
    param(
        [string]$Path,
        [switch]$Staged
    )
    $args_list = @("diff")
    if ($Staged) { $args_list += "--staged" }
    if ($Path) { $args_list += "--", $Path }
    $diff = & git @args_list 2>&1
    @{ success = $true; diff = ($diff -join "`n") } | ConvertTo-Json -Compress
}

function New-PSKitGitCommit {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Message
    )
    git add -A 2>&1 | Out-Null
    $result = git commit -m $Message 2>&1
    @{ success = ($LASTEXITCODE -eq 0); output = ($result -join "`n") } | ConvertTo-Json -Compress
}

function Get-PSKitGitLog {
    [CmdletBinding()]
    param(
        [int]$Limit = 20,
        [string]$Path = "",
        [string]$Since = "",
        [string]$Until = "",
        [string]$Author = ""
    )
    $gitArgs = @("log", "--format=%H|%h|%s|%an|%ai", "-n", $Limit)
    if ($Since)  { $gitArgs += "--since=$Since" }
    if ($Until)  { $gitArgs += "--until=$Until" }
    if ($Author) { $gitArgs += "--author=$Author" }
    if ($Path)   { $gitArgs += "--"; $gitArgs += $Path }
    $log = & git @gitArgs 2>&1
    $entries = $log | Where-Object { $_ } | ForEach-Object {
        $parts = $_ -split '\|', 5
        @{ hash = $parts[0]; short = $parts[1]; message = $parts[2]; author = $parts[3]; date = $parts[4] }
    }
    @{ success = $true; count = ($entries | Measure-Object).Count; commits = $entries } | ConvertTo-Json -Compress -Depth 3
}

function Save-PSKitGitStash {
    [CmdletBinding()]
    param([string]$Message = "Loom auto-stash")
    $result = git stash push -m $Message 2>&1
    @{ success = ($LASTEXITCODE -eq 0); output = ($result -join "`n") } | ConvertTo-Json -Compress
}

function Restore-PSKitGitStash {
    [CmdletBinding()]
    param()
    $result = git stash pop 2>&1
    @{ success = ($LASTEXITCODE -eq 0); output = ($result -join "`n") } | ConvertTo-Json -Compress
}

# ─── System Info ────────────────────────────────────────────────

function Get-PSKitGpuStatus {
    [CmdletBinding()]
    param()
    try {
        $nvsmi = nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu --format=csv,noheader 2>&1
        if ($LASTEXITCODE -eq 0) {
            $parts = ($nvsmi -split ',').Trim()
            return @{
                success = $true
                gpu = $parts[0]
                memory_total = $parts[1]
                memory_used = $parts[2]
                memory_free = $parts[3]
                utilization = $parts[4]
                temperature = $parts[5]
            } | ConvertTo-Json -Compress
        }
    } catch {}
    @{ success = $false; error = "nvidia-smi not available" } | ConvertTo-Json -Compress
}

function Get-PSKitDiskUsage {
    [CmdletBinding()]
    param([string]$Path = ".")
    $drive = (Get-Item $Path).PSDrive
    $info = Get-PSDrive -Name $drive.Name
    @{
        success = $true
        drive = $drive.Name
        used_gb = [math]::Round($info.Used / 1GB, 2)
        free_gb = [math]::Round($info.Free / 1GB, 2)
        total_gb = [math]::Round(($info.Used + $info.Free) / 1GB, 2)
    } | ConvertTo-Json -Compress
}

function Get-PSKitMemoryUsage {
    [CmdletBinding()]
    param()
    $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction SilentlyContinue
    if ($os) {
        @{
            success = $true
            total_gb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
            free_gb = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
            used_gb = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 2)
        } | ConvertTo-Json -Compress
    } else {
        @{ success = $false; error = "Unable to query memory info" } | ConvertTo-Json -Compress
    }
}

# ─── Build & Test ───────────────────────────────────────────────

function Invoke-PSKitBuild {
    [CmdletBinding()]
    param([string]$Command = "")
    if (-not $Command) {
        if (Test-Path "package.json")  { $Command = "npm run build" }
        elseif (Test-Path "Cargo.toml") { $Command = "cargo build" }
        elseif (Test-Path "Makefile")   { $Command = "make" }
        elseif (Test-Path "pyproject.toml" -or Test-Path "setup.py") { $Command = "python -m build" }
        else { return @{ success = $false; error = "No build system detected"; command_used = "" } | ConvertTo-Json -Compress }
    }
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $outFile = [System.IO.Path]::GetTempFileName()
    $errFile = [System.IO.Path]::GetTempFileName()
    try {
        $proc = Start-Process pwsh -ArgumentList "-NoProfile","-Command",$Command `
            -RedirectStandardOutput $outFile -RedirectStandardError $errFile `
            -Wait -PassThru -NoNewWindow
        $stdout = if (Test-Path $outFile) { [System.IO.File]::ReadAllText($outFile) } else { "" }
        $stderr = if (Test-Path $errFile) { [System.IO.File]::ReadAllText($errFile) } else { "" }
        $exitCode = $proc.ExitCode
    } catch {
        $stdout = ""; $stderr = $_.Exception.Message; $exitCode = 1
    } finally {
        Remove-Item $outFile,$errFile -ErrorAction SilentlyContinue
    }
    $sw.Stop()
    @{ success = ($exitCode -eq 0); command_used = $Command; exit_code = $exitCode
       stdout = $stdout.TrimEnd(); stderr = $stderr.TrimEnd(); duration_ms = $sw.ElapsedMilliseconds
    } | ConvertTo-Json -Compress
}

function Invoke-PSKitTest {
    [CmdletBinding()]
    param(
        [string]$Filter = "",
        [string]$Command = ""
    )
    if (-not $Command) {
        if (Test-Path "pyproject.toml" -or Test-Path "pytest.ini") {
            $Command = if ($Filter) { "python -m pytest -q -k `"$Filter`"" } else { "python -m pytest -q" }
        } elseif (Test-Path "package.json") {
            $Command = if ($Filter) { "npm test -- --grep `"$Filter`"" } else { "npm test" }
        } elseif (Test-Path "Cargo.toml") {
            $Command = if ($Filter) { "cargo test $Filter" } else { "cargo test" }
        } else { return @{ success = $false; error = "No test framework detected"; command_used = "" } | ConvertTo-Json -Compress }
    }
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $outFile = [System.IO.Path]::GetTempFileName()
    $errFile = [System.IO.Path]::GetTempFileName()
    try {
        $proc = Start-Process pwsh -ArgumentList "-NoProfile","-Command",$Command `
            -RedirectStandardOutput $outFile -RedirectStandardError $errFile `
            -Wait -PassThru -NoNewWindow
        $stdout = if (Test-Path $outFile) { [System.IO.File]::ReadAllText($outFile) } else { "" }
        $stderr = if (Test-Path $errFile) { [System.IO.File]::ReadAllText($errFile) } else { "" }
        $exitCode = $proc.ExitCode
    } catch {
        $stdout = ""; $stderr = $_.Exception.Message; $exitCode = 1
    } finally {
        Remove-Item $outFile,$errFile -ErrorAction SilentlyContinue
    }
    $sw.Stop()
    # Parse pytest-style summary
    $passed = 0; $failed = 0; $skipped = 0
    $allText = $stdout + $stderr
    if ($allText -match '(\d+) passed')  { $passed  = [int]$Matches[1] }
    if ($allText -match '(\d+) failed')  { $failed  = [int]$Matches[1] }
    if ($allText -match '(\d+) skipped') { $skipped = [int]$Matches[1] }
    @{ success = ($exitCode -eq 0); command_used = $Command; exit_code = $exitCode
       passed = $passed; failed = $failed; skipped = $skipped
       stdout = $stdout.TrimEnd(); stderr = $stderr.TrimEnd(); duration_ms = $sw.ElapsedMilliseconds
    } | ConvertTo-Json -Compress
}

# ─── Advanced Tools ─────────────────────────────────────────────

function Edit-PSKitFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Path,
        [Parameter(Mandatory, Position = 1)]
        [string]$OldText,
        [Parameter(Mandatory, Position = 2)]
        [string]$NewText,
        [switch]$Regex,
        [switch]$All
    )
    if (-not (Test-Path $Path)) {
        return @{ success = $false; error = "File not found: $Path" } | ConvertTo-Json -Compress
    }
    $content = Get-Content -Path $Path -Raw -Encoding UTF8
    $replaced = 0
    if ($Regex) {
        $newContent = if ($All) {
            [regex]::Replace($content, $OldText, $NewText)
        } else {
            [regex]::Replace($content, $OldText, $NewText, [System.Text.RegularExpressions.RegexOptions]::None, [System.TimeSpan]::FromSeconds(5))
            # Count occurrences
        }
        $replaced = ([regex]::Matches($content, $OldText)).Count
        $newContent = [regex]::Replace($content, $OldText, $NewText)
    } else {
        $replaced = ([regex]::Matches([regex]::Escape($content), [regex]::Escape($OldText))).Count
        if ($All) {
            $newContent = $content.Replace($OldText, $NewText)
        } else {
            $idx = $content.IndexOf($OldText)
            if ($idx -lt 0) {
                return @{ success = $false; error = "OldText not found in file"; path = $Path } | ConvertTo-Json -Compress
            }
            $newContent = $content.Substring(0, $idx) + $NewText + $content.Substring($idx + $OldText.Length)
            $replaced = 1
        }
    }
    Set-Content -Path $Path -Value $newContent -Encoding UTF8 -NoNewline
    @{
        success = $true
        path = (Resolve-Path $Path).Path
        replacements_made = $replaced
        preview = ($newContent -split "`n" | Select-Object -First 5) -join "`n"
    } | ConvertTo-Json -Compress
}

function Get-PSKitPortStatus {
    [CmdletBinding()]
    param(
        [int[]]$Ports = @(8080, 8443, 11434, 7474, 7687, 5432, 3000, 3001, 8000, 9000)
    )
    $results = @($Ports | ForEach-Object {
        $port = $_
        $listening = $false
        $pid_ = $null
        $procName = $null
        try {
            $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
            if ($conn) {
                $listening = $true
                $pid_ = $conn[0].OwningProcess
                $proc = Get-Process -Id $pid_ -ErrorAction SilentlyContinue
                $procName = if ($proc) { $proc.Name } else { $null }
            }
        } catch {}
        @{ port = $port; listening = $listening; pid = $pid_; process_name = $procName }
    })
    @{ success = $true; ports = $results } | ConvertTo-Json -Compress -Depth 3
}

function Invoke-PSKitHttpRequest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Uri,
        [string]$Method = 'GET',
        [hashtable]$Headers = @{},
        [string]$Body = '',
        [int]$TimeoutSec = 30
    )
    # Safety: only allow localhost and RFC-1918 private addresses
    $parsedUri = [System.Uri]$Uri
    $host_ = $parsedUri.Host
    $isLocal = $host_ -match '^(localhost|127\.\d+\.\d+\.\d+|::1|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2[0-9]|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+)$'
    if (-not $isLocal) {
        return @{ success = $false; error = "Invoke-PSKitHttpRequest is restricted to localhost and private IPs. Uri: $Uri" } | ConvertTo-Json -Compress
    }
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $params = @{ Uri = $Uri; Method = $Method; TimeoutSec = $TimeoutSec; UseBasicParsing = $true }
        if ($Headers.Count -gt 0) { $params['Headers'] = $Headers }
        if ($Body) { $params['Body'] = $Body }
        $resp = Invoke-WebRequest @params -ErrorAction Stop
        $sw.Stop()
        @{
            success = $true
            status_code = [int]$resp.StatusCode
            body = $resp.Content
            headers = ($resp.Headers | ConvertTo-Json -Compress -Depth 2)
            elapsed_ms = $sw.ElapsedMilliseconds
        } | ConvertTo-Json -Compress
    } catch {
        $sw.Stop()
        @{ success = $false; error = $_.Exception.Message; elapsed_ms = $sw.ElapsedMilliseconds } | ConvertTo-Json -Compress
    }
}

function Get-PSKitProcessInfo {
    [CmdletBinding()]
    param(
        [string]$Name = '',
        [int]$Id = -1,
        [switch]$IncludeThreads
    )
    try {
        $procs = if ($Id -gt 0) {
            Get-Process -Id $Id -ErrorAction SilentlyContinue
        } elseif ($Name) {
            Get-Process -Name $Name -ErrorAction SilentlyContinue
        } else {
            Get-Process -ErrorAction SilentlyContinue | Sort-Object CPU -Descending | Select-Object -First 20
        }
        $results = @($procs | ForEach-Object {
            $p = $_
            $entry = @{
                name = $p.Name
                id = $p.Id
                cpu_s = [math]::Round($p.CPU, 2)
                memory_mb = [math]::Round($p.WorkingSet64 / 1MB, 2)
                start_time = if ($p.StartTime) { $p.StartTime.ToString("o") } else { $null }
                responding = $p.Responding
                thread_count = $p.Threads.Count
            }
            if ($IncludeThreads) {
                $entry['threads'] = @($p.Threads | ForEach-Object { @{ id = $_.Id; state = $_.ThreadState.ToString() } })
            }
            $entry
        })
        @{ success = $true; count = $results.Count; processes = $results } | ConvertTo-Json -Compress -Depth 4
    } catch {
        @{ success = $false; error = $_.Exception.Message } | ConvertTo-Json -Compress
    }
}

# ─── Module Export ──────────────────────────────────────────────

# ─── New File Operations ─────────────────────────────────────────

function Read-PSKitFileRange {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Path,
        [Parameter(Mandatory)] [int]$StartLine,
        [Parameter(Mandatory)] [int]$EndLine
    )
    if (-not (Test-Path $Path)) {
        return @{ success = $false; error = "File not found: $Path" } | ConvertTo-Json -Compress
    }
    $lines = Get-Content -Path $Path
    $total = $lines.Count
    $s = [Math]::Max(0, $StartLine - 1)
    $e = [Math]::Min($total - 1, $EndLine - 1)
    $numbered = for ($i = $s; $i -le $e; $i++) {
        "{0,5}| {1}" -f ($i + 1), $lines[$i]
    }
    @{ success = $true; path = (Resolve-Path $Path).Path; start_line = $StartLine; end_line = $EndLine; line_count = $total; content = ($numbered -join "`n") } | ConvertTo-Json -Compress
}

function Move-PSKitFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Source,
        [Parameter(Mandatory, Position = 1)] [string]$Destination
    )
    if (-not (Test-Path $Source)) {
        return @{ success = $false; error = "Source not found: $Source" } | ConvertTo-Json -Compress
    }
    $destParent = Split-Path -Path $Destination -Parent
    if ($destParent -and -not (Test-Path $destParent)) { New-Item -ItemType Directory -Path $destParent -Force | Out-Null }
    Move-Item -Path $Source -Destination $Destination -Force
    @{ success = $true; source = $Source; destination = (Resolve-Path $Destination).Path } | ConvertTo-Json -Compress
}

function Remove-PSKitFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Path,
        [switch]$Recurse
    )
    if (-not (Test-Path $Path)) {
        return @{ success = $false; error = "Path not found: $Path" } | ConvertTo-Json -Compress
    }
    Remove-Item -Path $Path -Recurse:$Recurse -Force
    @{ success = $true; path = $Path } | ConvertTo-Json -Compress
}

function New-PSKitDirectory {
    [CmdletBinding()]
    param([Parameter(Mandatory, Position = 0)] [string]$Path)
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
    @{ success = $true; path = (Resolve-Path $Path).Path } | ConvertTo-Json -Compress
}

function Get-PSKitDirectoryListing {
    [CmdletBinding()]
    param(
        [Parameter(Position = 0)] [string]$Path = ".",
        [switch]$Recurse
    )
    $items = @(Get-ChildItem -Path $Path -Recurse:$Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 200 |
        ForEach-Object {
            @{ name = $_.Name; path = $_.FullName; type = if ($_.PSIsContainer) { "directory" } else { "file" }
               size_bytes = if ($_.PSIsContainer) { 0 } else { $_.Length }; modified = $_.LastWriteTime.ToString("o") }
        })
    @{ success = $true; path = (Resolve-Path $Path).Path; count = $items.Count; items = $items } | ConvertTo-Json -Compress -Depth 4
}

function Compare-PSKitFiles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Path1,
        [Parameter(Mandatory, Position = 1)] [string]$Path2
    )
    foreach ($p in @($Path1, $Path2)) {
        if (-not (Test-Path $p)) { return @{ success = $false; error = "File not found: $p" } | ConvertTo-Json -Compress }
    }
    $diff = git diff --no-index -- $Path1 $Path2 2>&1
    @{ success = $true; path1 = $Path1; path2 = $Path2; identical = ($LASTEXITCODE -eq 0); diff = ($diff -join "`n") } | ConvertTo-Json -Compress
}

function Invoke-PSKitCommand {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Script,
        [int]$TimeoutSec = 30
    )
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $outFile = [System.IO.Path]::GetTempFileName()
    $errFile = [System.IO.Path]::GetTempFileName()
    try {
        $proc = Start-Process pwsh -ArgumentList "-NoProfile","-Command",$Script `
            -RedirectStandardOutput $outFile -RedirectStandardError $errFile `
            -Wait -PassThru -NoNewWindow
        $stdout = if (Test-Path $outFile) { [System.IO.File]::ReadAllText($outFile) } else { "" }
        $stderr = if (Test-Path $errFile) { [System.IO.File]::ReadAllText($errFile) } else { "" }
        $exitCode = $proc.ExitCode
    } catch {
        $stdout = ""; $stderr = $_.Exception.Message; $exitCode = 1
    } finally {
        Remove-Item $outFile,$errFile -ErrorAction SilentlyContinue
    }
    $sw.Stop()
    @{ success = ($exitCode -eq 0); exit_code = $exitCode; output = $stdout.TrimEnd()
       stderr = $stderr.TrimEnd(); duration_ms = $sw.ElapsedMilliseconds } | ConvertTo-Json -Compress
}

function Get-PSKitEnvVars {
    [CmdletBinding()]
    param([string]$Filter = "")
    $vars = [System.Environment]::GetEnvironmentVariables()
    $result = [ordered]@{}
    foreach ($key in ($vars.Keys | Sort-Object)) {
        if (-not $Filter -or ($key -like "*$Filter*")) { $result[$key] = $vars[$key] }
    }
    @{ success = $true; count = $result.Count; vars = $result } | ConvertTo-Json -Compress -Depth 3
}

function Get-PSKitWhich {
    [CmdletBinding()]
    param([Parameter(Mandatory, Position = 0)] [string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        $ver = try { (& $Name --version 2>&1 | Select-Object -First 1) } catch { "" }
        @{ found = $true; name = $Name; path = $cmd.Source; version = "$ver" } | ConvertTo-Json -Compress
    } else {
        @{ found = $false; name = $Name; path = $null; version = $null } | ConvertTo-Json -Compress
    }
}

function Install-PSKitPackage {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Name,
        [string]$Manager = "",
        [string]$Version = ""
    )
    $pkg = if ($Version) { "$Name==$Version" } else { $Name }
    if (-not $Manager) {
        if     (Get-Command pip   -EA SilentlyContinue) { $Manager = "pip" }
        elseif (Get-Command npm   -EA SilentlyContinue) { $Manager = "npm" }
        elseif (Get-Command cargo -EA SilentlyContinue) { $Manager = "cargo" }
        else   { return @{ success = $false; error = "No package manager found on PATH" } | ConvertTo-Json -Compress }
    }
    $cmd = switch ($Manager.ToLower()) {
        "pip"    { "pip install $pkg" }
        "npm"    { "npm install $Name" }
        "cargo"  { "cargo add $Name" }
        "winget" { "winget install $Name" }
        default  { return @{ success = $false; error = "Unknown manager: $Manager" } | ConvertTo-Json -Compress }
    }
    $output = Invoke-Expression $cmd 2>&1
    @{ success = ($LASTEXITCODE -eq 0); manager = $Manager; package = $Name; command = $cmd; output = ($output -join "`n") } | ConvertTo-Json -Compress
}

# ─── New Git Operations ──────────────────────────────────────────

function New-PSKitGitBranch {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Name,
        [switch]$Switch
    )
    if ($Switch) { $out = git checkout -b $Name 2>&1 }
    else         { $out = git branch $Name 2>&1 }
    @{ success = ($LASTEXITCODE -eq 0); branch = $Name; output = ($out -join "`n") } | ConvertTo-Json -Compress
}

function Switch-PSKitGitBranch {
    [CmdletBinding()]
    param([Parameter(Mandatory, Position = 0)] [string]$Ref)
    $out = git checkout $Ref 2>&1
    @{ success = ($LASTEXITCODE -eq 0); ref = $Ref; output = ($out -join "`n") } | ConvertTo-Json -Compress
}

function Push-PSKitGit {
    [CmdletBinding()]
    param(
        [string]$Remote = "origin",
        [string]$Branch = ""
    )
    if (-not $Branch) { $Branch = git rev-parse --abbrev-ref HEAD 2>$null }
    $out = git push $Remote $Branch 2>&1
    @{ success = ($LASTEXITCODE -eq 0); remote = $Remote; branch = $Branch; output = ($out -join "`n") } | ConvertTo-Json -Compress
}

function Get-PSKitGitBlame {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Path,
        [int]$StartLine = 0,
        [int]$EndLine = 0
    )
    $rangeArg = if ($StartLine -gt 0 -and $EndLine -gt 0) { @("-L","$StartLine,$EndLine") } else { @() }
    $raw = & git blame --porcelain @rangeArg -- $Path 2>&1
    $lines = [System.Collections.Generic.List[hashtable]]::new()
    $i = 0; $author = ""; $date = ""
    while ($i -lt $raw.Count) {
        if ($raw[$i] -match '^([0-9a-f]{40}) \d+ (\d+)') {
            $hash = $Matches[1]; $lineNum = [int]$Matches[2]
            $j = $i + 1
            while ($j -lt $raw.Count -and $raw[$j] -notmatch '^[0-9a-f]{40}') {
                if ($raw[$j] -match '^author (.+)')      { $author = $Matches[1] }
                if ($raw[$j] -match '^author-time (\d+)') { $date = [DateTimeOffset]::FromUnixTimeSeconds([long]$Matches[1]).ToString("o") }
                if ($raw[$j] -match '^\t(.*)') {
                    $lines.Add(@{ line = $lineNum; hash = $hash.Substring(0,8); author = $author; date = $date; content = $Matches[1] })
                    break
                }
                $j++
            }
            $i = $j + 1
        } else { $i++ }
    }
    @($lines) | ConvertTo-Json -Compress -Depth 4
}

Export-ModuleMember -Function @(
    # File operations
    'Read-PSKitFile', 'Read-PSKitFileRange',
    'Write-PSKitFile', 'Edit-PSKitFile',
    'Move-PSKitFile', 'Remove-PSKitFile',
    'New-PSKitDirectory', 'Get-PSKitDirectoryListing',
    'Compare-PSKitFiles', 'Invoke-PSKitCommand',
    'Search-PSKitCode', 'Find-PSKitFiles',
    # Environment
    'Get-PSKitEnvVars', 'Get-PSKitWhich', 'Install-PSKitPackage',
    # Git
    'Get-PSKitGitStatus', 'Get-PSKitGitDiff', 'Get-PSKitGitLog',
    'New-PSKitGitCommit', 'Save-PSKitGitStash', 'Restore-PSKitGitStash',
    'New-PSKitGitBranch', 'Switch-PSKitGitBranch', 'Push-PSKitGit', 'Get-PSKitGitBlame',
    # System info
    'Get-PSKitGpuStatus', 'Get-PSKitDiskUsage', 'Get-PSKitMemoryUsage',
    # Network & processes
    'Get-PSKitPortStatus', 'Invoke-PSKitHttpRequest', 'Get-PSKitProcessInfo',
    # Build & test
    'Invoke-PSKitBuild', 'Invoke-PSKitTest'
)
