"""
Configuration manager for Komp TimeTracker
Handles loading, saving, and managing configuration files
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import time, timedelta

from ..core.models import (
    User, 
    AppRestriction, 
    TimeLimit, 
    BedtimeSchedule, 
    WebFilterConfig,
    SystemConfig,
    EnforcementMethod,
    RestrictionType,
    UserRole,
    parse_time_duration
)

logger = logging.getLogger(__name__)


class ConfigFileNotFoundError(Exception):
    """Raised when config file is not found"""
    pass


class InvalidConfigError(Exception):
    """Raised when config file is invalid"""
    pass


class ConfigManager:
    """Manages configuration loading and saving"""
    
    def __init__(self, config_path: str = "/etc/komp-timetracker/config.yaml"):
        self.config_path = Path(config_path)
        self._config: Optional[Dict[str, Any]] = None
        self._users: Optional[Dict[str, User]] = None
        self._system_config: Optional[SystemConfig] = None
        
    def _ensure_config_dir(self):
        """Ensure the configuration directory exists"""
        config_dir = self.config_path.parent
        if not config_dir.exists():
            try:
                config_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created config directory: {config_dir}")
            except PermissionError:
                logger.error(f"Permission denied: cannot create config directory {config_dir}")
                raise
    
    def _ensure_data_dir(self):
        """Ensure the data directory exists"""
        data_dir = Path("/var/lib/komp-timetracker")
        if not data_dir.exists():
            try:
                data_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created data directory: {data_dir}")
            except PermissionError:
                logger.error(f"Permission denied: cannot create data directory {data_dir}")
                raise
    
    def _ensure_log_dir(self):
        """Ensure the log directory exists"""
        log_dir = Path("/var/log/komp-timetracker")
        if not log_dir.exists():
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created log directory: {log_dir}")
            except PermissionError:
                logger.error(f"Permission denied: cannot create log directory {log_dir}")
                raise
    
    def load(self, create_default: bool = True) -> Dict[str, Any]:
        """Load configuration from file"""
        self._ensure_config_dir()
        self._ensure_data_dir()
        self._ensure_log_dir()
        
        if not self.config_path.exists():
            if create_default:
                logger.info(f"Config file not found, creating default: {self.config_path}")
                self._create_default_config()
            else:
                raise ConfigFileNotFoundError(f"Config file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                self._config = yaml.safe_load(f) or {}
            
            logger.info(f"Loaded configuration from {self.config_path}")
            return self._config
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in config file: {e}")
            raise InvalidConfigError(f"Invalid YAML in config file: {e}")
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            raise InvalidConfigError(f"Error loading config file: {e}")
    
    def save(self, config: Optional[Dict[str, Any]] = None):
        """Save configuration to file"""
        if config is None:
            config = self._config
        
        if config is None:
            raise ValueError("No configuration to save")
        
        self._ensure_config_dir()
        
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Saved configuration to {self.config_path}")
            
        except PermissionError:
            logger.error(f"Permission denied: cannot save config to {self.config_path}")
            raise
        except Exception as e:
            logger.error(f"Error saving config file: {e}")
            raise
    
    def _create_default_config(self):
        """Create a default configuration file"""
        default_config = {
            "system": {
                "enforcement_method": "cgroups",
                "grace_period": "5m",
                "monitoring_enabled": True,
                "data_retention_days": 30
            },
            "users": {},
            "monitoring": {
                "track_apps": True,
                "track_web": True,
                "retention_days": 30
            }
        }
        
        self._config = default_config
        self.save(default_config)
    
    @property
    def users(self) -> Dict[str, User]:
        """Get all users from configuration"""
        if self._users is None:
            self._load_users()
        return self._users or {}
    
    @property
    def system_config(self) -> SystemConfig:
        """Get system configuration"""
        if self._system_config is None:
            self._load_system_config()
        return self._system_config
    
    def _load_users(self):
        """Load users from configuration"""
        if self._config is None:
            self.load()
        
        users_config = self._config.get("users", {})
        self._users = {}
        
        for username, user_data in users_config.items():
            try:
                user = self._parse_user(username, user_data)
                self._users[username] = user
            except Exception as e:
                logger.error(f"Error parsing user {username}: {e}")
                continue
    
    def _parse_user(self, username: str, user_data: Dict[str, Any]) -> User:
        """Parse user data into User model"""
        # Parse time limits
        time_limits_data = user_data.get("time_limits", {})
        time_limits = TimeLimit(
            daily=parse_time_duration(time_limits_data.get("daily", "2h")) if time_limits_data.get("daily") else None,
            weekly=parse_time_duration(time_limits_data.get("weekly", "10h")) if time_limits_data.get("weekly") else None,
            monthly=parse_time_duration(time_limits_data.get("monthly")) if time_limits_data.get("monthly") else None
        )
        
        # Parse bedtime
        bedtime_data = user_data.get("bedtime", {})
        bedtime = BedtimeSchedule(
            enabled=bedtime_data.get("enabled", True),
            start=self._parse_time(bedtime_data.get("start", "21:00")),
            end=self._parse_time(bedtime_data.get("end", "7:00")),
            strict=bedtime_data.get("strict", False)
        )
        
        # Parse app restrictions
        app_restrictions = []
        for app_data in user_data.get("app_restrictions", []):
            restriction = AppRestriction(
                app_id=app_data.get("app_id", ""),
                restriction_type=RestrictionType(app_data.get("restriction_type", "limit")),
                time_limit=parse_time_duration(app_data.get("time_limit", "1h")) if app_data.get("time_limit") else None,
                allowed=app_data.get("allowed", True)
            )
            app_restrictions.append(restriction)
        
        # Parse web filter
        web_filter_data = user_data.get("web_filter", {})
        web_filter = WebFilterConfig(
            enabled=web_filter_data.get("enabled", True),
            safe_search=web_filter_data.get("safe_search", True),
            blocked_categories=web_filter_data.get("blocked_categories", []),
            allowed_domains=web_filter_data.get("allowed_domains", []),
            blocked_domains=web_filter_data.get("blocked_domains", [])
        )
        
        # Create user
        user = User(
            username=username,
            display_name=user_data.get("display_name"),
            age=user_data.get("age"),
            role=UserRole(user_data.get("role", "child")),
            time_limits=time_limits,
            bedtime=bedtime,
            app_restrictions=app_restrictions,
            web_filter=web_filter,
            allowed_apps=user_data.get("allowed_apps", []),
            restricted_apps=user_data.get("restricted_apps", []),
            enabled=user_data.get("enabled", True)
        )
        
        return user
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string into time object"""
        if isinstance(time_str, time):
            return time_str
        
        try:
            if ":" in time_str:
                parts = time_str.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                return time(hour, minute)
            else:
                hour = int(time_str)
                return time(hour, 0)
        except (ValueError, IndexError):
            return time(21, 0)  # Default bedtime start
    
    def _load_system_config(self):
        """Load system configuration"""
        if self._config is None:
            self.load()
        
        system_data = self._config.get("system", {})
        
        self._system_config = SystemConfig(
            enforcement_method=EnforcementMethod(system_data.get("enforcement_method", "cgroups")),
            grace_period=parse_time_duration(system_data.get("grace_period", "5m")),
            monitoring_enabled=system_data.get("monitoring_enabled", True),
            data_retention_days=system_data.get("data_retention_days", 30)
        )
    
    def add_user(self, user: User) -> None:
        """Add a new user to configuration"""
        if self._config is None:
            self.load()
        
        if "users" not in self._config:
            self._config["users"] = {}
        
        self._config["users"][user.username] = user.to_dict()
        self._users = None  # Invalidate cache
        self.save()
        logger.info(f"Added user: {user.username}")
    
    def update_user(self, username: str, user_data: Dict[str, Any]) -> None:
        """Update an existing user"""
        if self._config is None:
            self.load()
        
        if "users" not in self._config:
            self._config["users"] = {}
        
        if username not in self._config["users"]:
            raise ValueError(f"User {username} not found")
        
        self._config["users"][username].update(user_data)
        self._users = None  # Invalidate cache
        self.save()
        logger.info(f"Updated user: {username}")
    
    def remove_user(self, username: str) -> None:
        """Remove a user from configuration"""
        if self._config is None:
            self.load()
        
        if "users" not in self._config or username not in self._config["users"]:
            raise ValueError(f"User {username} not found")
        
        del self._config["users"][username]
        self._users = None  # Invalidate cache
        self.save()
        logger.info(f"Removed user: {username}")
    
    def get_user(self, username: str) -> Optional[User]:
        """Get a specific user by username"""
        users = self.users
        return users.get(username)
    
    def reload(self):
        """Reload configuration from file"""
        self._config = None
        self._users = None
        self._system_config = None
        self.load()
    
    def get_config(self) -> Dict[str, Any]:
        """Get the raw configuration dictionary"""
        if self._config is None:
            self.load()
        return self._config or {}
    
    def set_config(self, config: Dict[str, Any]):
        """Set the configuration dictionary"""
        self._config = config
        self._users = None
        self._system_config = None
        self.save()
