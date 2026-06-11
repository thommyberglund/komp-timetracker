"""
Data models for Komp TimeTracker
"""

from datetime import datetime, time, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
import re


class RestrictionType(str, Enum):
    """Types of application restrictions"""
    BLOCK = "block"
    LIMIT = "limit"
    ALLOW = "allow"


class EnforcementMethod(str, Enum):
    """Methods for enforcing restrictions"""
    CGROUPS = "cgroups"
    FLATPAK = "flatpak"
    FIREWALL = "firewall"
    XDG_OPEN = "xdg-open"  # Intercept default app openings


class UserRole(str, Enum):
    """User roles in the system"""
    CHILD = "child"
    TEEN = "teen"
    ADULT = "adult"
    PARENT = "parent"


class TimeLimit(BaseModel):
    """Time limit configuration"""
    daily: Optional[timedelta] = Field(default=None, description="Daily time limit")
    weekly: Optional[timedelta] = Field(default=None, description="Weekly time limit")
    monthly: Optional[timedelta] = Field(default=None, description="Monthly time limit")
    
    @validator('daily', 'weekly', 'monthly', pre=True)
    def parse_duration(cls, v):
        if isinstance(v, str):
            return parse_time_duration(v)
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "daily": format_duration(self.daily) if self.daily else None,
            "weekly": format_duration(self.weekly) if self.weekly else None,
            "monthly": format_duration(self.monthly) if self.monthly else None,
        }


class BedtimeSchedule(BaseModel):
    """Bedtime schedule configuration"""
    enabled: bool = Field(default=True, description="Whether bedtime restrictions are enabled")
    start: time = Field(default=time(21, 0), description="Bedtime start time")
    end: time = Field(default=time(7, 0), description="Bedtime end time (next day)")
    strict: bool = Field(default=False, description="If True, completely block access during bedtime")
    
    def is_active(self, current_time: datetime) -> bool:
        """Check if bedtime is currently active"""
        if not self.enabled:
            return False
        
        current = current_time.time()
        
        if self.start <= self.end:
            # Normal case: e.g., 21:00 to 7:00
            return current >= self.start or current < self.end
        else:
            # Crosses midnight: e.g., 23:00 to 1:00
            return current >= self.start or current < self.end


class AppRestriction(BaseModel):
    """Application restriction configuration"""
    app_id: str = Field(..., description="Application identifier (name, flatpak ID, or path)")
    restriction_type: RestrictionType = Field(default=RestrictionType.LIMIT, description="Type of restriction")
    time_limit: Optional[timedelta] = Field(default=None, description="Time limit for LIMIT restriction")
    allowed: bool = Field(default=True, description="Whether the app is allowed")
    
    @validator('time_limit', pre=True)
    def parse_duration(cls, v):
        if isinstance(v, str):
            return parse_time_duration(v)
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "app_id": self.app_id,
            "restriction_type": self.restriction_type.value,
            "allowed": self.allowed
        }
        if self.time_limit:
            result["time_limit"] = format_duration(self.time_limit)
        return result


class WebFilterConfig(BaseModel):
    """Web filtering configuration"""
    enabled: bool = Field(default=True, description="Whether web filtering is enabled")
    safe_search: bool = Field(default=True, description="Enforce safe search on search engines")
    blocked_categories: List[str] = Field(default_factory=list, description="Blocked content categories")
    allowed_domains: List[str] = Field(default_factory=list, description="Explicitly allowed domains")
    blocked_domains: List[str] = Field(default_factory=list, description="Explicitly blocked domains")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "safe_search": self.safe_search,
            "blocked_categories": self.blocked_categories,
            "allowed_domains": self.allowed_domains,
            "blocked_domains": self.blocked_domains
        }


