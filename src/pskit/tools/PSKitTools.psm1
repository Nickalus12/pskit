# PSKitTools.psm1
# PowerShell helper functions for PSKit MCP

#Requires -Version 7.0

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
    $lines = Get-Content -Path $Path
    if ($MaxLines -gt 0) { $lines = $lines | Select-Object -First $MaxLines }
    $numbered = for ($i = 0; $i -lt $lines.Count; $i++) {
        "{0,5}| {1}" -f ($i + 1), $lines[$i]
    }
    @{
        success    = $true
        path       = (Resolve-Path $Path).Path
        line_count = (Get-Content -Path $Path).Count
        content    = ($numbered -join "`n")
    } | ConvertTo-Json -Compress
}

function Write-PSKitFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Path,
        [Parameter(Mandatory, Position = 1)] [string]$Content
    )
    $parent = Split-Path -Path $Path -Parent
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -Path $Path -Value $Content -Encoding UTF8
    @{ success = $true; path = (Resolve-Path $Path).Path; bytes = (Get-Item $Path).Length } | ConvertTo-Json -Compress
}

function Edit-PSKitFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Path,
        [Parameter(Mandatory, Position = 1)] [string]$OldText,
        [Parameter(Mandatory, Position = 2)] [string]$NewText,
        [switch]$Regex,
        [switch]$All
    )
    if (-not (Test-Path $Path)) {
        return @{ success = $false; error = "File not found: $Path" } | ConvertTo-Json -Compress
    }
    $content = Get-Content -Path $Path -Raw
    $count = 0
    if ($Regex) {
        $pattern = $OldText
        $count = ([regex]::Matches($content, $pattern)).Count
        if ($All) { $content = [regex]::Replace($content, $pattern, $NewText) }
        else { $content = [regex]::Replace($content, $pattern, $NewText, [System.Text.RegularExpressions.RegexOptions]::None) }
    } else {
        $count = ([regex]::Matches([regex]::Escape($content), [regex]::Escape($OldText))).Count
        if ($All) { $content = $content.Replace($OldText, $NewText) }
        else {
            $idx = $content.IndexOf($OldText)
            if ($idx -ge 0) { $content = $content.Substring(0, $idx) + $NewText + $content.Substring($idx + $OldText.Length) }
            else { $count = 0 }
        }
    }
    if ($count -eq 0) {
        return @{ success = $false; error = "old_text not found in file"; path = $Path } | ConvertTo-Json -Compress
    }
    Set-Content -Path $Path -Value $content -Encoding UTF8 -NoNewline
    @{ success = $true; replacements_made = $count; preview = $content.Substring(0, [Math]::Min(200, $content.Length)); path = $Path } | ConvertTo-Json -Compress
}

function Search-PSKitCode {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Pattern,
        [string]$Path = ".",
        [string]$Include = "*.*",
        [int]$MaxResults = 50
    )
    $rgCmd = Get-Command rg -ErrorAction SilentlyContinue
    if ($rgCmd) {
        $raw = rg --json $Pattern $Path --glob $Include 2>$null |
               Where-Object { $_ -match '"type":"match"' } |
               Select-Object -First $MaxResults
        $results = $raw | ForEach-Object {
            $obj = $_ | ConvertFrom-Json
            @{ file = $obj.data.path.text; line_number = $obj.data.line_number; text = $obj.data.lines.text.Trim() }
        }
    } else {
        $results = Get-ChildItem -Path $Path -Recurse -Include $Include -File |
            Select-String -Pattern $Pattern | Select-Object -First $MaxResults |
            ForEach-Object { @{ file = $_.Path; line_number = $_.LineNumber; text = $_.Line.Trim() } }
    }
    $results | ConvertTo-Json -Compress
}

function Find-PSKitFiles {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, Position = 0)] [string]$Pattern,
        [string]$Path = ".",
        [int]$MaxResults = 100
    )
    $rgCmd = Get-Command rg -ErrorAction SilentlyContinue
    if ($rgCmd) {
        $files = rg --files $Path --glob $Pattern 2>$null | Select-Object -First $MaxResults
        $results = $files | ForEach-Object {
            $item = Get-Item $_
            @{ name = $item.Name; path = $item.FullName; size_bytes = $item.Length; modified = $item.LastWriteTime.ToString("o") }
        }
    } else {
        $results = Get-ChildItem -Path $Path -Recurse -Include $Pattern -File |
            Select-Object -First $MaxResults |
            ForEach-Object { @{ name = $_.Name; path = $_.FullName; size_bytes = $_.Length; modified = $_.LastWriteTime.ToString("o") } }
    }
    $results | ConvertTo-Json -Compress
}

function Get-PSKitGitStatus {
    $branch = git rev-parse --abbrev-ref HEAD 2>$null
    $ahead  = (git rev-list "@{u}..HEAD" 2>$null | Measure-Object).Count
    $behind = (git rev-list "HEAD..@{u}" 2>$null | Measure-Object).Count
    $changes = git status --porcelain 2>$null | ForEach-Object {
        @{ status = $_.Substring(0,2).Trim(); file = $_.Substring(3) }
    }
    @{ branch = $branch; ahead = $ahead; behind = $behind; changes = @($changes) } | ConvertTo-Json -Compress -Depth 5
}

function Get-PSKitGitDiff {
    [CmdletBinding()]
    param([string]$Path = "", [switch]$Staged)
    $args = @("diff")
    if ($Staged) { $args += "--cached" }
    if ($Path)   { $args += "--", $Path }
    $output = & git @args 2>&1
    @{ success = $true; output = ($output -join "`n") } | ConvertTo-Json -Compress
}

function Get-PSKitGitLog {
    param([int]$Limit = 20)
    $log = git log --pretty=format:"%H|%h|%s|%an|%aI" -n $Limit 2>$null
    $commits = $log | ForEach-Object {
        $p = $_ -split "\|", 5
        @{ hash = $p[0]; short_hash = $p[1]; message = $p[2]; author = $p[3]; date = $p[4] }
    }
    @($commits) | ConvertTo-Json -Compress -Depth 5
}

function New-PSKitGitCommit {
    param([Parameter(Mandatory)] [string]$Message)
    git add -A 2>&1 | Out-Null
    $out = git commit -m $Message 2>&1
    @{ success = ($LASTEXITCODE -eq 0); output = ($out -join "`n") } | ConvertTo-Json -Compress
}

function Save-PSKitGitStash {
    param([string]$Message = "pskit auto-stash")
    $out = git stash push -m $Message 2>&1
    @{ success = ($LASTEXITCODE -eq 0); output = ($out -join "`n") } | ConvertTo-Json -Compress
}

function Restore-PSKitGitStash {
    $out = git stash pop 2>&1
    @{ success = ($LASTEXITCODE -eq 0); output = ($out -join "`n") } | ConvertTo-Json -Compress
}

Export-ModuleMember -Function Read-PSKitFile, Write-PSKitFile, Edit-PSKitFile,
    Search-PSKitCode, Find-PSKitFiles,
    Get-PSKitGitStatus, Get-PSKitGitDiff, Get-PSKitGitLog,
    New-PSKitGitCommit, Save-PSKitGitStash, Restore-PSKitGitStash
