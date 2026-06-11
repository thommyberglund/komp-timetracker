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

# Install Python dependencies system-wide to avoid network issues in sandbox
echo -e "${BLUE}Installing Python dependencies system-wide...${NC}"
if [ -f requirements.txt ]; then
    sudo pip3 install -r requirements.txt 2>/dev/null || {
        echo -e "${YELLOW}Warning: Could not install Python dependencies system-wide${NC}"
        echo "You may need to install them manually:"
        echo "  sudo pip3 install pyyaml pydantic click rich psutil"
    }
fi

# Create build directory
BUILD_DIR="./flatpak-build"
APP_ID="com.komp_timetracker.KompTimeTracker"
MANIFEST="${APP_ID}.json"

mkdir -p "$BUILD_DIR"

echo -e "${BLUE}Building Komp TimeTracker Flatpak...${NC}"

# Build the Flatpak
flatpak-builder \
    --user \
    --install \
    --force-clean \
    "$BUILD_DIR" \
    "$MANIFEST"

echo -e "${GREEN}Build completed!${NC}"

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
    echo "Note: If you get Python module errors, run:"
    echo "  flatpak run $APP_ID status"
    echo "This will install any missing Python modules on first run."
else
    echo -e "${RED}✗ Build failed${NC}"
    echo
    echo "Trying alternative build method without build directory..."
    
    # Try building without specifying build directory
    flatpak-builder \
        --user \
        --install \
        --force-clean \
        "$MANIFEST"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Alternative build method succeeded!${NC}"
        echo
        echo "Note: If you get Python module errors, run:"
        echo "  flatpak run $APP_ID status"
    else
        echo -e "${RED}✗ All build methods failed${NC}"
        echo
        echo "Please check your flatpak setup:"
        echo "  flatpak --version"
        echo "  flatpak-builder --version"
        echo "  flatpak list --app | grep freedesktop"
        echo
        echo "And try building manually with:"
        echo "  flatpak-builder --user --install $MANIFEST"
        exit 1
    fi
fi
