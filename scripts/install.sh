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
GITHUB_API="https://api.github.com/repos/${REPO}/releases/latest"
MIRROR_URL="https://cdn.jsdelivr.net/gh/${REPO}@main/dist/${BINARY}"

# Prepare install directory
mkdir -p "$INSTALL_DIR"

# Function to download
download_dymo() {
    echo "Trying to fetch latest release from GitHub..."
    VERSION=$(curl -fsSL "$GITHUB_API" | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')
    if [ -n "$VERSION" ]; then
        GITHUB_URL="https://github.com/${REPO}/releases/download/${VERSION}/${BINARY}"
        echo "Downloading from GitHub release $VERSION..."
        curl -fsSL "$GITHUB_URL" -o "$OUTPUT_FILE" && return 0
    fi
    echo "GitHub download failed (rate limit or auth issue). Using mirror..." >&2
    curl -fsSL "$MIRROR_URL" -o "$OUTPUT_FILE"
}

# Execute download
download_dymo

chmod +x "$OUTPUT_FILE"

# Add to PATH if needed
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> ~/.bashrc 2>/dev/null || true
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> ~/.zshrc 2>/dev/null || true
    export PATH="$PATH:$INSTALL_DIR"
fi

echo "Installed successfully. Run: dymo-code"