# Dymo Code Installer - Windows
# Usage: iwr -useb https://raw.githubusercontent.com/TPEOficial/dymo-code/main/scripts/install.ps1 | iex

$ErrorActionPreference = "Stop"
$Repo = "TPEOficial/dymo-code"
$InstallDir = "$env:LOCALAPPDATA\dymo-code"
$OutputFile = "$InstallDir\dymo-code.exe"

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# URLs
$GitHubLatestReleaseApi = "https://api.github.com/repos/$Repo/releases/latest"
$MirrorUrl = "https://cdn.jsdelivr.net/gh/$Repo@main/dist/dymo-code-windows-amd64.exe"

function Download-Dymo {
    try {
        Write-Host "Trying to fetch latest release from GitHub..."
        $Release = Invoke-RestMethod -Uri $GitHubLatestReleaseApi
        $Version = $Release.tag_name
        $GitHubUrl = "https://github.com/$Repo/releases/download/$Version/dymo-code-windows-amd64.exe"
        Write-Host "Downloading from GitHub release $Version..."
        Invoke-WebRequest -Uri $GitHubUrl -OutFile $OutputFile
    } catch {
        Write-Host "GitHub download failed (rate limit or auth issue). Using mirror..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri $MirrorUrl -OutFile $OutputFile
    }
}

Download-Dymo

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
}

Write-Host "Installed successfully. Restart terminal and run: dymo-code"