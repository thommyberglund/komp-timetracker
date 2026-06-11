# Flatpak Deployment Guide for Komp TimeTracker

This guide explains how to deploy Komp TimeTracker as a Flatpak application on Bazzite Linux.

## 📋 Prerequisites

### 1. Install Flatpak and Flatpak Builder

On Bazzite Linux (Fedora-based), run:

```bash
# Install Flatpak
sudo dnf install flatpak

# Install Flatpak Builder
sudo dnf install flatpak-builder

# Add the Flathub repository (for runtime dependencies)
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
```

### 2. Install Required Runtimes

```bash
# Install the base runtime
flatpak install flathub org.freedesktop.Platform//23.08
flatpak install flathub org.freedesktop.Sdk//23.08
```

## 🚀 Deployment Methods

### Method 1: Local Build and Install (Recommended for Development)

#### Step 1: Clone the Repository

```bash
git clone https://github.com/thommyberglund/komp-timetracker.git
cd komp-timetracker
```

#### Step 2: Build the Flatpak

```bash
# Make the build script executable
chmod +x flatpak-build.sh

# Run the build script
./flatpak-build.sh
```

This will:
- Create a local Flatpak repository
- Build the application
- Install it to your user's Flatpak installation

#### Step 3: Verify Installation

```bash
# Check if the app is installed
flatpak list | grep komp_timetracker

# Run the app
flatpak run com.komp_timetracker.KompTimeTracker --help
```

### Method 2: Manual Build with Flatpak Builder

#### Step 1: Create Build Directory

```bash
mkdir -p flatpak-build flatpak-repo
```

#### Step 2: Build the Flatpak

```bash
flatpak-builder \
    --user \
    --install \
    --force-clean \
    --build-dir=flatpak-build \
    flatpak-repo \
    com.komp_timetracker.KompTimeTracker.json
```

#### Step 3: Export to Repository (Optional)

```bash
# Create a local repository
flatpak build-export flatpak-repo flatpak-build

# Add the local repository
flatpak remote-add --no-gpg-verify komp-timetracker-repo flatpak-repo

# Install from the repository
flatpak install komp-timetracker-repo com.komp_timetracker.KompTimeTracker
```

### Method 3: System-wide Installation

For system-wide installation (requires root):

```bash
# Build with system-wide installation
flatpak-builder \
    --install \
    --force-clean \
    --prefix=/var/lib/flatpak/app \
    --build-dir=flatpak-build \
    flatpak-repo \
    com.komp_timetracker.KompTimeTracker.json
```

## 📦 Publishing to Flathub (Optional)

If you want to publish to Flathub for public distribution:

### Step 1: Create a Flathub Account

1. Go to https://flathub.org and create an account
2. Fork the Flathub repository on GitHub

### Step 2: Prepare Your Manifest

Ensure your manifest follows Flathub guidelines:
- Use proper app ID (reverse DNS notation)
- Include proper metadata
- Follow security best practices

### Step 3: Submit a Pull Request

1. Create a new branch in your Flathub fork
2. Add your manifest file to the appropriate category
3. Submit a pull request

## 🔧 Configuration for Flatpak

When running as a Flatpak, the application uses different paths:

- **Configuration**: `~/.config/komp-timetracker/config.yaml`
- **Database**: `~/.local/share/komp-timetracker/usage.db`
- **Logs**: `~/.cache/komp-timetracker/`

### First Run Setup

The first time you run the Flatpak, it will:
1. Create the configuration directory
2. Copy the default configuration file
3. Set up the database

```bash
# First run - will create default config
flatpak run com.komp_timetracker.KompTimeTracker status

# Edit the configuration
nano ~/.config/komp-timetracker/config.yaml
```

## 🎯 Usage with Flatpak

### Basic Commands

```bash
# Show help
flatpak run com.komp_timetracker.KompTimeTracker --help

# Show status of all users
flatpak run com.komp_timetracker.KompTimeTracker status

# Add a user
flatpak run com.komp_timetracker.KompTimeTracker add-user child1 --name "Child User" --age 12 --daily-limit 2h

# Set bedtime
flatpak run com.komp_timetracker.KompTimeTracker bedtime child1 --start 21:00 --end 7:00

# Restrict an app
flatpak run com.komp_timetracker.KompTimeTracker restrict-app child1 steam --limit 1h

# Generate reports
flatpak run com.komp_timetracker.KompTimeTracker report --days 7
```

