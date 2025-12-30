# Dymo Code Installer - Windows
# Usage: iwr -useb https://raw.githubusercontent.com/TPEOficial/dymo-code/main/scripts/install.ps1 | iex

$ErrorActionPreference = "Stop"
$Repo = "TPEOficial/dymo-code"
$InstallDir = "$env:LOCALAPPDATA\dymo-code"

# Get latest version.
$Release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest"
$Version = $Release.tag_name
$DownloadUrl = "https://github.com/$Repo/releases/download/$Version/dymo-code-windows-amd64.exe"

# Download and install.
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $DownloadUrl -OutFile "$InstallDir\dymo-code.exe"

# Add to PATH.
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
}

Write-Host "Installed successfully. Restart terminal and run: dymo-code"