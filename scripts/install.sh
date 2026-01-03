#!/bin/bash
# Dymo Code Installer - Linux/macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/TPEOficial/dymo-code/main/scripts/install.sh | bash

set -e

REPO="TPEOficial/dymo-code"
INSTALL_DIR="${HOME}/.local/bin"

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

# Get latest version
VERSION=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
          | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')
[ -z "$VERSION" ] && { echo "Failed to get version"; exit 1; }

GITHUB_URL="https://github.com/${REPO}/releases/download/${VERSION}/${BINARY}"
MIRROR_URL="https://cdn.jsdelivr.net/gh/${REPO}@main/dist/${BINARY}"

# Prepare install directory
mkdir -p "$INSTALL_DIR"

# Download with fallback
if ! curl -fsSL "$GITHUB_URL" -o "${INSTALL_DIR}/dymo-code"; then
    echo "GitHub download failed. Trying mirror..."
    curl -fsSL "$MIRROR_URL" -o "${INSTALL_DIR}/dymo-code"
fi

chmod +x "${INSTALL_DIR}/dymo-code"

# Add to PATH if needed
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> ~/.bashrc 2>/dev/null || true
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> ~/.zshrc 2>/dev/null || true
    export PATH="$PATH:$INSTALL_DIR"
fi

echo "Installed successfully. Run: dymo-code"