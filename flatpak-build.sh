#!/bin/bash

# Flatpak Build Script for Komp TimeTracker
# This script builds and installs the Flatpak version

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if flatpak is installed
if ! command -v flatpak &> /dev/null; then
    echo -e "${RED}Error: flatpak is not installed${NC}"
    echo "Install flatpak first:"
    echo "  sudo dnf install flatpak"
    exit 1
fi

# Check if flatpak-builder is installed
if ! command -v flatpak-builder &> /dev/null; then
    echo -e "${YELLOW}flatpak-builder not found, installing...${NC}"
    sudo dnf install flatpak-builder
fi

# Check and install required runtimes
RUNTIME="org.freedesktop.Platform"
SDK="org.freedesktop.Sdk"
RUNTIME_VERSION="22.08"

APP_ID="com.komp_timetracker.KompTimeTracker"
MANIFEST="$SCRIPT_DIR/$APP_ID.json"

echo -e "${BLUE}Checking required runtimes...${NC}"

# Check if Flathub is added
if ! flatpak remote-list | grep -q flathub; then
    echo -e "${YELLOW}Adding Flathub repository...${NC}"
    flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
fi

# Install runtime if not present
if ! flatpak list --app | grep -q "${RUNTIME} ${RUNTIME_VERSION}"; then
    echo -e "${YELLOW}Installing ${RUNTIME} ${RUNTIME_VERSION}...${NC}"
    flatpak install flathub ${RUNTIME}//${RUNTIME_VERSION} -y
fi

# Install SDK if not present
if ! flatpak list --app | grep -q "${SDK} ${RUNTIME_VERSION}"; then
    echo -e "${YELLOW}Installing ${SDK} ${RUNTIME_VERSION}...${NC}"
    flatpak install flathub ${SDK}//${RUNTIME_VERSION} -y
fi

# Create build directory
BUILD_DIR="$SCRIPT_DIR/flatpak-build"
mkdir -p "$BUILD_DIR"

echo -e "${BLUE}Building Komp TimeTracker Flatpak...${NC}"

# First, uninstall any existing version
if flatpak list --user | grep -q "$APP_ID"; then
    echo -e "${YELLOW}Uninstalling existing version...${NC}"
    flatpak uninstall --user "$APP_ID" -y || true
fi

# Build the Flatpak from the script directory
cd "$SCRIPT_DIR"

# Use --force-clean to ensure a clean build
flatpak-builder \
    --user \
    --install \
    --force-clean \
    "$BUILD_DIR" \
    "$MANIFEST"

# Check if build succeeded
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Komp TimeTracker installed as Flatpak${NC}"
    echo
    echo "You can now run:"
    echo "  flatpak run $APP_ID --help"
    echo
    echo "Or check installation:"
    echo "  flatpak list | grep komp_timetracker"
    echo
    echo "To test the application:"
    echo "  flatpak run $APP_ID status"
    echo "  flatpak run $APP_ID add-user testuser"
    echo
    echo "Note: The first run may take a moment to set up the configuration."
else
    echo -e "${RED}✗ Build failed${NC}"
    echo
    echo "Trying alternative build method..."
    
    # Try building without specifying build directory
    flatpak-builder \
        --user \
        --install \
        --force-clean \
        "$MANIFEST"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Alternative build method succeeded!${NC}"
        echo
        echo "You can now run:"
        echo "  flatpak run $APP_ID --help"
    else
        echo -e "${RED}✗ All build methods failed${NC}"
        echo
        echo "Please check your flatpak setup:"
        echo "  flatpak --version"
        echo "  flatpak-builder --version"
        echo "  flatpak list --app | grep freedesktop"
        echo
        echo "And try building manually from the repo directory:"
        echo "  cd $SCRIPT_DIR"
        echo "  flatpak-builder --user --install $APP_ID.json"
        exit 1
    fi
fi

echo -e "${GREEN}Build process completed!${NC}"
