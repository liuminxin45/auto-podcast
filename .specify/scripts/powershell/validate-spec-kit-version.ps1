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
        text = $text
    }
}

function Test-SemVer {
    param([string]$Version)
    return ($Version -match '^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$')
}

$result = New-VersionResult "validate-spec-kit-version"
$resolvedRoot = Resolve-Path -LiteralPath $RepoRoot -ErrorAction SilentlyContinue
if (-not $resolvedRoot) {
    Set-VersionBlocked $result "RepoRoot not found: $RepoRoot"
} else {
    $repoRootPath = $resolvedRoot.Path
    $pyproject = Join-Path $repoRootPath "pyproject.toml"
    $assets = Join-Path $repoRootPath "src/specify_cli/_assets.py"
    $versionModule = Join-Path $repoRootPath "src/specify_cli/_version.py"
    $info = Read-PyprojectVersion -Path $pyproject

    if (-not $info) {
        Set-VersionBlocked $result "pyproject.toml not found"
    } elseif ([string]::IsNullOrWhiteSpace($info.version)) {
        Set-VersionBlocked $result "pyproject.toml missing [project] version"
    } elseif (-not (Test-SemVer -Version $info.version)) {
        Set-VersionBlocked $result "Spec Kit version must be semantic version X.Y.Z with optional pre-release/build metadata"
    }

    if ($info -and $info.package_name -ne "specify-cli") {
        Set-VersionBlocked $result "pyproject.toml project.name must stay specify-cli"
    }

    if (-not (Test-Path -LiteralPath $assets -PathType Leaf)) {
        Set-VersionBlocked $result "src/specify_cli/_assets.py not found"
    } else {
        $assetsText = Get-Content -LiteralPath $assets -Raw
        if ($assetsText -notmatch 'importlib\.metadata\.version\("specify-cli"\)') {
            Set-VersionBlocked $result "_assets.py must read installed specify-cli distribution version"
        }
        if ($assetsText -notmatch 'pyproject\.toml') {
            Set-VersionBlocked $result "_assets.py must keep pyproject.toml fallback for source checkouts"
        }
    }

    if (-not (Test-Path -LiteralPath $versionModule -PathType Leaf)) {
        Set-VersionBlocked $result "src/specify_cli/_version.py not found"
    } else {
        $versionText = Get-Content -LiteralPath $versionModule -Raw
        if ($versionText -notmatch 'specify self check') {
            Set-VersionBlocked $result "_version.py must expose specify self check guidance"
        }
        if ($versionText -notmatch 'self upgrade is not implemented') {
            $result.hints += "self upgrade is implemented or wording changed; verify release docs before publishing."
        }
    }

    $tagExists = $false
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $null = git -C $repoRootPath rev-parse --is-inside-work-tree 2>$null
        if ($LASTEXITCODE -eq 0 -and $info -and $info.version) {
            $null = git -C $repoRootPath show-ref --tags --verify --quiet "refs/tags/v$($info.version)"
            $tagExists = ($LASTEXITCODE -eq 0)
        }
    }

    $result.facts.repo_root = $repoRootPath
    $result.facts.version_source = "pyproject.toml"
    $result.facts.pyproject = $pyproject
    $result.facts.package_name = if ($info) { $info.package_name } else { "" }
    $result.facts.version = if ($info) { $info.version } else { "" }
    $result.facts.tag_name = if ($info -and $info.version) { "v$($info.version)" } else { "" }
    $result.facts.tag_exists = $tagExists
    $result.facts.assets_version_lookup = $assets
    $result.facts.self_check_module = $versionModule
    $result.hints += "Create the git tag only after the version bump commit is validated."
}

if ($Json) {
    $result | ConvertTo-Json -Depth 8 -Compress
} else {
    if ($result.status -ne "ok") {
        foreach ($blocker in $result.blockers) { Write-Error $blocker }
        exit 1
    }
    Write-Output "Spec Kit version is valid: $($result.facts.version)"
}
