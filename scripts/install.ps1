# Dymo Code Installer - Windows
# Usage: iwr -useb https://raw.githubusercontent.com/TPEOficial/dymo-code/main/scripts/install.ps1 | iex.

$ErrorActionPreference = "Stop"
$Repo = "TPEOficial/dymo-code"
$InstallDir = "$env:LOCALAPPDATA\dymo-code"

# Get latest version.
try {
    $Release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest"
    $Version = $Release.tag_name
} catch {
    Write-Host "Failed to fetch release info from GitHub." -ForegroundColor Yellow
    throw
}

$GitHubUrl = "https://github.com/$Repo/releases/download/$Version/dymo-code-windows-amd64.exe"
$MirrorUrl = "https://cdn.jsdelivr.net/gh/$Repo@main/dist/dymo-code-windows-amd64.exe"
$OutputFile = "$InstallDir\dymo-code.exe"

# Prepare install directory.
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Download with fallback.
try {
    Invoke-WebRequest -Uri $GitHubUrl -OutFile $OutputFile
} catch {
    Write-Host "GitHub download failed. Trying mirror..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $MirrorUrl -OutFile $OutputFile
}

# Add to PATH.
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
}

Write-Host "Installed successfully. Restart terminal and run: dymo-code"