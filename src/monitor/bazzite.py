"""
Bazzite-specific monitoring functionality
"""

import os
import subprocess
import logging
from typing import Optional, List, Dict, Any
import xml.etree.ElementTree as ET

from .tracker import UsageTracker
from ..config.manager import ConfigManager

logger = logging.getLogger(__name__)


class BazziteMonitor:
    """Monitors Bazzite-specific applications and features"""
    
    def __init__(self, tracker: UsageTracker, config_manager: ConfigManager):
        self.tracker = tracker
        self.config_manager = config_manager
        
    def get_flatpak_apps(self) -> List[Dict[str, Any]]:
        """Get list of installed Flatpak applications"""
        apps = []
        
        try:
            # Use flatpak command to list installed apps
            result = subprocess.run(
                ["flatpak", "list", "--app", "--columns=application,instance,runtime"],
                capture_output=True, text=True, check=True
            )
            
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            
            for line in lines:
                if not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    app_id = parts[0]
                    instance_id = parts[1] if len(parts) > 1 else app_id
                    
                    apps.append({
                        "app_id": app_id,
                        "instance_id": instance_id,
                        "is_flatpak": True,
                        "name": self._get_flatpak_app_name(app_id)
                    })
                    
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"Error getting Flatpak apps: {e}")
        
        return apps
    
    def _get_flatpak_app_name(self, app_id: str) -> str:
        """Get the display name of a Flatpak app"""
        try:
            result = subprocess.run(
                ["flatpak", "info", app_id],
                capture_output=True, text=True, check=True
            )
            
            # Parse the output to find the name
            for line in result.stdout.split('\n'):
                if line.startswith("Name:"):
                    return line.split(":", 1)[1].strip()
                    
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return app_id
    
    def get_steam_games(self) -> List[Dict[str, Any]]:
        """Get list of installed Steam games"""
        games = []
        
        # Common Steam library paths
        steam_paths = [
            os.path.expanduser("~/.local/share/Steam/steamapps"),
            os.path.expanduser("~/.steam/steam/steamapps"),
            "/var/lib/flatpak/app/com.valvesoftware.Steam/.local/share/Steam/steamapps"
        ]
        
        for steam_path in steam_paths:
            if os.path.exists(steam_path):
                games.extend(self._scan_steam_library(steam_path))
        
        return games
    
    def _scan_steam_library(self, library_path: str) -> List[Dict[str, Any]]:
        """Scan a Steam library directory for games"""
        games = []
        
        # Look for appmanifest files
        manifest_path = os.path.join(library_path, "appmanifest_*.acf")
        
        try:
            import glob
            for manifest_file in glob.glob(manifest_path):
                try:
                    game_info = self._parse_steam_manifest(manifest_file)
                    if game_info:
                        games.append(game_info)
                except Exception as e:
                    logger.debug(f"Error parsing Steam manifest {manifest_file}: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"Error scanning Steam library {library_path}: {e}")
        
        return games
    
    def _parse_steam_manifest(self, manifest_path: str) -> Optional[Dict[str, Any]]:
        """Parse a Steam app manifest file"""
        try:
            with open(manifest_path, 'r') as f:
                content = f.read()
            
            # Parse the ACF format (simplified)
            app_id = None
            name = None
            
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('"appid"'):
                    app_id = line.split('"')[3]
                elif line.startswith('"name"'):
                    name = line.split('"')[3]
            
            if app_id and name:
                return {
                    "app_id": f"steam_{app_id}",
                    "name": name,
                    "steam_id": app_id,
                    "is_steam": True,
                    "is_flatpak": False
                }
                
        except Exception as e:
            logger.debug(f"Error parsing manifest: {e}")
        
        return None
    
    def is_flatpak_running(self, app_id: str) -> bool:
        """Check if a Flatpak app is currently running"""
        try:
            result = subprocess.run(
                ["flatpak", "ps"],
                capture_output=True, text=True, check=True
            )
            
            for line in result.stdout.split('\n'):
                if app_id in line:
                    return True
                    
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return False
    
    def get_flatpak_permissions(self, app_id: str) -> Dict[str, Any]:
        """Get permissions for a Flatpak app"""
        permissions = {}
        
        try:
            result = subprocess.run(
                ["flatpak", "info", "--show-permissions", app_id],
                capture_output=True, text=True, check=True
            )
            
            # Parse permissions from output
            current_section = None
            for line in result.stdout.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1]
                    permissions[current_section] = []
                elif current_section and line:
                    permissions[current_section].append(line)
                    
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.debug(f"Error getting Flatpak permissions for {app_id}: {e}")
        
        return permissions
    
    def monitor_flatpak_usage(self):
        """Monitor Flatpak application usage"""
        flatpak_apps = self.get_flatpak_apps()
        users = self.config_manager.users
        
        for app in flatpak_apps:
            app_id = app["app_id"]
            
            # Check if this app is being used by any monitored user
            for username, user in users.items():
                if not user.enabled:
                    continue
                
                # Check if this app is restricted for the user
                if app_id in user.restricted_apps:
                    if self.is_flatpak_running(app_id):
                        logger.info(f"Restricted Flatpak app running: {app_id} by user {username}")
                        # In a real implementation, we'd enforce the restriction here
                        
    def get_system_info(self) -> Dict[str, Any]:
        """Get Bazzite system information"""
        info = {
            "is_bazzite": self._check_if_bazzite(),
            "flatpak_apps": len(self.get_flatpak_apps()),
            "steam_games": len(self.get_steam_games())
        }
        
        return info
    
    def _check_if_bazzite(self) -> bool:
        """Check if we're running on Bazzite Linux"""
        try:
            # Check for Bazzite-specific files or commands
            result = subprocess.run(
                ["cat", "/etc/os-release"],
                capture_output=True, text=True, check=True
            )
            
            return "Bazzite" in result.stdout or "bazzite" in result.stdout
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Check for common Bazzite directories
        bazzite_paths = [
            "/var/lib/flatpak/app/com.valvesoftware.Steam",
            "/usr/share/bazzite"
        ]
        
        for path in bazzite_paths:
            if os.path.exists(path):
                return True
        
        return False
    
    def get_active_flatpak_sessions(self) -> List[Dict[str, Any]]:
        """Get currently running Flatpak applications"""
        sessions = []
        
        try:
            result = subprocess.run(
                ["flatpak", "ps", "--columns=instance,application,pid"],
                capture_output=True, text=True, check=True
            )
            
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            
            for line in lines:
                if not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) >= 3:
                    sessions.append({
                        "instance": parts[0],
                        "app_id": parts[1],
                        "pid": int(parts[2])
                    })
                    
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.debug(f"Error getting Flatpak sessions: {e}")
        
        return sessions
    
    def get_wayland_sessions(self) -> List[Dict[str, Any]]:
        """Get active Wayland sessions"""
        sessions = []
        
        try:
            # Check for active Wayland sessions using loginctl
            result = subprocess.run(
                ["loginctl", "list-sessions"],
                capture_output=True, text=True, check=True
            )
            
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) >= 3:
                    session_id = parts[0]
                    user = parts[1]
                    seat = parts[2]
                    
                    # Check if this is a Wayland session
                    try:
                        result = subprocess.run(
                            ["loginctl", "show-session", session_id, "-p", "Type"],
                            capture_output=True, text=True, check=True
                        )
                        
                        if "wayland" in result.stdout.lower():
                            sessions.append({
                                "session_id": session_id,
                                "user": user,
                                "seat": seat,
                                "type": "wayland"
                            })
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue
                        
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.debug(f"Error getting Wayland sessions: {e}")
        
        return sessions