### Create Desktop Shortcut

```bash
# Update desktop database
flatpak run --command=update-desktop-database com.komp_timetracker.KompTimeTracker

# Update icon cache
flatpak run --command=gtk-update-icon-cache com.komp_timetracker.KompTimeTracker -f -t
```

After this, you should see "Komp TimeTracker" in your application menu.

## 🔒 Permissions

The Flatpak manifest includes the following permissions:

- **Wayland/X11**: For GUI applications (if you add a GUI later)
- **Network**: For web filtering and updates
- **Host filesystem**: For monitoring system applications
- **IPC**: For inter-process communication
- **DBus**: For system integration
- **System DBus**: For systemd integration
- **Devices**: For GPU access (DRI)

### Adjusting Permissions

You can adjust permissions when running:

```bash
# Run with additional permissions
flatpak run --filesystem=host com.komp_timetracker.KompTimeTracker status

# Run with network access
flatpak run --share=network com.komp_timetracker.KompTimeTracker report

# Persistent permissions (override)
flatpak override --user --filesystem=host com.komp_timetracker.KompTimeTracker
flatpak override --user --share=network com.komp_timetracker.KompTimeTracker
```

## 🐛 Troubleshooting

### Common Issues

#### 1. "Command not found" after installation

```bash
# Check if the app is installed
flatpak list | grep komp_timetracker

# If not installed, reinstall
./flatpak-build.sh
```

#### 2. Permission denied errors

```bash
# Grant additional filesystem access
flatpak override --user --filesystem=host com.komp_timetracker.KompTimeTracker

# For system monitoring, you might need host access
flatpak override --user --filesystem=/ com.komp_timetracker.KompTimeTracker
```

#### 3. Python module not found

```bash
# Rebuild with proper dependencies
rm -rf flatpak-build flatpak-repo
./flatpak-build.sh
```

#### 4. Configuration file not found

```bash
# Check the config directory
ls -la ~/.config/komp-timetracker/

# If missing, run once to create it
flatpak run com.komp_timetracker.KompTimeTracker status
```

### Debug Mode

```bash
# Run with verbose output
flatpak run --verbose com.komp_timetracker.KompTimeTracker status

# Check logs
journalctl -u flatpak-* -f
```

## 📈 Performance Considerations

### Monitoring Performance

The Flatpak version has some limitations:
- Process monitoring might be less accurate due to sandboxing
- System-level restrictions (cgroups) may not work in Flatpak sandbox
- Consider using the system-wide installation for full functionality

### Recommended: Hybrid Approach

For best results on Bazzite:
1. **Install system-wide** for the service components (monitoring, enforcement)
2. **Use Flatpak** for the CLI interface

```bash
# Install system service (as root)
./scripts/install.sh

# Install Flatpak for CLI (as user)
./flatpak-build.sh

# Use Flatpak CLI to control the system service
flatpak run com.komp_timetracker.KompTimeTracker status
```

## 🔄 Updates

### Updating the Flatpak

```bash
# Pull the latest changes
git pull origin main

# Rebuild
./flatpak-build.sh

# Or uninstall and reinstall
flatpak uninstall com.komp_timetracker.KompTimeTracker
./flatpak-build.sh
```

### Automatic Updates

To enable automatic updates:

```bash
# Enable automatic updates for user installations
flatpak remote-modify --enable --no-gpg-verify komp-timetracker-repo

# For Flathub (if published)
flatpak remote-modify --enable flathub
```

## 🎉 Next Steps

1. **Test the Flatpak**: Run various commands to ensure everything works
2. **Customize Configuration**: Edit `~/.config/komp-timetracker/config.yaml`
3. **Add Users**: Set up users and restrictions
4. **Monitor Usage**: Check reports and status
5. **Consider System Installation**: For full functionality, consider the system-wide installation

## 📚 Additional Resources

- [Flatpak Documentation](https://docs.flatpak.org/)
- [Flathub Packaging Guide](https://github.com/flathub/flathub/wiki/Packaging-Tutorial)
- [Bazzite Linux Documentation](https://bazzite.gg/)

---

**Note**: The Flatpak version provides a portable, sandboxed way to run Komp TimeTracker. However, for full parental control functionality (especially system-level restrictions), a system-wide installation is recommended on Bazzite Linux.