# Komp TimeTracker - Parental Control for Bazzite Linux

A comprehensive parental control application designed specifically for Bazzite Linux, providing time management, content filtering, and usage monitoring for children and teens.

## Features

- **Time Limits**: Set daily/weekly usage limits per user or application
- **Application Restrictions**: Block or limit access to specific applications (Steam, browsers, etc.)
- **Content Filtering**: Web filtering and safe search enforcement
- **Activity Monitoring**: Track usage patterns and generate reports
- **Bedtime Mode**: Automatic restrictions during sleep hours
- **Bazzite Integration**: Native support for Flatpak, Steam, and Wayland

## Architecture

```
komp-timetracker/
├── src/
│   ├── core/           # Core functionality and data models
│   ├── monitor/        # Usage monitoring and tracking
│   ├── restrict/       # Restriction enforcement
│   ├── ui/             # User interface (CLI + optional GUI)
│   └── config/         # Configuration management
├── tests/              # Unit and integration tests
├── docs/               # Documentation
├── packaging/          # Packaging for Bazzite (RPM, Flatpak)
└── scripts/            # Installation and setup scripts
```

## Quick Start

### Installation on Bazzite

```bash
# Clone the repository
sudo dnf install -y git
git clone https://github.com/thommyberglund/komp-timetracker.git
cd komp-timetracker

# Install dependencies
sudo dnf install -y python3 python3-pip python3-systemd
pip3 install -r requirements.txt

# Install as a systemd service
sudo cp packaging/systemd/komp-timetracker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable komp-timetracker
sudo systemctl start komp-timetracker

# Install CLI tool
sudo cp src/ui/cli.py /usr/local/bin/komp-control
sudo chmod +x /usr/local/bin/komp-control
```

### Basic Usage

```bash
# View status
komp-control status

# Add a child user
komp-control add-user --name "Child1" --age 12 --daily-limit 2h

# Set app restrictions
komp-control restrict-app --user Child1 --app steam --limit 1h

# Enable bedtime mode
komp-control bedtime --user Child1 --start 21:00 --end 7:00

# View usage reports
komp-control report --user Child1 --days 7
```

## Configuration

Edit `/etc/komp-timetracker/config.yaml`:

```yaml
users:
  Child1:
    daily_limit: 2h
    weekly_limit: 10h
    bedtime:
      start: "21:00"
      end: "7:00"
    restricted_apps:
      - steam
      - firefox
    allowed_apps:
      - org.gnome.Calculator
      - org.gnome.Nautilus
    web_filter: true
    safe_search: true

monitoring:
  track_apps: true
  track_web: true
  retention_days: 30

enforcement:
  method: "cgroups"  # or "flatpak", "firewall"
  grace_period: 5m
```

## Bazzite-Specific Features

### Flatpak Integration
- Monitors and restricts Flatpak applications
- Uses Flatpak permissions to enforce restrictions
- Tracks usage per Flatpak app ID

### Steam Integration
- Monitors Steam gaming sessions
- Can limit playtime per game or globally
- Integrates with Steam's parental controls

### Wayland Support
- Works with Wayland display server
- Uses appropriate APIs for session monitoring

## Development

```bash
# Run tests
python3 -m pytest tests/

# Run the monitor manually
python3 src/monitor/usage_tracker.py

# Run the restriction enforcer
python3 src/restrict/enforcer.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- GitHub Issues: https://github.com/thommyberglund/komp-timetracker/issues
- Documentation: https://github.com/thommyberglund/komp-timetracker/wiki
