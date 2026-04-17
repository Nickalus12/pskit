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

    if ($IsLinux -or $IsMacOS) {
        try {
            $abs = (Resolve-Path $Path -ErrorAction Stop).Path
            # POSIX `df -Pk` gives us stable columns: Filesystem | 1024-blocks | Used | Available | Capacity | Mounted on
            $lines = df -Pk $abs 2>$null
            if ($LASTEXITCODE -ne 0 -or $lines.Count -lt 2) {
                return @{ success = $false; error = "df failed for $abs" } | ConvertTo-Json -Compress
            }
            $parts = ($lines[1] -split '\s+')
            $total_kb = [long]$parts[1]
            $used_kb  = [long]$parts[2]
            $free_kb  = [long]$parts[3]
            return @{
                success = $true
                drive = $parts[0]
                mount = $parts[-1]
                used_gb  = [math]::Round($used_kb / 1MB, 2)
                free_gb  = [math]::Round($free_kb / 1MB, 2)
                total_gb = [math]::Round($total_kb / 1MB, 2)
                platform = if ($IsLinux) { 'linux' } else { 'macos' }
            } | ConvertTo-Json -Compress
        } catch {
            return @{ success = $false; error = $_.Exception.Message } | ConvertTo-Json -Compress
        }
    }

    # Windows path
    $drive = (Get-Item $Path).PSDrive
    $info = Get-PSDrive -Name $drive.Name
    @{
        success = $true
        drive = $drive.Name
        used_gb = [math]::Round($info.Used / 1GB, 2)
        free_gb = [math]::Round($info.Free / 1GB, 2)
        total_gb = [math]::Round(($info.Used + $info.Free) / 1GB, 2)
        platform = 'windows'
    } | ConvertTo-Json -Compress
}

function Get-PSKitMemoryUsage {
    [CmdletBinding()]
    param()

    if ($IsLinux) {
        try {
            $meminfo = Get-Content '/proc/meminfo' -ErrorAction Stop
            $kv = @{}
            foreach ($line in $meminfo) {
                if ($line -match '^(\w+):\s+(\d+)\s+kB') { $kv[$Matches[1]] = [long]$Matches[2] }
            }
            $total_kb = $kv['MemTotal']
            # MemAvailable is the right "free" metric on modern kernels (>=3.14)
            $avail_kb = if ($kv.ContainsKey('MemAvailable')) { $kv['MemAvailable'] } else { $kv['MemFree'] + $kv['Buffers'] + $kv['Cached'] }
            return @{
                success = $true
                total_gb = [math]::Round($total_kb / 1MB, 2)
                free_gb  = [math]::Round($avail_kb / 1MB, 2)
                used_gb  = [math]::Round(($total_kb - $avail_kb) / 1MB, 2)
                platform = 'linux'
            } | ConvertTo-Json -Compress
        } catch {
            return @{ success = $false; error = "Unable to read /proc/meminfo: $($_.Exception.Message)" } | ConvertTo-Json -Compress
        }
    }

    if ($IsMacOS) {
        try {
            $totalBytes = [long](sysctl -n hw.memsize)
            # vm_stat reports pages; default page size is 16384 on Apple Silicon, 4096 elsewhere
            $pageSize = [long](sysctl -n hw.pagesize)
            $vm = vm_stat
            $free_p = 0L; $active_p = 0L; $inactive_p = 0L; $wired_p = 0L; $spec_p = 0L
            foreach ($line in $vm) {
                if ($line -match 'Pages free:\s+(\d+)')              { $free_p = [long]$Matches[1] }
                elseif ($line -match 'Pages active:\s+(\d+)')        { $active_p = [long]$Matches[1] }
                elseif ($line -match 'Pages inactive:\s+(\d+)')      { $inactive_p = [long]$Matches[1] }
                elseif ($line -match 'Pages wired down:\s+(\d+)')    { $wired_p = [long]$Matches[1] }
                elseif ($line -match 'Pages speculative:\s+(\d+)')   { $spec_p = [long]$Matches[1] }
            }
            $free_bytes = ($free_p + $inactive_p + $spec_p) * $pageSize
            return @{
                success = $true
                total_gb = [math]::Round($totalBytes / 1GB, 2)
                free_gb  = [math]::Round($free_bytes / 1GB, 2)
                used_gb  = [math]::Round(($totalBytes - $free_bytes) / 1GB, 2)
                platform = 'macos'
            } | ConvertTo-Json -Compress
        } catch {
            return @{ success = $false; error = "Unable to query macOS memory: $($_.Exception.Message)" } | ConvertTo-Json -Compress
        }
    }

    # Windows path (original implementation)
    $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction SilentlyContinue
    if ($os) {
        return @{
            success = $true
            total_gb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
            free_gb  = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
            used_gb  = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 2)
            platform = 'windows'
        } | ConvertTo-Json -Compress
    }
    @{ success = $false; error = "Unable to query memory info on this platform" } | ConvertTo-Json -Compress
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

    if ($IsLinux -or $IsMacOS) {
        # Build a lookup of listening ports -> pid/process via `ss` (Linux) or `lsof` (macOS)
        $portMap = @{}
        if ($IsLinux) {
            $ssCmd = Get-Command ss -ErrorAction SilentlyContinue
            if ($ssCmd) {
                $raw = ss -tlnp 2>$null
                foreach ($line in $raw) {
                    # State  Recv-Q Send-Q  Local Address:Port   Peer...  users:(("proc",pid=1234,fd=5))
                    if ($line -match ':(\d+)\s+\S+\s+.*users:\(\("([^"]+)",pid=(\d+)') {
                        $portMap[[int]$Matches[1]] = @{ pid = [int]$Matches[3]; name = $Matches[2] }
                    } elseif ($line -match ':(\d+)\s') {
                        if (-not $portMap.ContainsKey([int]$Matches[1])) { $portMap[[int]$Matches[1]] = @{ pid = $null; name = $null } }
                    }
                }
            } else {
                # Fall back to /proc/net/tcp — pid lookup requires matching inodes to /proc/<pid>/fd; skip process names
                try {
                    $tcp = Get-Content '/proc/net/tcp'
                    foreach ($line in $tcp | Select-Object -Skip 1) {
                        $tokens = ($line.Trim() -split '\s+')
                        if ($tokens[3] -eq '0A') {   # 0A = LISTEN
                            $hexPort = ($tokens[1] -split ':')[1]
                            $portMap[[Convert]::ToInt32($hexPort, 16)] = @{ pid = $null; name = $null }
                        }
                    }
                } catch {}
            }
        } else {
            # macOS
            $lsofCmd = Get-Command lsof -ErrorAction SilentlyContinue
            if ($lsofCmd) {
                $raw = lsof -nP -iTCP -sTCP:LISTEN 2>$null
                foreach ($line in $raw | Select-Object -Skip 1) {
                    # COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME
                    $toks = ($line -split '\s+')
                    if ($toks.Count -ge 9) {
                        if ($toks[-1] -match ':(\d+)$') {
                            $portMap[[int]$Matches[1]] = @{ pid = [int]$toks[1]; name = $toks[0] }
                        }
                    }
                }
            }
        }

        $results = @($Ports | ForEach-Object {
            $p = $_
            if ($portMap.ContainsKey($p)) {
                @{ port = $p; listening = $true; pid = $portMap[$p].pid; process_name = $portMap[$p].name }
            } else {
                @{ port = $p; listening = $false; pid = $null; process_name = $null }
            }
        })
        return @{ success = $true; ports = $results; platform = if ($IsLinux) { 'linux' } else { 'macos' } } | ConvertTo-Json -Compress -Depth 3
    }

    # Windows path
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
    @{ success = $true; ports = $results; platform = 'windows' } | ConvertTo-Json -Compress -Depth 3
}

