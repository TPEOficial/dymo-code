#!/bin/bash
# Build script for macOS and Linux
# Creates a standalone executable

set -e

echo "============================================================"
echo "Building Dymo Code for $(uname -s)"
echo "============================================================"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 not found. Please install Python 3.8+"
    exit 1
fi

echo "Python version: $(python3 --version)"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Run the build
echo ""
echo "Starting build..."
python build.py --clean

echo ""
echo "Build complete! Check the dist/ folder for the executable."

# Make the output executable
if [ -f "dist/dymo-code-"* ]; then
    chmod +x dist/dymo-code-*
    echo "Executable permissions set."
fi
