[CmdletBinding()]
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\GreyNOC\DMZ",
    [string]$ReleaseTag = "latest",
    [string]$Repo = "GreyNOC/DMZ",
    [switch]$AddToPath
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
}

$scriptDir = Split-Path -Parent $PSCommandPath
$localExe = Join-Path $scriptDir "greynoc-dmz.exe"
$sourceDir = $scriptDir
$tempRoot = $null

if (-not (Test-Path -LiteralPath $localExe)) {
    $assetName = "greynoc-dmz-windows-x64.zip"
    if ($ReleaseTag -eq "latest") {
        $releaseUrl = "https://github.com/$Repo/releases/latest/download/$assetName"
    } else {
        $releaseUrl = "https://github.com/$Repo/releases/download/$ReleaseTag/$assetName"
    }

    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("greynoc-dmz-install-" + [System.Guid]::NewGuid())
    $zipPath = Join-Path $tempRoot $assetName
    New-Item -ItemType Directory -Path $tempRoot | Out-Null

    Write-Step "Downloading $releaseUrl"
    Invoke-WebRequest -Uri $releaseUrl -OutFile $zipPath

    Write-Step "Extracting release bundle"
    Expand-Archive -LiteralPath $zipPath -DestinationPath $tempRoot -Force
    $sourceDir = $tempRoot
}

$sourceExe = Join-Path $sourceDir "greynoc-dmz.exe"
if (-not (Test-Path -LiteralPath $sourceExe)) {
    throw "Could not find greynoc-dmz.exe in $sourceDir"
}

Write-Step "Installing to $InstallDir"
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item -LiteralPath $sourceExe -Destination (Join-Path $InstallDir "greynoc-dmz.exe") -Force

foreach ($name in @("README.md", "SECURITY.md")) {
    $sourceFile = Join-Path $sourceDir $name
    if (Test-Path -LiteralPath $sourceFile) {
        Copy-Item -LiteralPath $sourceFile -Destination (Join-Path $InstallDir $name) -Force
    }
}

if ($AddToPath) {
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $pathItems = @()
    if ($currentPath) {
        $pathItems = $currentPath -split ";" | Where-Object { $_ }
    }
    if ($pathItems -notcontains $InstallDir) {
        $newPath = ($pathItems + $InstallDir) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Step "Added $InstallDir to the user PATH. Open a new terminal to use it by name."
    }
}

Write-Step "Verifying installed executable"
& (Join-Path $InstallDir "greynoc-dmz.exe") --help | Out-Null

if ($tempRoot) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
}

Write-Host "GreyNOC DMZ installed: $(Join-Path $InstallDir 'greynoc-dmz.exe')"
