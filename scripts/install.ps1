$ErrorActionPreference = "Stop"
$InstallDir = "$env:LOCALAPPDATA\Dymo-Code"
$BinDir = "$InstallDir\bin"
$OutputFile = "$BinDir\dymo-code.exe"
$DownloadUrl = "https://github.com/TPEOficial/dymo-code/releases/latest/download/dymo-code-windows-amd64.exe"

Write-Host "Installing Dymo Code..." -ForegroundColor Cyan

# Create directories
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null

# Set TLS 1.2
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Download with retry
$maxRetries = 3
$success = $false

for ($i = 1; $i -le $maxRetries; $i++) {
    try {
        Write-Host "Downloading from GitHub (attempt $i/$maxRetries)..." -ForegroundColor Gray

        # Use WebClient for better compatibility with redirects
        $webClient = New-Object System.Net.WebClient
        $webClient.Headers.Add("User-Agent", "Dymo-Code-Installer/1.0")
        $webClient.DownloadFile($DownloadUrl, $OutputFile)

        # Verify download
        if (Test-Path $OutputFile) {
            $fileSize = (Get-Item $OutputFile).Length
            if ($fileSize -gt 1000000) {  # At least 1MB
                $success = $true
                Write-Host "Download complete ($([math]::Round($fileSize/1MB, 2)) MB)" -ForegroundColor Green
                break
            } else {
                Write-Host "Downloaded file too small, retrying..." -ForegroundColor Yellow
                Remove-Item $OutputFile -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
        Write-Host "Attempt $i failed: $($_.Exception.Message)" -ForegroundColor Yellow
        if ($i -lt $maxRetries) {
            Start-Sleep -Seconds 2
        }
    }
}

if (-not $success) {
    Write-Host ""
    Write-Host "Failed to download after $maxRetries attempts." -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual installation instructions:" -ForegroundColor Yellow
    Write-Host "  1. Save the file to: " -NoNewline -ForegroundColor White
    Write-Host $OutputFile -ForegroundColor Cyan
    Write-Host "  2. File name must be: " -NoNewline -ForegroundColor White
    Write-Host "dymo-code.exe" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Press Enter to open the download page in your browser..." -ForegroundColor Gray
    $null = Read-Host
    Start-Process $DownloadUrl
    Write-Host ""
    Write-Host "After downloading, move the file to:" -ForegroundColor Yellow
    Write-Host $OutputFile -ForegroundColor Cyan
    exit 1
}

# Add to PATH
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    Write-Host "Added to PATH" -ForegroundColor Green
}

Write-Host ""
Write-Host "Installed successfully!" -ForegroundColor Green
Write-Host "Restart your terminal and run: dymo-code" -ForegroundColor Cyan