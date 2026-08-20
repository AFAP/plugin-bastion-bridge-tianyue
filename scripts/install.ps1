# Install the TianYue bastion bridge skill for DeepSeek Harness.
# Use -InstallBridge to also download the bridge EXE from GitHub Releases.
#
# Remote skill install:
#   powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/AFAP/plugin-bastion-bridge-tianyue/main/scripts/install.ps1 | iex"
# Local skill + bridge install:
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -InstallBridge
#
# Arguments are parsed from $args so both irm | iex and -File remain supported.
$Owner = ""
$Repo = "plugin-bastion-bridge-tianyue"
$Ref = "main"
$InstallBridge = $false
$BridgeTag = "latest"
$WhatIf = $false

for ($i = 0; $i -lt $args.Count; $i++) {
    switch -Regex ($args[$i]) {
        '^(-|/)InstallBridge$' { $InstallBridge = $true }
        '^(-|/)Owner$'        { $i++; if ($i -lt $args.Count) { $Owner = $args[$i] } }
        '^(-|/)Repo$'         { $i++; if ($i -lt $args.Count) { $Repo = $args[$i] } }
        '^(-|/)Ref$'          { $i++; if ($i -lt $args.Count) { $Ref = $args[$i] } }
        '^(-|/)BridgeTag$'    { $i++; if ($i -lt $args.Count) { $BridgeTag = $args[$i] } }
        '^(-|/)WhatIf$'       { $WhatIf = $true }
    }
}

$DefaultOwner = "AFAP"
if (-not $Owner) { $Owner = $DefaultOwner }
$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "    [OK] $Message" -ForegroundColor Green }
function Write-Warn2([string]$Message) { Write-Host "    [NOTE] $Message" -ForegroundColor Yellow }

function Resolve-SkillsRoot {
    if ($env:DSH_HOME -and $env:DSH_HOME.Trim().Length -gt 0) {
        return Join-Path $env:DSH_HOME "skills"
    }
    return Join-Path $HOME ".dsh\skills"
}

$SkillsRoot = Resolve-SkillsRoot
$SkillTarget = Join-Path $SkillsRoot "bastion-tianyue"
$LegacySkillTarget = Join-Path $SkillsRoot "tianyue-bastion"
$ScriptDir = $null
if ($PSScriptRoot) { $ScriptDir = $PSScriptRoot }
$BundleSource = $null
$LocalBundle = $null
if ($ScriptDir) { $LocalBundle = Join-Path $ScriptDir "..\skill\bastion-tianyue" }

if ($LocalBundle -and (Test-Path (Join-Path $LocalBundle "SKILL.md"))) {
    $BundleSource = $LocalBundle
    Write-Step "Using local skill bundle: $LocalBundle"
} else {
    $ZipUrl = "https://codeload.github.com/$Owner/$Repo/zip/refs/heads/$Ref"
    $ZipPath = Join-Path $env:TEMP "$Repo-$Ref.zip"
    $ExtractDir = Join-Path $env:TEMP "$Repo-$Ref"
    Write-Step "Downloading skill bundle: $ZipUrl"
    if (-not $WhatIf) {
        Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath -UseBasicParsing
        if (Test-Path $ExtractDir) { Remove-Item $ExtractDir -Recurse -Force }
        Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force
        $RefFolder = $Ref -replace '/', '-'
        $BundleSource = Join-Path $ExtractDir "$Repo-$RefFolder\skill\bastion-tianyue"
    }
}

if (-not $WhatIf -and -not (Test-Path (Join-Path $BundleSource "SKILL.md"))) {
    Write-Host "ERROR: SKILL.md was not found at $BundleSource" -ForegroundColor Red
    exit 1
}

Write-Step "Installing the DSH skill to: $SkillTarget"
if (-not $WhatIf) {
    if (Test-Path $SkillTarget) { Remove-Item $SkillTarget -Recurse -Force }
    if (Test-Path $LegacySkillTarget) {
        Remove-Item $LegacySkillTarget -Recurse -Force
        Write-Ok "Removed the legacy tianyue-bastion skill."
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $SkillTarget -Parent) | Out-Null
    Copy-Item -Path $BundleSource -Destination $SkillTarget -Recurse
    Get-ChildItem $SkillTarget -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Ok "The skill is installed."
} else {
    Write-Warn2 "WhatIf: copy $BundleSource -> $SkillTarget"
    Write-Warn2 "WhatIf: remove legacy skill if present: $LegacySkillTarget"
}

if ($InstallBridge) {
    $ExeName = "tianyue_ssh_bridge.exe"
    $ExeUrl = "https://github.com/$Owner/$Repo/releases/latest/download/$ExeName"
    if ($BridgeTag -ne "latest") {
        $ExeUrl = "https://github.com/$Owner/$Repo/releases/download/$BridgeTag/$ExeName"
    }
    $BridgeDir = Join-Path $env:LOCALAPPDATA "sshbridge\TianYueSSHBridge\bin"
    $BridgePath = Join-Path $BridgeDir $ExeName
    Write-Step "Downloading the bridge: $ExeUrl"
    if (-not $WhatIf) {
        New-Item -ItemType Directory -Force -Path $BridgeDir | Out-Null
        Invoke-WebRequest -Uri $ExeUrl -OutFile $BridgePath -UseBasicParsing
        Write-Ok "Bridge downloaded to: $BridgePath"
    } else {
        Write-Warn2 "WhatIf: download $ExeUrl -> $BridgePath"
    }
    Write-Host "Set the TianYue local SSH/SecureCRT tool path to the EXE above."
}

Write-Host "Installation complete. Invoke /bastion-tianyue in DSH or assign an authorized operations task." -ForegroundColor Green
