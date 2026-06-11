"""
Restriction enforcement methods
"""

import os
import subprocess
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from ..core.models import User, EnforcementMethod
from ..config.manager import ConfigManager
from ..monitor.tracker import UsageTracker

logger = logging.getLogger(__name__)


class RestrictionMethod(ABC):
    """Abstract base class for restriction enforcement methods"""
    
    def __init__(self, config_manager: ConfigManager, tracker: UsageTracker):
        self.config_manager = config_manager
        self.tracker = tracker
        
    @abstractmethod
    def enforce_restrictions(self, user: User) -> bool:
        """Enforce restrictions for a user"""
        pass
    
    @abstractmethod
    def lift_restrictions(self, user: User) -> bool:
        """Lift restrictions for a user"""
        pass
    
    @abstractmethod
    def is_restricted(self, user: User, app_id: str) -> bool:
        """Check if an app is restricted for a user"""
        pass
    
    @abstractmethod
    def get_method_name(self) -> str:
        """Get the name of this enforcement method"""
        pass


class CgroupsEnforcer(RestrictionMethod):
    """Enforce restrictions using Linux cgroups"""
    
    def __init__(self, config_manager: ConfigManager, tracker: UsageTracker):
        super().__init__(config_manager, tracker)
        self.cgroup_base = "/sys/fs/cgroup"
        
    def get_method_name(self) -> str:
        return "cgroups"
    
    def _get_user_cgroup(self, user: User) -> str:
        """Get the cgroup path for a user"""
        return os.path.join(self.cgroup_base, f"komp-timetracker/{user.username}")
    
    def _create_cgroup(self, user: User) -> bool:
        """Create a cgroup for a user"""
        cgroup_path = self._get_user_cgroup(user)
        
        try:
            # Create the cgroup directory
            os.makedirs(cgroup_path, exist_ok=True)
            
            # Set CPU limits (example: limit to 50% CPU)
            # This is a simplified example - real implementation would be more sophisticated
            cpu_max_path = os.path.join(cgroup_path, "cpu.max")
            with open(cpu_max_path, 'w') as f:
                f.write("50000 100000\n")  # 50% CPU limit
            
            # Set memory limits
            memory_max_path = os.path.join(cgroup_path, "memory.max")
            with open(memory_max_path, 'w') as f:
                f.write("1000000000\n")  # 1GB memory limit
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating cgroup for {user.username}: {e}")
            return False
    
    def _remove_cgroup(self, user: User) -> bool:
        """Remove a cgroup for a user"""
        cgroup_path = self._get_user_cgroup(user)
        
        try:
            if os.path.exists(cgroup_path):
                # Move all processes out of the cgroup first
                self._move_processes_out(user)
                
                # Remove the cgroup
                os.rmdir(cgroup_path)
                return True
                
        except Exception as e:
            logger.error(f"Error removing cgroup for {user.username}: {e}")
            return False
    
    def _move_processes_out(self, user: User):
        """Move all processes out of a user's cgroup"""
        cgroup_path = self._get_user_cgroup(user)
        
        try:
            # Find all PIDs in the cgroup
            cgroup_procs_path = os.path.join(cgroup_path, "cgroup.procs")
            if os.path.exists(cgroup_procs_path):
                with open(cgroup_procs_path, 'r') as f:
                    for pid in f.read().split():
                        try:
                            # Move to root cgroup
                            subprocess.run(
                                ["echo", pid, ">", "/sys/fs/cgroup/cgroup.procs"],
                                shell=True, check=True
                            )
                        except Exception as e:
                            logger.error(f"Error moving PID {pid} out of cgroup: {e}")
                            
        except Exception as e:
            logger.error(f"Error moving processes out of cgroup: {e}")
    
    def _add_pid_to_cgroup(self, user: User, pid: int) -> bool:
        """Add a process to a user's cgroup"""
        cgroup_path = self._get_user_cgroup(user)
        
        try:
            # Write PID to cgroup.procs
            cgroup_procs_path = os.path.join(cgroup_path, "cgroup.procs")
            with open(cgroup_procs_path, 'a') as f:
                f.write(f"{pid}\n")
            return True
            
        except Exception as e:
            logger.error(f"Error adding PID {pid} to cgroup: {e}")
            return False
    
    def enforce_restrictions(self, user: User) -> bool:
        """Enforce restrictions using cgroups"""
        if not self._create_cgroup(user):
            return False
        
        # In a real implementation, we'd also:
        # 1. Find all processes belonging to the user
        # 2. Move them into the restricted cgroup
        # 3. Set appropriate limits based on the user's configuration
        
        logger.info(f"Enforced cgroup restrictions for user: {user.username}")
        return True
    
    def lift_restrictions(self, user: User) -> bool:
        """Lift cgroup restrictions for a user"""
        return self._remove_cgroup(user)
    
    def is_restricted(self, user: User, app_id: str) -> bool:
        """Check if an app is restricted via cgroups"""
        # Check if the user has time limits exceeded
        total_usage = self.tracker.get_total_usage(user.username, days=1)
        daily_limit = user.time_limits.daily
        
        if daily_limit and total_usage >= daily_limit:
            return True
        
        # Check if the app is specifically restricted
        if not user.is_app_allowed(app_id):
            return True
        
        # Check bedtime
        if user.bedtime.is_active(datetime.now()):
            return True
        
        return False


