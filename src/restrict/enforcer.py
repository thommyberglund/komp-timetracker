"""
Main restriction enforcer for Komp TimeTracker
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

from ..core.models import User, EnforcementMethod
from ..config.manager import ConfigManager
from ..monitor.tracker import UsageTracker
from .methods import (
    RestrictionMethod, 
    get_enforcer,
    CgroupsEnforcer,
    FlatpakEnforcer,
    FirewallEnforcer,
    XdgOpenEnforcer
)

logger = logging.getLogger(__name__)


class RestrictionEnforcer:
    """Main class for enforcing parental control restrictions"""
    
    def __init__(self, config_manager: ConfigManager, tracker: UsageTracker):
        self.config_manager = config_manager
        self.tracker = tracker
        self._enforcers: Dict[str, RestrictionMethod] = {}
        self._last_check: Dict[str, datetime] = {}
        
    def _get_enforcer(self, method: EnforcementMethod) -> RestrictionMethod:
        """Get the appropriate enforcer for the given method"""
        method_name = method.value
        if method_name not in self._enforcers:
            self._enforcers[method_name] = get_enforcer(method, self.config_manager, self.tracker)
        return self._enforcers[method_name]
    
    def get_system_enforcer(self) -> RestrictionMethod:
        """Get the enforcer based on system configuration"""
        system_config = self.config_manager.system_config
        return self._get_enforcer(system_config.enforcement_method)
    
    def check_and_enforce(self, user: User) -> bool:
        """Check if restrictions should be enforced for a user and enforce them"""
        if not user.enabled:
            logger.debug(f"User {user.username} is not enabled for restrictions")
            return False
        
        # Check if we should enforce restrictions
        if self._should_enforce(user):
            return self.enforce(user)
        else:
            return self.lift(user)
    
    def _should_enforce(self, user: User) -> bool:
        """Determine if restrictions should be enforced for a user"""
        now = datetime.now()
        
        # Check if it's bedtime
        if user.bedtime.is_active(now):
            logger.debug(f"Bedtime active for user {user.username}")
            return True
        
        # Check daily time limit
        if user.time_limits.daily:
            total_usage = self.tracker.get_total_usage(user.username, days=1)
            if total_usage >= user.time_limits.daily:
                logger.debug(f"Daily limit exceeded for user {user.username}: {total_usage} >= {user.time_limits.daily}")
                return True
        
        # Check weekly time limit
        if user.time_limits.weekly:
            total_usage = self.tracker.get_total_usage(user.username, days=7)
            if total_usage >= user.time_limits.weekly:
                logger.debug(f"Weekly limit exceeded for user {user.username}: {total_usage} >= {user.time_limits.weekly}")
                return True
        
        # Check if any app-specific limits are exceeded
        for app_restriction in user.app_restrictions:
            if app_restriction.restriction_type.value == "limit" and app_restriction.time_limit:
                app_usage = self.tracker.get_app_usage(user.username, app_restriction.app_id)
                if app_usage >= app_restriction.time_limit:
                    logger.debug(f"App limit exceeded for user {user.username}, app {app_restriction.app_id}: {app_usage} >= {app_restriction.time_limit}")
                    return True
        
        return False
    
    def enforce(self, user: User) -> bool:
        """Enforce restrictions for a user"""
        enforcer = self.get_system_enforcer()
        return enforcer.enforce_restrictions(user)
    
    def lift(self, user: User) -> bool:
        """Lift restrictions for a user"""
        enforcer = self.get_system_enforcer()
        return enforcer.lift_restrictions(user)
    
    def is_restricted(self, user: User, app_id: str) -> bool:
        """Check if an app is restricted for a user"""
        enforcer = self.get_system_enforcer()
        return enforcer.is_restricted(user, app_id)
    
    def check_all_users(self) -> Dict[str, bool]:
        """Check and enforce restrictions for all users"""
        users = self.config_manager.users
        results = {}
        
        for username, user in users.items():
            try:
                result = self.check_and_enforce(user)
                results[username] = result
                logger.info(f"Restriction check for {username}: {'enforced' if result else 'lifted'}")
            except Exception as e:
                logger.error(f"Error checking restrictions for {username}: {e}")
                results[username] = False
        
        return results
    
    def enforce_continuously(self, interval: float = 60.0):
        """Continuously check and enforce restrictions"""
        logger.info(f"Starting continuous restriction enforcement with {interval}s interval")
        
        try:
            while True:
                self.check_all_users()
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Continuous enforcement stopped by user")
        except Exception as e:
            logger.error(f"Error in continuous enforcement: {e}")
    
    def get_restriction_status(self, user: User) -> Dict[str, Any]:
        """Get the current restriction status for a user"""
        now = datetime.now()
        status = {
            "user": user.username,
            "enabled": user.enabled,
            "restricted": False,
            "reasons": [],
            "time_remaining": None,
            "app_restrictions": []
        }
        
        if not user.enabled:
            status["restricted"] = False
            return status
        
        # Check bedtime
        if user.bedtime.is_active(now):
            status["restricted"] = True
            status["reasons"].append("bedtime_active")
        
        # Check daily limit
        if user.time_limits.daily:
            total_usage = self.tracker.get_total_usage(user.username, days=1)
            remaining = user.time_limits.daily - total_usage
            
            if remaining <= timedelta(0):
                status["restricted"] = True
                status["reasons"].append("daily_limit_exceeded")
                status["time_remaining"] = timedelta(0)
            else:
                status["time_remaining"] = remaining
        
        # Check app-specific restrictions
        for app_restriction in user.app_restrictions:
            app_status = {
                "app_id": app_restriction.app_id,
                "restriction_type": app_restriction.restriction_type.value,
                "allowed": app_restriction.allowed,
                "time_remaining": None
            }
            
            if app_restriction.restriction_type.value == "limit" and app_restriction.time_limit:
                app_usage = self.tracker.get_app_usage(user.username, app_restriction.app_id)
                remaining = app_restriction.time_limit - app_usage
                app_status["time_remaining"] = remaining
                
                if remaining <= timedelta(0):
                    app_status["restricted"] = True
                    status["restricted"] = True
                    status["reasons"].append(f"app_limit_exceeded:{app_restriction.app_id}")
                else:
                    app_status["restricted"] = False
            else:
                app_status["restricted"] = not app_restriction.allowed
                if app_status["restricted"]:
                    status["restricted"] = True
                    status["reasons"].append(f"app_blocked:{app_restriction.app_id}")
            
            status["app_restrictions"].append(app_status)
        
        return status
