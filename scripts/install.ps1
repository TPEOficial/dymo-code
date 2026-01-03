# Dymo Code Installer - Windows
# Usage: iwr -useb https://raw.githubusercontent.com/TPEOficial/dymo-code/main/scripts/install.ps1 | iex

$ErrorActionPreference = "Stop"
$InstallDir = "$env:LOCALAPPDATA\dymo-code"
$OutputFile = "$InstallDir\dymo-code.exe"

# URLs
$GitHubUrl = "https://github.com/TPEOficial/dymo-code/releases/latest/download/dymo-code-windows-amd64.exe"
$MirrorUrl = "https://raw.githubusercontent.com/TPEOficial/dymo-code/main/dist/dymo-code-windows-amd64.exe"

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Download-Dymo {
    for ($i=1; $i -le 3; $i++) {
        try {
            Write-Host "Attempt $i: Downloading from GitHub..."
            Invoke-WebRequest -Uri $GitHubUrl -OutFile $OutputFile
            Write-Host "Download successful from GitHub."
            return
        } catch {
            Write-Host "Attempt $i failed. Retrying..." -ForegroundColor Yellow
            Start-Sleep -Seconds 2
        }
    }
    Write-Host "GitHub download failed. Trying mirror..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $MirrorUrl -OutFile $OutputFile
}

Download-Dymo

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
}

Write-Host "Installed successfully. Restart terminal and run: dymo-code"