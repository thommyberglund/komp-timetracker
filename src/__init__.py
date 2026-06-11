"""
Komp TimeTracker - Parental Control for Bazzite Linux

A comprehensive parental control application for Bazzite Linux.
"""

__version__ = "0.1.0"
__author__ = "Thommy Berglund"
__license__ = "MIT"

from .core.models import User, AppRestriction, TimeLimit, BedtimeSchedule
from .config.manager import ConfigManager
from .monitor.tracker import UsageTracker
from .restrict.enforcer import RestrictionEnforcer

# Default paths
DEFAULT_CONFIG_PATH = "/etc/komp-timetracker/config.yaml"
DEFAULT_DB_PATH = "/var/lib/komp-timetracker/usage.db"
DEFAULT_LOG_PATH = "/var/log/komp-timetracker"
