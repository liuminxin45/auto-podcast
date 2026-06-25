#!/usr/bin/env pwsh

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Version,
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

function Test-SemVer {
    param([string]$Value)
    return ($Value -match '^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$')
}

$result = New-VersionResult "bump-spec-kit-version"
$resolvedRoot = Resolve-Path -LiteralPath $RepoRoot -ErrorAction SilentlyContinue
if (-not $resolvedRoot) {
    Set-VersionBlocked $result "RepoRoot not found: $RepoRoot"
} elseif (-not (Test-SemVer -Value $Version)) {
    Set-VersionBlocked $result "Version must be semantic version X.Y.Z with optional pre-release/build metadata"
} else {
    $repoRootPath = $resolvedRoot.Path
    $pyproject = Join-Path $repoRootPath "pyproject.toml"
    if (-not (Test-Path -LiteralPath $pyproject -PathType Leaf)) {
        Set-VersionBlocked $result "pyproject.toml not found"
    } else {
        $text = Get-Content -LiteralPath $pyproject -Raw
        $versionMatch = [regex]::Match($text, '(?m)^version\s*=\s*"([^"]+)"\s*$')
        if (-not $versionMatch.Success) {
            Set-VersionBlocked $result "pyproject.toml missing project version line"
        } else {
            $current = $versionMatch.Groups[1].Value
            $updated = [regex]::Replace($text, '(?m)^version\s*=\s*"([^"]+)"\s*$', "version = `"$Version`"", 1)
            if ($updated -ne $text) {
                Set-Content -LiteralPath $pyproject -Value $updated -Encoding UTF8
            }
            $result.facts.repo_root = $repoRootPath
            $result.facts.pyproject = $pyproject
            $result.facts.previous_version = $current
            $result.facts.version = $Version
            $result.facts.tag_name = "v$Version"
            $result.facts.changed = ($current -ne $Version)
            $result.hints += "Run validate-spec-kit-version.ps1 before committing the version bump."
            $result.hints += "Create tag v$Version only after the version bump commit is validated."
        }
    }
}

if ($Json) {
    $result | ConvertTo-Json -Depth 8 -Compress
} else {
    if ($result.status -ne "ok") {
        foreach ($blocker in $result.blockers) { Write-Error $blocker }
        exit 1
    }
    Write-Output "Spec Kit version: $($result.facts.previous_version) -> $($result.facts.version)"
    Write-Output "Next tag: $($result.facts.tag_name)"
}
