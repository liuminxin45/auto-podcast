#!/usr/bin/env pwsh

[CmdletBinding()]
param(
    [string]$RepoRoot = (Get-Location).Path,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

function New-VersionResult {
    param([string]$Name)
    [ordered]@{
        tool = $Name
        status = "ok"
        facts = [ordered]@{}
        blockers = @()
        unknowns = @()
        hints = @()
    }
}

function Set-VersionBlocked {
    param($Result, [string]$Message)
    $Result.status = "blocked"
    $Result.blockers += $Message
}

function Read-PyprojectVersion {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    $text = Get-Content -LiteralPath $Path -Raw
    $nameMatch = [regex]::Match($text, '(?m)^\s*name\s*=\s*"([^"]+)"\s*$')
    $versionMatch = [regex]::Match($text, '(?m)^\s*version\s*=\s*"([^"]+)"\s*$')

    [PSCustomObject]@{
        package_name = if ($nameMatch.Success) { $nameMatch.Groups[1].Value } else { "" }
        version = if ($versionMatch.Success) { $versionMatch.Groups[1].Value } else { "" }
    }
}

$result = New-VersionResult "get-spec-kit-version"
$resolvedRoot = Resolve-Path -LiteralPath $RepoRoot -ErrorAction SilentlyContinue
if (-not $resolvedRoot) {
    Set-VersionBlocked $result "RepoRoot not found: $RepoRoot"
} else {
    $repoRootPath = $resolvedRoot.Path
    $pyproject = Join-Path $repoRootPath "pyproject.toml"
    $info = Read-PyprojectVersion -Path $pyproject
    if (-not $info) {
        Set-VersionBlocked $result "pyproject.toml not found"
    } elseif ([string]::IsNullOrWhiteSpace($info.version)) {
        Set-VersionBlocked $result "pyproject.toml missing [project] version"
    } else {
        $result.facts.repo_root = $repoRootPath
        $result.facts.version_source = "pyproject.toml"
        $result.facts.pyproject = $pyproject
        $result.facts.package_name = $info.package_name
        $result.facts.version = $info.version
        $result.facts.tag_name = "v$($info.version)"
        $result.facts.cli_distribution = "specify-cli"
        $result.hints += "pyproject.toml is the single source of truth for Spec Kit core version."
    }
}

if ($Json) {
    $result | ConvertTo-Json -Depth 8 -Compress
} else {
    if ($result.status -ne "ok") {
        foreach ($blocker in $result.blockers) { Write-Error $blocker }
        exit 1
    }
    Write-Output $result.facts.version
}
