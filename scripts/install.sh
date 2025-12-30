#!/bin/bash
# Dymo Code Installer - Linux/macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/TPEOficial/dymo-code/main/scripts/install.sh | bash

set -e

REPO="TPEOficial/dymo-code"
INSTALL_DIR="${HOME}/.local/bin"

# Detect OS and set binary name.
case "$(uname -s)" in
    Linux*)  BINARY="dymo-code-linux-x86_64" ;;
    Darwin*) BINARY="dymo-code-macos-arm64" ;;
    *)       echo "Unsupported OS"; exit 1 ;;
esac

# Get latest version.
VERSION=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')
[ -z "$VERSION" ] && { echo "Failed to get version"; exit 1; }

# Download and install.
mkdir -p "$INSTALL_DIR"
curl -fsSL "https://github.com/${REPO}/releases/download/${VERSION}/${BINARY}" -o "${INSTALL_DIR}/dymo-code"
chmod +x "${INSTALL_DIR}/dymo-code"

# Add to PATH if needed.
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> ~/.bashrc 2>/dev/null || true
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> ~/.zshrc 2>/dev/null || true
    export PATH="$PATH:$INSTALL_DIR"
fi

echo "Installed successfully. Run: dymo-code"