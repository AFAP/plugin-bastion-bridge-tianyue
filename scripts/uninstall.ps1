# Uninstall the TianYue bastion bridge skill for DeepSeek Harness.
# Use -RemoveBridge to also delete the EXE downloaded by install.ps1.
#
#   powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1 -RemoveBridge
$RemoveBridge = $false
$WhatIf = $false

for ($i = 0; $i -lt $args.Count; $i++) {
    switch -Regex ($args[$i]) {
        '^(-|/)RemoveBridge$' { $RemoveBridge = $true }
        '^(-|/)WhatIf$'       { $WhatIf = $true }
    }
}

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "    [OK] $Message" -ForegroundColor Green }
function Write-Warn2([string]$Message) { Write-Host "    [NOTE] $Message" -ForegroundColor Yellow }

$SkillTarget = Join-Path $HOME ".dsh\skills\tianyue-bastion"
if ($env:DSH_HOME -and $env:DSH_HOME.Trim().Length -gt 0) {
    $SkillTarget = Join-Path $env:DSH_HOME "skills\tianyue-bastion"
}

Write-Step "Removing the DSH skill: $SkillTarget"
if (Test-Path $SkillTarget) {
    if (-not $WhatIf) {
        Remove-Item $SkillTarget -Recurse -Force
        Write-Ok "The skill was removed."
    } else {
        Write-Warn2 "WhatIf: remove $SkillTarget"
    }
} else {
    Write-Ok "The skill is not installed."
}

if ($RemoveBridge) {
    $BridgePath = Join-Path $env:LOCALAPPDATA "sshbridge\TianYueSSHBridge\bin\tianyue_ssh_bridge.exe"
    Write-Step "Removing the bridge: $BridgePath"
    if (Test-Path $BridgePath) {
        if (-not $WhatIf) {
            Remove-Item $BridgePath -Force
            Write-Ok "The bridge was removed."
        } else {
            Write-Warn2 "WhatIf: remove $BridgePath"
        }
    } else {
        Write-Ok "The bridge is not installed."
    }
}

Write-Host "Uninstall complete." -ForegroundColor Green
