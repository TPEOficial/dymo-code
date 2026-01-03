#!/bin/bash
# Dymo Code Installer - Linux/macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/TPEOficial/dymo-code/main/scripts/install.sh | bash

set -e

REPO="TPEOficial/dymo-code"
INSTALL_DIR="${HOME}/.local/bin"
OUTPUT_FILE="${INSTALL_DIR}/dymo-code"

# Detect OS and architecture
OS=$(uname -s)
ARCH=$(uname -m)

case "$OS" in
    Linux)
        case "$ARCH" in
            x86_64) BINARY="dymo-code-linux-x86_64" ;;
            aarch64) BINARY="dymo-code-linux-arm64" ;;
            *) echo "Unsupported architecture"; exit 1 ;;
        esac
        ;;
    Darwin)
        case "$ARCH" in
            arm64) BINARY="dymo-code-macos-arm64" ;;
            x86_64) BINARY="dymo-code-macos-x86_64" ;;
            *) echo "Unsupported architecture"; exit 1 ;;
        esac
        ;;
    *)
        echo "Unsupported OS"; exit 1 ;;
esac

# URLs
GITHUB_URL="https://github.com/${REPO}/releases/latest/download/${BINARY}"
MIRROR_URL="https://raw.githubusercontent.com/${REPO}/main/dist/${BINARY}"

mkdir -p "$INSTALL_DIR"

download_dymo() {
    for i in 1 2 3; do
        echo "Attempt $i: Downloading from GitHub..."
        if curl -fsSL "$GITHUB_URL" -o "$OUTPUT_FILE"; then
            echo "Download successful from GitHub."
            return
        else
            echo "Attempt $i failed. Retrying..." >&2
            sleep 2
        fi
    done
    echo "GitHub download failed. Trying mirror..." >&2
    curl -fsSL "$MIRROR_URL" -o "$OUTPUT_FILE"
}

download_dymo
chmod +x "$OUTPUT_FILE"

if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> ~/.bashrc 2>/dev/null || true
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> ~/.zshrc 2>/dev/null || true
    export PATH="$PATH:$INSTALL_DIR"
fi

echo "Installed successfully. Run: dymo-code"