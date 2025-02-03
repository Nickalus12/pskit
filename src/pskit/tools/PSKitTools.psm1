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

Export-ModuleMember -Function Read-PSKitFile, Write-PSKitFile, Search-PSKitCode, Find-PSKitFiles
