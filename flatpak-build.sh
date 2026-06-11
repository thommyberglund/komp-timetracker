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

# Create build directory
BUILD_DIR="./flatpak-build"
REPO_DIR="./flatpak-repo"
APP_ID="com.komp_timetracker.KompTimeTracker"
MANIFEST="${APP_ID}.json"

mkdir -p "$BUILD_DIR"
mkdir -p "$REPO_DIR"

echo -e "${BLUE}Building Komp TimeTracker Flatpak...${NC}"

# Build the Flatpak - using syntax compatible with flatpak-builder on Bazzite
# The --build-dir and --repo flags might not be supported in older versions
# So we'll use the basic syntax that works across versions
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
    echo "Or create a desktop entry:"
    echo "  flatpak run --command=gtk-update-icon-cache $APP_ID -f -t"
    echo "  flatpak run --command=update-desktop-database $APP_ID"
else
    echo -e "${RED}✗ Build failed${NC}"
    echo
    echo "Trying alternative build method..."
    
    # Try building without --build-dir and --repo flags
    echo -e "${BLUE}Attempting build without build-dir flag...${NC}"
    flatpak-builder \
        --user \
        --install \
        --force-clean \
        "$MANIFEST"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Alternative build method succeeded!${NC}"
    else
        echo -e "${RED}✗ All build methods failed${NC}"
        echo
        echo "Please check your flatpak-builder version:"
        flatpak-builder --version
        echo
        echo "And try building manually with:"
        echo "  flatpak-builder --user --install $MANIFEST"
        exit 1
    fi
fi
