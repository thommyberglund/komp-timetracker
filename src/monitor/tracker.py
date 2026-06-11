"""
Usage tracker for monitoring application usage
"""

import os
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
import psutil

from ..core.models import UsageRecord, User
from ..config.manager import ConfigManager

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Raised when there's a database error"""
    pass


class UsageTracker:
    """Tracks application usage and stores it in a database"""
    
    def __init__(self, db_path: str = "/var/lib/komp-timetracker/usage.db"):
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._config_manager: Optional[ConfigManager] = None
        
    def _ensure_db_dir(self):
        """Ensure the database directory exists"""
        db_dir = self.db_path.parent
        if not db_dir.exists():
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            except PermissionError:
                logger.error(f"Permission denied: cannot create database directory {db_dir}")
                raise
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection"""
        if self._conn is None:
            self._ensure_db_dir()
            try:
                self._conn = sqlite3.connect(str(self.db_path))
                self._conn.row_factory = sqlite3.Row
                self._initialize_database()
            except sqlite3.Error as e:
                logger.error(f"Database connection error: {e}")
                raise DatabaseError(f"Database connection error: {e}")
        return self._conn
    
    def _initialize_database(self):
        """Initialize the database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id TEXT UNIQUE NOT NULL,
                app_name TEXT,
                flatpak_id TEXT,
                is_flatpak BOOLEAN DEFAULT FALSE,
                is_steam BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                app_id TEXT NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                duration_seconds INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(username),
                FOREIGN KEY (app_id) REFERENCES applications(app_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS web_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                url TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                blocked BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (user_id) REFERENCES users(username)
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_usage_user_app 
            ON usage_sessions(user_id, app_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_usage_start 
            ON usage_sessions(start_time)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_web_user 
            ON web_activity(user_id)
        ''')
        
        conn.commit()
        logger.info("Database initialized")
    
    def close(self):
        """Close the database connection"""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def record_usage_start(self, user_id: str, app_id: str, app_name: str = None) -> int:
        """Record the start of application usage"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Ensure user exists
        cursor.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (user_id,))
        
        # Ensure app exists
        cursor.execute('''
            INSERT OR IGNORE INTO applications (app_id, app_name) 
            VALUES (?, ?)
        ''', (app_id, app_name or app_id))
        
        # Record session start
        cursor.execute('''
            INSERT INTO usage_sessions (user_id, app_id, start_time) 
            VALUES (?, ?, ?)
        ''', (user_id, app_id, datetime.now()))
        
        session_id = cursor.lastrowid
        conn.commit()
        
        logger.debug(f"Recorded usage start: user={user_id}, app={app_id}, session_id={session_id}")
        return session_id
    
    def record_usage_end(self, session_id: int, end_time: datetime = None) -> None:
        """Record the end of application usage"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if end_time is None:
            end_time = datetime.now()
        
        # Get the session
        cursor.execute("SELECT * FROM usage_sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()
        
        if session:
            start_time = datetime.fromisoformat(session['start_time'])
            duration = end_time - start_time
            
            cursor.execute('''
                UPDATE usage_sessions 
                SET end_time = ?, duration_seconds = ? 
                WHERE id = ?
            ''', (end_time.isoformat(), int(duration.total_seconds()), session_id))
            
            conn.commit()
            logger.debug(f"Recorded usage end: session_id={session_id}, duration={duration}")
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all currently active usage sessions"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM usage_sessions 
            WHERE end_time IS NULL
        ''')
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append(dict(row))
        
        return sessions
    
    def get_usage_for_user(self, user_id: str, days: int = 7) -> List[UsageRecord]:
        """Get usage records for a specific user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(days=days)
        
        cursor.execute('''
            SELECT s.*, a.app_name 
            FROM usage_sessions s
            LEFT JOIN applications a ON s.app_id = a.app_id
            WHERE s.user_id = ? AND s.start_time >= ?
            ORDER BY s.start_time DESC
        ''', (user_id, since.isoformat()))
        
        records = []
        for row in cursor.fetchall():
            record = UsageRecord(
                id=row['id'],
                user_id=row['user_id'],
                app_id=row['app_id'],
                app_name=row['app_name'],
                start_time=datetime.fromisoformat(row['start_time']),
                end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
                duration=timedelta(seconds=row['duration_seconds']) if row['duration_seconds'] else None
            )
            records.append(record)
        
        return records
    
    def get_total_usage(self, user_id: str, days: int = 1) -> timedelta:
        """Get total usage time for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(days=days)
        
        cursor.execute('''
            SELECT COALESCE(SUM(duration_seconds), 0) as total_seconds
            FROM usage_sessions 
            WHERE user_id = ? AND start_time >= ?
        ''', (user_id, since.isoformat()))
        
        row = cursor.fetchone()
        total_seconds = row['total_seconds'] if row else 0
        
        return timedelta(seconds=total_seconds)
    
    def get_app_usage(self, user_id: str, app_id: str, days: int = 7) -> timedelta:
        """Get usage time for a specific app"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(days=days)
        
        cursor.execute('''
            SELECT COALESCE(SUM(duration_seconds), 0) as total_seconds
            FROM usage_sessions 
            WHERE user_id = ? AND app_id = ? AND start_time >= ?
        ''', (user_id, app_id, since.isoformat()))
        
        row = cursor.fetchone()
        total_seconds = row['total_seconds'] if row else 0
        
        return timedelta(seconds=total_seconds)
    
    def cleanup_old_data(self, days: int = 30):
        """Remove usage data older than specified days"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days)
        
        cursor.execute('''
            DELETE FROM usage_sessions 
            WHERE start_time < ?
        ''', (cutoff.isoformat(),))
        
        cursor.execute('''
            DELETE FROM web_activity 
            WHERE timestamp < ?
        ''', (cutoff.isoformat(),))
        
        conn.commit()
        logger.info(f"Cleaned up data older than {days} days")


class ProcessMonitor:
    """Monitors running processes and tracks usage"""
    
    def __init__(self, tracker: UsageTracker, config_manager: ConfigManager):
        self.tracker = tracker
        self.config_manager = config_manager
        self.active_sessions: Dict[Tuple[str, str], int] = {}  # (user_id, app_id) -> session_id
        
    def _get_user_from_pid(self, pid: int) -> Optional[str]:
        """Get the user running a process"""
        try:
            process = psutil.Process(pid)
            return process.username()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
    
    def _get_app_id_from_process(self, process: psutil.Process) -> str:
        """Get application ID from a process"""
        try:
            # Try to get the executable name
            exe = process.exe()
            if exe:
                return os.path.basename(exe)
            
            # Try to get the command line
            cmdline = process.cmdline()
            if cmdline:
                return os.path.basename(cmdline[0])
            
            return process.name()
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return "unknown"
    
    def _is_flatpak_process(self, process: psutil.Process) -> bool:
        """Check if a process is a Flatpak application"""
        try:
            # Check if the process is running from a Flatpak directory
            exe = process.exe()
            if exe and "/var/lib/flatpak/app/" in exe:
                return True
            
            # Check command line for flatpak run
            cmdline = " ".join(process.cmdline())
            if "flatpak run" in cmdline:
                return True
            
            return False
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def _get_flatpak_id(self, process: psutil.Process) -> Optional[str]:
        """Get Flatpak ID from a process"""
        try:
            cmdline = " ".join(process.cmdline())
            if "flatpak run" in cmdline:
                # Extract the app ID from flatpak run command
                parts = cmdline.split()
                if "run" in parts:
                    idx = parts.index("run")
                    if idx + 1 < len(parts):
                        return parts[idx + 1]
            
            # Check environment variables
            env = process.environ()
            if env and "FLATPAK_ID" in env:
                return env["FLATPAK_ID"]
            
            return None
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
    
    def _is_steam_process(self, process: psutil.Process) -> bool:
        """Check if a process is related to Steam"""
        try:
            name = process.name().lower()
            exe = process.exe() or ""
            
            steam_indicators = ["steam", "steamos", "steamwebhelper", "steamservice"]
            
            if any(indicator in name for indicator in steam_indicators):
                return True
            
            if any(indicator in exe.lower() for indicator in steam_indicators):
                return True
            
            return False
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def scan_processes(self):
        """Scan all running processes and track usage"""
        logger.debug("Scanning processes...")
        
        # Get all users from config
        users = self.config_manager.users
        
        # Get all running processes
        processes = list(psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'username']))
        
        for process in processes:
            try:
                pid = process.info['pid']
                username = process.info['username']
                
                # Only track users that are in our configuration
                if username not in users:
                    continue
                
                user = users[username]
                
                # Skip if user is not enabled
                if not user.enabled:
                    continue
                
                # Get app ID
                app_id = self._get_app_id_from_process(process)
                
                # Check if it's a Flatpak app
                if self._is_flatpak_process(process):
                    flatpak_id = self._get_flatpak_id(process)
                    if flatpak_id:
                        app_id = flatpak_id
                
                # Check if it's Steam
                if self._is_steam_process(process):
                    app_id = "steam"
                
                # Skip system processes
                if app_id in ["systemd", "init", "kernel", ""]:
                    continue
                
                # Check if we already have an active session for this user/app
                key = (username, app_id)
                
                if key not in self.active_sessions:
                    # Start a new session
                    session_id = self.tracker.record_usage_start(username, app_id)
                    self.active_sessions[key] = session_id
                    logger.debug(f"Started tracking: user={username}, app={app_id}, pid={pid}")
                
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.debug(f"Error accessing process {pid}: {e}")
                continue
        
        # Check for ended sessions
        self._check_ended_sessions()
    
    def _check_ended_sessions(self):
        """Check for sessions that have ended"""
        active_pids = set()
        
        # Get all currently running PIDs
        for process in psutil.process_iter(['pid', 'username']):
            try:
                active_pids.add(process.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Check our active sessions
        ended_sessions = []
        
        for (user_id, app_id), session_id in self.active_sessions.items():
            # For now, we'll assume sessions are still active
            # In a more sophisticated implementation, we'd track PIDs
            pass
        
        # For simplicity, we'll just keep sessions open
        # A real implementation would track process lifetimes
    
    def stop_all_sessions(self):
        """Stop all active sessions"""
        for (user_id, app_id), session_id in self.active_sessions.items():
            self.tracker.record_usage_end(session_id)
        
        self.active_sessions.clear()
        logger.info("Stopped all active sessions")
    
    def monitor_continuously(self, interval: float = 60.0):
        """Monitor processes continuously"""
        logger.info(f"Starting continuous monitoring with {interval}s interval")
        
        try:
            while True:
                self.scan_processes()
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            self.stop_all_sessions()
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
            self.stop_all_sessions()
