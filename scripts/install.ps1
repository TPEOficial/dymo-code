$InstallDir = "$env:LOCALAPPDATA\dymo-code"
$OutputFile = "$InstallDir\dymo-code.exe"
$GitHubUrl = "https://github.com/TPEOficial/dymo-code/releases/latest/download/dymo-code-windows-amd64.exe"
$MirrorUrl = "https://raw.githubusercontent.com/TPEOficial/dymo-code/main/dist/dymo-code-windows-amd64.exe"

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

for ($i=1; $i -le 3; $i++) {
    try {
        Invoke-WebRequest -Uri $GitHubUrl -OutFile $OutputFile
        break
    } catch {
        if ($i -eq 3) {
            Invoke-WebRequest -Uri $MirrorUrl -OutFile $OutputFile
        } else {
            Start-Sleep -Seconds 2
        }
    }
}

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$InstallDir", "User")
}

Write-Host "Installed successfully. Restart terminal and run: dymo-code"