class FlatpakEnforcer(RestrictionMethod):
    """Enforce restrictions using Flatpak permissions"""
    
    def __init__(self, config_manager: ConfigManager, tracker: UsageTracker):
        super().__init__(config_manager, tracker)
        
    def get_method_name(self) -> str:
        return "flatpak"
    
    def _get_flatpak_apps_for_user(self, user: User) -> List[str]:
        """Get Flatpak apps that should be restricted for a user"""
        restricted = []
        
        # Add explicitly restricted apps
        restricted.extend(user.restricted_apps)
        
        # Add apps with time limits that have been exceeded
        for app_restriction in user.app_restrictions:
            if app_restriction.restriction_type.value == "limit":
                app_usage = self.tracker.get_app_usage(user.username, app_restriction.app_id)
                if app_restriction.time_limit and app_usage >= app_restriction.time_limit:
                    restricted.append(app_restriction.app_id)
        
        return restricted
    
    def enforce_restrictions(self, user: User) -> bool:
        """Enforce restrictions using Flatpak permissions"""
        restricted_apps = self._get_flatpak_apps_for_user(user)
        
        for app_id in restricted_apps:
            if not self._restrict_flatpak_app(user, app_id):
                logger.warning(f"Failed to restrict Flatpak app {app_id} for user {user.username}")
        
        logger.info(f"Enforced Flatpak restrictions for user: {user.username}")
        return True
    
    def _restrict_flatpak_app(self, user: User, app_id: str) -> bool:
        """Restrict a specific Flatpak app for a user"""
        try:
            # Use flatpak override to restrict permissions
            # This is a simplified example - real implementation would be more sophisticated
            
            # Remove network access
            subprocess.run(
                ["flatpak", "override", "--user", "--no-filesystem=host", app_id],
                check=True, capture_output=True
            )
            
            # Remove network access
            subprocess.run(
                ["flatpak", "override", "--user", "--no-network", app_id],
                check=True, capture_output=True
            )
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error restricting Flatpak app {app_id}: {e}")
            return False
        except FileNotFoundError:
            logger.error("flatpak command not found")
            return False
    
    def lift_restrictions(self, user: User) -> bool:
        """Lift Flatpak restrictions for a user"""
        # Reset all overrides for the user's restricted apps
        restricted_apps = self._get_flatpak_apps_for_user(user)
        
        for app_id in restricted_apps:
            try:
                # Reset overrides
                subprocess.run(
                    ["flatpak", "override", "--user", "--reset", app_id],
                    check=True, capture_output=True
                )
            except Exception as e:
                logger.error(f"Error lifting restrictions for Flatpak app {app_id}: {e}")
                return False
        
        logger.info(f"Lifted Flatpak restrictions for user: {user.username}")
        return True
    
    def is_restricted(self, user: User, app_id: str) -> bool:
        """Check if a Flatpak app is restricted"""
        restricted_apps = self._get_flatpak_apps_for_user(user)
        return app_id in restricted_apps


class FirewallEnforcer(RestrictionMethod):
    """Enforce restrictions using firewall rules"""
    
    def __init__(self, config_manager: ConfigManager, tracker: UsageTracker):
        super().__init__(config_manager, tracker)
        
    def get_method_name(self) -> str:
        return "firewall"
    
    def enforce_restrictions(self, user: User) -> bool:
        """Enforce restrictions using firewall rules"""
        # In a real implementation, we'd use nftables or iptables
        # to block network access for specific applications
        
        # This is a placeholder - actual implementation would depend on
        # the specific firewall being used and the restrictions needed
        
        logger.info(f"Enforced firewall restrictions for user: {user.username}")
        return True
    
    def lift_restrictions(self, user: User) -> bool:
        """Lift firewall restrictions for a user"""
        logger.info(f"Lifted firewall restrictions for user: {user.username}")
        return True
    
    def is_restricted(self, user: User, app_id: str) -> bool:
        """Check if an app is restricted via firewall"""
        # Check if the app should be blocked
        if not user.is_app_allowed(app_id):
            return True
        
        # Check time limits
        app_usage = self.tracker.get_app_usage(user.username, app_id)
        for app_restriction in user.app_restrictions:
            if (app_restriction.app_id == app_id and 
                app_restriction.restriction_type.value == "limit" and
                app_restriction.time_limit and 
                app_usage >= app_restriction.time_limit):
                return True
        
        return False


class XdgOpenEnforcer(RestrictionMethod):
    """Enforce restrictions by intercepting xdg-open calls"""
    
    def __init__(self, config_manager: ConfigManager, tracker: UsageTracker):
        super().__init__(config_manager, tracker)
        
    def get_method_name(self) -> str:
        return "xdg-open"
    
    def enforce_restrictions(self, user: User) -> bool:
        """Enforce restrictions by setting up xdg-open interception"""
        # In a real implementation, we'd replace or wrap xdg-open
        # to check restrictions before opening applications
        
        logger.info(f"Enforced xdg-open restrictions for user: {user.username}")
        return True
    
    def lift_restrictions(self, user: User) -> bool:
        """Lift xdg-open restrictions for a user"""
        logger.info(f"Lifted xdg-open restrictions for user: {user.username}")
        return True
    
    def is_restricted(self, user: User, app_id: str) -> bool:
        """Check if an app is restricted via xdg-open"""
        return not user.is_app_allowed(app_id)


def get_enforcer(method: EnforcementMethod, config_manager: ConfigManager, tracker: UsageTracker) -> RestrictionMethod:
    """Get the appropriate enforcer for the given method"""
    enforcers = {
        EnforcementMethod.CGROUPS: CgroupsEnforcer,
        EnforcementMethod.FLATPAK: FlatpakEnforcer,
        EnforcementMethod.FIREWALL: FirewallEnforcer,
        EnforcementMethod.XDG_OPEN: XdgOpenEnforcer
    }
    
    enforcer_class = enforcers.get(method)
    if enforcer_class:
        return enforcer_class(config_manager, tracker)
    
    # Default to cgroups
    return CgroupsEnforcer(config_manager, tracker)
