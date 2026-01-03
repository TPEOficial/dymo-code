#!/bin/bash
set -e

INSTALL_DIR="${HOME}/.local/bin"
OUTPUT_FILE="${INSTALL_DIR}/dymo-code"
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
    *) echo "Unsupported OS"; exit 1 ;;
esac

GITHUB_URL="https://github.com/TPEOficial/dymo-code/releases/latest/download/${BINARY}"
MIRROR_URL="https://raw.githubusercontent.com/TPEOficial/dymo-code/main/dist/${BINARY}"

mkdir -p "$INSTALL_DIR"

for i in 1 2 3; do
    if curl -fsSL "$GITHUB_URL" -o "$OUTPUT_FILE"; then
        break
    elif [ "$i" -eq 3 ]; then
        curl -fsSL "$MIRROR_URL" -o "$OUTPUT_FILE"
    else
        sleep 2
    fi
done

chmod +x "$OUTPUT_FILE"

if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> ~/.bashrc 2>/dev/null || true
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> ~/.zshrc 2>/dev/null || true
    export PATH="$PATH:$INSTALL_DIR"
fi

echo "Installed successfully. Run: dymo-code"