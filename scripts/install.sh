#!/bin/bash

# Komp TimeTracker Installation Script for Bazzite Linux
# This script installs the parental control system

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

# Detect Bazzite
if [ ! -f /etc/os-release ] || ! grep -qi bazzite /etc/os-release; then
    echo -e "${YELLOW}Warning: This script is designed for Bazzite Linux${NC}"
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${BLUE}Installing Komp TimeTracker on Bazzite Linux...${NC}"

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
dnf install -y python3 python3-pip python3-systemd python3-psutil git

# Install Python dependencies
echo -e "${BLUE}Installing Python packages...${NC}"
pip3 install pyyaml pydantic click rich

# Create directories
echo -e "${BLUE}Creating directories...${NC}"
mkdir -p /etc/komp-timetracker
mkdir -p /var/lib/komp-timetracker
mkdir -p /var/log/komp-timetracker
mkdir -p /usr/local/bin

# Copy configuration files
echo -e "${BLUE}Installing configuration...${NC}"
cp config.yaml /etc/komp-timetracker/config.yaml 2>/dev/null || true

# Create default config if it doesn't exist
if [ ! -f /etc/komp-timetracker/config.yaml ]; then
    cat > /etc/komp-timetracker/config.yaml << 'EOF'
system:
  enforcement_method: "flatpak"
  grace_period: "5m"
  monitoring_enabled: true
  data_retention_days: 30

users: {}

monitoring:
  track_apps: true
  track_web: true
  retention_days: 30
EOF
fi

# Install systemd services
echo -e "${BLUE}Installing systemd services...${NC}"
cp packaging/systemd/komp-timetracker.service /etc/systemd/system/
cp packaging/systemd/komp-timetracker-monitor.service /etc/systemd/system/
cp packaging/systemd/komp-timetracker-enforcer.service /etc/systemd/system/

# Reload systemd
echo -e "${BLUE}Reloading systemd...${NC}"
systemctl daemon-reload

# Enable services
echo -e "${BLUE}Enabling services...${NC}"
systemctl enable komp-timetracker.service
systemctl enable komp-timetracker-monitor.service
systemctl enable komp-timetracker-enforcer.service

# Install CLI tool
echo -e "${BLUE}Installing CLI tool...${NC}"
cat > /usr/local/bin/komp-control << 'EOF'
#!/bin/bash
python3 -m komp_timetracker.ui.cli "$@"
EOF
chmod +x /usr/local/bin/komp-control

# Set permissions
echo -e "${BLUE}Setting permissions...${NC}"
chown -R root:root /etc/komp-timetracker
chmod -R 755 /etc/komp-timetracker
chown -R root:root /var/lib/komp-timetracker
chmod -R 755 /var/lib/komp-timetracker
chown -R root:root /var/log/komp-timetracker
chmod -R 755 /var/log/komp-timetracker

# Start services
echo -e "${BLUE}Starting services...${NC}"
systemctl start komp-timetracker.service
systemctl start komp-timetracker-monitor.service
systemctl start komp-timetracker-enforcer.service

# Verify installation
echo -e "${BLUE}Verifying installation...${NC}"
if command -v komp-control &> /dev/null; then
    echo -e "${GREEN}✓ komp-control CLI installed successfully${NC}"
else
    echo -e "${RED}✗ komp-control CLI installation failed${NC}"
fi

if systemctl is-active komp-timetracker.service &> /dev/null; then
    echo -e "${GREEN}✓ komp-timetracker.service is running${NC}"
else
    echo -e "${RED}✗ komp-timetracker.service failed to start${NC}"
fi

echo -e "${GREEN}Installation completed!${NC}"
echo
echo "Usage:"
echo "  komp-control status              # Show status of all users"
echo "  komp-control add-user USERNAME   # Add a new user"
echo "  komp-control restrict-app USER APP --limit 1h  # Limit app usage"
echo "  komp-control bedtime USER --start 21:00 --end 7:00  # Set bedtime"
echo "  komp-control report              # Show usage reports"
echo
echo "Configuration file: /etc/komp-timetracker/config.yaml"
echo "Database: /var/lib/komp-timetracker/usage.db"
echo "Logs: /var/log/komp-timetracker/"
