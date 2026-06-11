"""
Tests for data models
"""

import pytest
from datetime import datetime, time, timedelta
from src.core.models import (
    User, 
    AppRestriction, 
    TimeLimit, 
    BedtimeSchedule, 
    WebFilterConfig,
    UsageRecord,
    SystemConfig,
    RestrictionType,
    EnforcementMethod,
    UserRole,
    parse_time_duration,
    format_duration,
    validate_username
)


class TestTimeParsing:
    """Test time duration parsing and formatting"""
    
    def test_parse_simple_hours(self):
        """Test parsing simple hours"""
        assert parse_time_duration("2h") == timedelta(hours=2)
        assert parse_time_duration("1h") == timedelta(hours=1)
        
    def test_parse_simple_minutes(self):
        """Test parsing simple minutes"""
        assert parse_time_duration("30m") == timedelta(minutes=30)
        assert parse_time_duration("45m") == timedelta(minutes=45)
        
    def test_parse_combined(self):
        """Test parsing combined hours and minutes"""
        assert parse_time_duration("1h 30m") == timedelta(hours=1, minutes=30)
        assert parse_time_duration("2h 15m") == timedelta(hours=2, minutes=15)
        
    def test_parse_with_days(self):
        """Test parsing with days"""
        assert parse_time_duration("1d") == timedelta(days=1)
        assert parse_time_duration("1d 2h") == timedelta(days=1, hours=2)
        
    def test_parse_with_seconds(self):
        """Test parsing with seconds"""
        assert parse_time_duration("30s") == timedelta(seconds=30)
        assert parse_time_duration("1m 30s") == timedelta(minutes=1, seconds=30)
        
    def test_parse_empty(self):
        """Test parsing empty string"""
        assert parse_time_duration("") == timedelta(0)
        assert parse_time_duration(None) == timedelta(0)


class TestTimeFormatting:
    """Test time duration formatting"""
    
    def test_format_hours(self):
        """Test formatting hours"""
        assert format_duration(timedelta(hours=2)) == "2h"
        assert format_duration(timedelta(hours=1)) == "1h"
        
    def test_format_minutes(self):
        """Test formatting minutes"""
        assert format_duration(timedelta(minutes=30)) == "30m"
        assert format_duration(timedelta(minutes=45)) == "45m"
        
    def test_format_combined(self):
        """Test formatting combined durations"""
        assert format_duration(timedelta(hours=1, minutes=30)) == "1h 30m"
        assert format_duration(timedelta(hours=2, minutes=15, seconds=30)) == "2h 15m 30s"
        
    def test_format_with_days(self):
        """Test formatting with days"""
        assert format_duration(timedelta(days=1)) == "1d"
        assert format_duration(timedelta(days=1, hours=2)) == "1d 2h"
        
    def test_format_zero(self):
        """Test formatting zero duration"""
        assert format_duration(timedelta(0)) == "0"


class TestUsernameValidation:
    """Test username validation"""
    
    def test_valid_usernames(self):
        """Test valid usernames"""
        assert validate_username("child1") == True
        assert validate_username("user_name") == True
        assert validate_username("user-name") == True
        assert validate_username("user123") == True
        
    def test_invalid_usernames(self):
        """Test invalid usernames"""
        assert validate_username("") == False
        assert validate_username("user name") == False
        assert validate_username("user@name") == False
        assert validate_username("a" * 33) == False  # Too long


class TestUserModel:
    """Test User model"""
    
    def test_create_user(self):
        """Test creating a user"""
        user = User(
            username="testuser",
            display_name="Test User",
            age=12,
            role=UserRole.CHILD
        )
        assert user.username == "testuser"
        assert user.display_name == "Test User"
        assert user.age == 12
        assert user.role == UserRole.CHILD
        assert user.enabled == True
        
    def test_user_with_time_limits(self):
        """Test user with time limits"""
        user = User(
            username="testuser",
            time_limits=TimeLimit(
                daily=timedelta(hours=2),
                weekly=timedelta(hours=10)
            )
        )
        assert user.time_limits.daily == timedelta(hours=2)
        assert user.time_limits.weekly == timedelta(hours=10)
        
    def test_user_with_bedtime(self):
        """Test user with bedtime schedule"""
        user = User(
            username="testuser",
            bedtime=BedtimeSchedule(
                enabled=True,
                start=time(21, 0),
                end=time(7, 0)
            )
        )
        assert user.bedtime.enabled == True
        assert user.bedtime.start == time(21, 0)
        assert user.bedtime.end == time(7, 0)
        
    def test_bedtime_is_active(self):
        """Test bedtime active check"""
        bedtime = BedtimeSchedule(
            enabled=True,
            start=time(21, 0),
            end=time(7, 0)
        )
        
        # Test during bedtime (22:00)
        assert bedtime.is_active(datetime(2024, 1, 1, 22, 0)) == True
        
        # Test outside bedtime (10:00)
        assert bedtime.is_active(datetime(2024, 1, 1, 10, 0)) == False
        
        # Test disabled bedtime
        bedtime.enabled = False
        assert bedtime.is_active(datetime(2024, 1, 1, 22, 0)) == False


class TestAppRestriction:
    """Test AppRestriction model"""
    
    def test_create_restriction(self):
        """Test creating an app restriction"""
        restriction = AppRestriction(
            app_id="steam",
            restriction_type=RestrictionType.LIMIT,
            time_limit=timedelta(hours=1),
            allowed=True
        )
        assert restriction.app_id == "steam"
        assert restriction.restriction_type == RestrictionType.LIMIT
        assert restriction.time_limit == timedelta(hours=1)
        assert restriction.allowed == True
        
    def test_block_restriction(self):
        """Test block restriction"""
        restriction = AppRestriction(
            app_id="discord",
            restriction_type=RestrictionType.BLOCK,
            allowed=False
        )
        assert restriction.restriction_type == RestrictionType.BLOCK
        assert restriction.allowed == False


class TestWebFilterConfig:
    """Test WebFilterConfig model"""
    
    def test_create_web_filter(self):
        """Test creating web filter config"""
        web_filter = WebFilterConfig(
            enabled=True,
            safe_search=True,
            blocked_categories=["adult", "gambling"],
            allowed_domains=["example.com"],
            blocked_domains=["youtube.com"]
        )
        assert web_filter.enabled == True
        assert web_filter.safe_search == True
        assert "adult" in web_filter.blocked_categories
        assert "example.com" in web_filter.allowed_domains
        assert "youtube.com" in web_filter.blocked_domains


class TestSystemConfig:
    """Test SystemConfig model"""
    
    def test_create_system_config(self):
        """Test creating system config"""
        config = SystemConfig(
            enforcement_method=EnforcementMethod.FLATPAK,
            grace_period=timedelta(minutes=5),
            monitoring_enabled=True,
            data_retention_days=30
        )
        assert config.enforcement_method == EnforcementMethod.FLATPAK
        assert config.grace_period == timedelta(minutes=5)
        assert config.monitoring_enabled == True
        assert config.data_retention_days == 30
