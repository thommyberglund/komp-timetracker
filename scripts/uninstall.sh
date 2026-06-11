#!/bin/bash

# Komp TimeTracker Uninstallation Script
# This script removes the parental control system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    exit 1
fi

echo -e "${BLUE}Uninstalling Komp TimeTracker...${NC}"

# Stop services
echo -e "${BLUE}Stopping services...${NC}"
systemctl stop komp-timetracker.service 2>/dev/null || true
systemctl stop komp-timetracker-monitor.service 2>/dev/null || true
systemctl stop komp-timetracker-enforcer.service 2>/dev/null || true

# Disable services
echo -e "${BLUE}Disabling services...${NC}"
systemctl disable komp-timetracker.service 2>/dev/null || true
systemctl disable komp-timetracker-monitor.service 2>/dev/null || true
systemctl disable komp-timetracker-enforcer.service 2>/dev/null || true

# Remove systemd service files
echo -e "${BLUE}Removing systemd service files...${NC}"
rm -f /etc/systemd/system/komp-timetracker.service
rm -f /etc/systemd/system/komp-timetracker-monitor.service
rm -f /etc/systemd/system/komp-timetracker-enforcer.service

# Reload systemd
echo -e "${BLUE}Reloading systemd...${NC}"
systemctl daemon-reload

# Remove CLI tool
echo -e "${BLUE}Removing CLI tool...${NC}"
rm -f /usr/local/bin/komp-control

# Remove configuration and data
echo -e "${BLUE}Removing configuration and data...${NC}"
rm -rf /etc/komp-timetracker
rm -rf /var/lib/komp-timetracker
rm -rf /var/log/komp-timetracker

echo -e "${GREEN}Uninstallation completed!${NC}"
echo
echo "All Komp TimeTracker files and services have been removed."
