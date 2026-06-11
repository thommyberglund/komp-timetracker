"""
Utility functions for Komp TimeTracker core module
"""

from datetime import timedelta
import re


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
