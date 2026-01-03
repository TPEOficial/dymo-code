#!/bin/bash
set -e

INSTALL_DIR="${HOME}/.local/bin"
OUTPUT_FILE="${INSTALL_DIR}/dymo-code"
OS=$(uname -s)
ARCH=$(uname -m)

echo "Installing Dymo Code..."

# Detect OS and architecture
case "$OS" in
    Linux)
        case "$ARCH" in
            x86_64) BINARY="dymo-code-linux-x86_64" ;;
            aarch64|arm64) BINARY="dymo-code-linux-arm64" ;;
            *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
        esac
        ;;
    Darwin)
        case "$ARCH" in
            arm64) BINARY="dymo-code-macos-arm64" ;;
            x86_64) BINARY="dymo-code-macos-x86_64" ;;
            *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
        esac
        ;;
    MINGW*|MSYS*|CYGWIN*)
        BINARY="dymo-code-windows-amd64.exe"
        ;;
    *) echo "Unsupported OS: $OS"; exit 1 ;;
esac

DOWNLOAD_URL="https://github.com/TPEOficial/dymo-code/releases/latest/download/${BINARY}"

# Create install directory
mkdir -p "$INSTALL_DIR"

# Download with retry
max_retries=3
success=false

for i in $(seq 1 $max_retries); do
    echo "Downloading from GitHub (attempt $i/$max_retries)..."

    if curl -fsSL --user-agent "Dymo-Code-Installer/1.0" -o "$OUTPUT_FILE" "$DOWNLOAD_URL"; then
        # Verify download (at least 1MB)
        file_size=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null || echo "0")
        if [ "$file_size" -gt 1000000 ]; then
            success=true
            echo "Download complete ($(echo "scale=2; $file_size/1048576" | bc 2>/dev/null || echo "$file_size bytes"))"
            break
        else
            echo "Downloaded file too small, retrying..."
            rm -f "$OUTPUT_FILE"
        fi
    else
        echo "Attempt $i failed"
    fi

    if [ "$i" -lt "$max_retries" ]; then
        sleep 2
    fi
done

if [ "$success" = false ]; then
    echo ""
    echo "Failed to download after $max_retries attempts."
    echo ""
    echo "Manual installation instructions:"
    echo "  1. Save the file to: $OUTPUT_FILE"
    echo "  2. File name must be: dymo-code"
    echo ""
    echo "Press Enter to open the download page in your browser..."
    read -r

    # Open browser based on OS
    if command -v xdg-open > /dev/null; then
        xdg-open "$DOWNLOAD_URL"
    elif command -v open > /dev/null; then
        open "$DOWNLOAD_URL"
    else
        echo "Could not open browser. Please visit:"
        echo "$DOWNLOAD_URL"
    fi

    echo ""
    echo "After downloading, move the file to:"
    echo "$OUTPUT_FILE"
    echo ""
    echo "Then run: chmod +x $OUTPUT_FILE"
    exit 1
fi

# Make executable
chmod +x "$OUTPUT_FILE"

# Add to PATH in shell configs
add_to_path() {
    local shell_rc="$1"
    if [ -f "$shell_rc" ]; then
        if ! grep -q "$INSTALL_DIR" "$shell_rc" 2>/dev/null; then
            echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> "$shell_rc"
        fi
    fi
}

add_to_path "$HOME/.bashrc"
add_to_path "$HOME/.zshrc"
add_to_path "$HOME/.profile"

# Export for current session
export PATH="$PATH:$INSTALL_DIR"

echo ""
echo "Installed successfully!"
echo "Restart your terminal or run: source ~/.bashrc"
echo "Then run: dymo-code"