class User(BaseModel):
    """User configuration"""
    username: str = Field(..., description="System username")
    display_name: Optional[str] = Field(default=None, description="Display name")
    age: Optional[int] = Field(default=None, description="User's age")
    role: UserRole = Field(default=UserRole.CHILD, description="User role")
    time_limits: TimeLimit = Field(default_factory=TimeLimit, description="Time limits")
    bedtime: BedtimeSchedule = Field(default_factory=BedtimeSchedule, description="Bedtime schedule")
    app_restrictions: List[AppRestriction] = Field(default_factory=list, description="Application restrictions")
    web_filter: WebFilterConfig = Field(default_factory=WebFilterConfig, description="Web filtering config")
    allowed_apps: List[str] = Field(default_factory=list, description="Explicitly allowed applications")
    restricted_apps: List[str] = Field(default_factory=list, description="Explicitly restricted applications")
    enabled: bool = Field(default=True, description="Whether restrictions are enabled for this user")
    
    @validator('username')
    def validate_username(cls, v):
        if not v:
            raise ValueError("Username cannot be empty")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Username contains invalid characters")
        if len(v) > 32:
            raise ValueError("Username too long (max 32 characters)")
        return v
    
    @validator('age')
    def validate_age(cls, v):
        if v is not None and (v < 0 or v > 150):
            raise ValueError("Age must be between 0 and 150")
        return v
    
    def get_app_restriction(self, app_id: str) -> Optional[AppRestriction]:
        """Get restriction for a specific app"""
        for restriction in self.app_restrictions:
            if restriction.app_id == app_id:
                return restriction
        return None
    
    def is_app_allowed(self, app_id: str) -> bool:
        """Check if an app is allowed for this user"""
        if not self.enabled:
            return True
        
        # Check explicitly allowed apps
        if app_id in self.allowed_apps:
            return True
        
        # Check explicitly restricted apps
        if app_id in self.restricted_apps:
            return False
        
        # Check app restrictions
        restriction = self.get_app_restriction(app_id)
        if restriction:
            return restriction.allowed
        
        # Default: allowed
        return True
    
    def get_time_remaining(self, app_id: str = None) -> Optional[timedelta]:
        """Get remaining time for user or specific app"""
        # This would be calculated based on actual usage
        # For now, return the daily limit as remaining
        if self.time_limits.daily:
            return self.time_limits.daily
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "username": self.username,
            "display_name": self.display_name,
            "age": self.age,
            "role": self.role.value,
            "time_limits": self.time_limits.to_dict(),
            "bedtime": {
                "enabled": self.bedtime.enabled,
                "start": self.bedtime.start.isoformat(),
                "end": self.bedtime.end.isoformat(),
                "strict": self.bedtime.strict
            },
            "app_restrictions": [r.to_dict() for r in self.app_restrictions],
            "web_filter": self.web_filter.to_dict(),
            "allowed_apps": self.allowed_apps,
            "restricted_apps": self.restricted_apps,
            "enabled": self.enabled
        }


class UsageRecord(BaseModel):
    """Record of application usage"""
    id: Optional[int] = Field(default=None, description="Record ID")
    user_id: str = Field(..., description="Username")
    app_id: str = Field(..., description="Application ID")
    app_name: Optional[str] = Field(default=None, description="Application name")
    start_time: datetime = Field(..., description="Start time of usage")
    end_time: Optional[datetime] = Field(default=None, description="End time of usage")
    duration: Optional[timedelta] = Field(default=None, description="Duration of usage")
    
    @validator('duration', pre=True)
    def parse_duration(cls, v):
        if isinstance(v, str):
            return parse_time_duration(v)
        return v
    
    def calculate_duration(self) -> timedelta:
        """Calculate duration from start and end times"""
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return timedelta(0)


class SystemConfig(BaseModel):
    """System-wide configuration"""
    enforcement_method: EnforcementMethod = Field(
        default=EnforcementMethod.CGROUPS,
        description="Primary method for enforcing restrictions"
    )
    grace_period: timedelta = Field(
        default=timedelta(minutes=5),
        description="Grace period before restrictions are enforced"
    )
    monitoring_enabled: bool = Field(default=True, description="Whether monitoring is enabled")
    data_retention_days: int = Field(default=30, description="Days to retain usage data")
    
    @validator('grace_period', pre=True)
    def parse_duration(cls, v):
        if isinstance(v, str):
            return parse_time_duration(v)
        return v


# Utility functions
def parse_time_duration(duration_str: str) -> timedelta:
    """Parse a time duration string into timedelta"""
    if not duration_str:
        return timedelta(0)
    
    duration_str = duration_str.strip().lower()
    
    # Try to parse various formats
    # Format: 1h 30m, 90m, 2h, 1d, etc.
    
    days = 0
    hours = 0
    minutes = 0
    seconds = 0
    
    # Extract days
    day_match = re.search(r'(\d+)d', duration_str)
    if day_match:
        days = int(day_match.group(1))
        duration_str = duration_str.replace(day_match.group(0), '')
    
    # Extract hours
    hour_match = re.search(r'(\d+)h', duration_str)
    if hour_match:
        hours = int(hour_match.group(1))
        duration_str = duration_str.replace(hour_match.group(0), '')
    
    # Extract minutes
    minute_match = re.search(r'(\d+)m', duration_str)
    if minute_match:
        minutes = int(minute_match.group(1))
        duration_str = duration_str.replace(minute_match.group(0), '')
    
    # Extract seconds
    second_match = re.search(r'(\d+)s', duration_str)
    if second_match:
        seconds = int(second_match.group(1))
    
    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def format_duration(duration: timedelta) -> str:
    """Format timedelta into human-readable string"""
    if not duration:
        return "0"
    
    total_seconds = int(duration.total_seconds())
    
    if total_seconds == 0:
        return "0"
    
    parts = []
    
    days = total_seconds // (24 * 3600)
    if days > 0:
        parts.append(f"{days}d")
        total_seconds %= (24 * 3600)
    
    hours = total_seconds // 3600
    if hours > 0:
        parts.append(f"{hours}h")
        total_seconds %= 3600
    
    minutes = total_seconds // 60
    if minutes > 0:
        parts.append(f"{minutes}m")
        total_seconds %= 60
    
    if total_seconds > 0:
        parts.append(f"{total_seconds}s")
    
    return " ".join(parts)


def validate_username(username: str) -> bool:
    """Validate a username"""
    if not username:
        return False
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False
    if len(username) > 32:
        return False
    return True