function Invoke-PSKitHttpRequest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)]
        [Alias('Url')]
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
            # .Responding is Windows-only — guard it
            $responding = $null
            try { $responding = $p.Responding } catch { $responding = $null }
            # .Threads on Linux pwsh can be a PSObject collection without .ThreadState
            $threadCount = 0
            try { $threadCount = $p.Threads.Count } catch { $threadCount = 0 }
            # .StartTime on some Linux processes throws when not accessible
            $startTime = $null
            try { if ($p.StartTime) { $startTime = $p.StartTime.ToString("o") } } catch { $startTime = $null }

            $cpu_s = $null
            try { $cpu_s = [math]::Round($p.CPU, 2) } catch { $cpu_s = $null }
            $memory_mb = $null
            try { $memory_mb = [math]::Round($p.WorkingSet64 / 1MB, 2) } catch { $memory_mb = $null }
            $entry = @{
                name = $p.Name
                id = $p.Id
                cpu_s = $cpu_s
                memory_mb = $memory_mb
                start_time = $startTime
                responding = $responding
                thread_count = $threadCount
            }
            if ($IncludeThreads -and $threadCount -gt 0) {
                $threadList = @()
                foreach ($t in $p.Threads) {
                    $tid = $null; $tstate = $null
                    try { $tid = $t.Id } catch {}
                    try { $tstate = $t.ThreadState.ToString() } catch {}
                    $threadList += @{ id = $tid; state = $tstate }
                }
                $entry['threads'] = $threadList
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
        # Prefer language-native managers first (they install to user scope)
        if     (Get-Command pip   -EA SilentlyContinue) { $Manager = "pip" }
        elseif (Get-Command npm   -EA SilentlyContinue) { $Manager = "npm" }
        elseif (Get-Command cargo -EA SilentlyContinue) { $Manager = "cargo" }
        elseif ($IsMacOS -and (Get-Command brew -EA SilentlyContinue))         { $Manager = "brew" }
        elseif ($IsLinux -and (Get-Command apt-get -EA SilentlyContinue))      { $Manager = "apt" }
        elseif ($IsLinux -and (Get-Command dnf -EA SilentlyContinue))          { $Manager = "dnf" }
        elseif ($IsLinux -and (Get-Command pacman -EA SilentlyContinue))       { $Manager = "pacman" }
        elseif (Get-Command winget -EA SilentlyContinue)                       { $Manager = "winget" }
        else   { return @{ success = $false; error = "No package manager found on PATH" } | ConvertTo-Json -Compress }
    }
    $cmd = switch ($Manager.ToLower()) {
        "pip"    { "pip install $pkg" }
        "npm"    { "npm install $Name" }
        "cargo"  { "cargo add $Name" }
        "brew"   { "brew install $Name" }
        "apt"    { "sudo apt-get install -y $Name" }
        "dnf"    { "sudo dnf install -y $Name" }
        "pacman" { "sudo pacman -S --noconfirm $Name" }
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
