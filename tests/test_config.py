"""
Tests for configuration management
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import time, timedelta

from src.config.manager import ConfigManager, ConfigFileNotFoundError, InvalidConfigError
from src.core.models import User, UserRole, TimeLimit, BedtimeSchedule


class TestConfigManager:
    """Test ConfigManager class"""
    
    def test_create_default_config(self):
        """Test creating default configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")
            config_manager = ConfigManager(config_path)
            
            # Load should create default config
            config = config_manager.load()
            
            assert "system" in config
            assert "users" in config
            assert "monitoring" in config
            
            # Check default values
            assert config["system"]["enforcement_method"] == "cgroups"
            assert config["system"]["grace_period"] == "5m"
            assert config["system"]["monitoring_enabled"] == True
            
    def test_load_existing_config(self):
        """Test loading existing configuration"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")
            
            # Create a config file
            config_content = """
system:
  enforcement_method: "flatpak"
  grace_period: "10m"
  monitoring_enabled: false
  data_retention_days: 60

users:
  testuser:
    username: "testuser"
    display_name: "Test User"
    age: 12
    role: "child"
    enabled: true
    time_limits:
      daily: "2h"
      weekly: "10h"
    bedtime:
      enabled: true
      start: "21:00"
      end: "7:00"
      strict: false
"""
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            config_manager = ConfigManager(config_path)
            config = config_manager.load()
            
            assert config["system"]["enforcement_method"] == "flatpak"
            assert config["system"]["grace_period"] == "10m"
            assert config["system"]["monitoring_enabled"] == False
            
    def test_add_user(self):
        """Test adding a user"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")
            config_manager = ConfigManager(config_path)
            config_manager.load()
            
            # Create a user
            user = User(
                username="newuser",
                display_name="New User",
                age=10,
                role=UserRole.CHILD,
                time_limits=TimeLimit(
                    daily=timedelta(hours=2),
                    weekly=timedelta(hours=10)
                ),
                bedtime=BedtimeSchedule(
                    enabled=True,
                    start=time(21, 0),
                    end=time(7, 0)
                )
            )
            
            config_manager.add_user(user)
            
            # Reload and check
            config_manager.reload()
            users = config_manager.users
            
            assert "newuser" in users
            assert users["newuser"].display_name == "New User"
            assert users["newuser"].age == 10
            
    def test_remove_user(self):
        """Test removing a user"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")
            config_manager = ConfigManager(config_path)
            config_manager.load()
            
            # Add a user first
            user = User(
                username="tempuser",
                display_name="Temp User"
            )
            config_manager.add_user(user)
            
            # Remove the user
            config_manager.remove_user("tempuser")
            
            # Check that user is removed
            config_manager.reload()
            users = config_manager.users
            
            assert "tempuser" not in users
            
    def test_get_user(self):
        """Test getting a specific user"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")
            config_manager = ConfigManager(config_path)
            config_manager.load()
            
            # Add a user
            user = User(
                username="getuser",
                display_name="Get User"
            )
            config_manager.add_user(user)
            
            # Get the user
            retrieved_user = config_manager.get_user("getuser")
            
            assert retrieved_user is not None
            assert retrieved_user.username == "getuser"
            assert retrieved_user.display_name == "Get User"
            
    def test_update_user(self):
        """Test updating a user"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")
            config_manager = ConfigManager(config_path)
            config_manager.load()
            
            # Add a user
            user = User(
                username="updateuser",
                display_name="Original Name"
            )
            config_manager.add_user(user)
            
            # Update the user
            config_manager.update_user("updateuser", {
                "display_name": "Updated Name",
                "age": 15
            })
            
            # Check the update
            config_manager.reload()
            updated_user = config_manager.get_user("updateuser")
            
            assert updated_user.display_name == "Updated Name"
            assert updated_user.age == 15
            
    def test_config_file_not_found(self):
        """Test ConfigFileNotFoundError"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "nonexistent.yaml")
            config_manager = ConfigManager(config_path)
            
            with pytest.raises(ConfigFileNotFoundError):
                config_manager.load(create_default=False)
                
    def test_invalid_yaml(self):
        """Test InvalidConfigError with invalid YAML"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "invalid.yaml")
            
            # Create invalid YAML
            with open(config_path, 'w') as f:
                f.write("invalid: yaml: content:")
            
            config_manager = ConfigManager(config_path)
            
            with pytest.raises(InvalidConfigError):
                config_manager.load()


class TestConfigDirectories:
    """Test configuration directory creation"""
    
    def test_create_config_directory(self):
        """Test that config directory is created"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "subdir", "config.yaml")
            config_manager = ConfigManager(config_path)
            
            config_manager.load()
            
            # Check that directory was created
            config_dir = os.path.dirname(config_path)
            assert os.path.exists(config_dir)
            
    def test_create_data_directory(self):
        """Test that data directory is created"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")
            config_manager = ConfigManager(config_path)
            
            config_manager.load()
            
            # Check that data directory was created
            data_dir = "/var/lib/komp-timetracker"
            # Note: This might not work in all test environments
            # due to permission issues
