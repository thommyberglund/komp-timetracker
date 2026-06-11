"""
Command-line interface for Komp TimeTracker
"""

import os
import sys
import logging
import click
from datetime import datetime, time, timedelta
from typing import Optional, List, Dict, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, BarColumn, TimeRemainingColumn

from ..core.models import (
    User, 
    AppRestriction, 
    TimeLimit, 
    BedtimeSchedule, 
    UserRole,
    RestrictionType,
    parse_time_duration,
    format_duration
)
from ..config.manager import ConfigManager, ConfigFileNotFoundError, InvalidConfigError
from ..monitor.tracker import UsageTracker
from ..restrict.enforcer import RestrictionEnforcer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rich console
console = Console()


class KompControlCLI:
    """Main CLI class for Komp TimeTracker"""
    
    def __init__(self, config_path: str = "/etc/komp-timetracker/config.yaml", 
                 db_path: str = "/var/lib/komp-timetracker/usage.db"):
        self.config_manager = ConfigManager(config_path)
        self.tracker = UsageTracker(db_path)
        self.enforcer = RestrictionEnforcer(self.config_manager, self.tracker)
        
    def status(self, user: Optional[str] = None):
        """Show status of parental controls"""
        try:
            self.config_manager.load()
            users = self.config_manager.users
            
            if user:
                # Show status for specific user
                self._show_user_status(user, users)
            else:
                # Show status for all users
                self._show_all_users_status(users)
                
        except (ConfigFileNotFoundError, InvalidConfigError) as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
    
    def _show_all_users_status(self, users: Dict[str, User]):
        """Show status for all users"""
        table = Table(title="Komp TimeTracker - User Status", show_header=True, header_style="bold blue")
        
        table.add_column("Username", style="cyan")
        table.add_column("Display Name", style="green")
        table.add_column("Role", style="magenta")
        table.add_column("Enabled", style="yellow")
        table.add_column("Bedtime Active", style="red")
        table.add_column("Daily Usage", style="blue")
        table.add_column("Status", style="bold")
        
        for username, user in users.items():
            daily_usage = self.tracker.get_total_usage(username, days=1)
            daily_limit = user.time_limits.daily
            
            # Check if restricted
            status = self.enforcer.get_restriction_status(user)
            is_restricted = status["restricted"]
            
            # Format daily usage
            usage_str = format_duration(daily_usage)
            if daily_limit:
                usage_str += f" / {format_duration(daily_limit)}"
            
            # Bedtime status
            bedtime_active = user.bedtime.is_active(datetime.now())
            
            status_text = "[green]Active[/green]" if not is_restricted else "[red]Restricted[/red]"
            if is_restricted and status["reasons"]:
                reasons = ", ".join(status["reasons"])
                status_text += f" ({reasons})"
            
            table.add_row(
                username,
                user.display_name or "-",
                user.role.value,
                "Yes" if user.enabled else "No",
                "Yes" if bedtime_active else "No",
                usage_str,
                status_text
            )
        
        console.print(table)
        
        # Show system info
        system_info = self._get_system_info()
        console.print(f"\n[bold blue]System Info:[/bold blue]")
        console.print(f"  Enforcement Method: {system_info['enforcement_method']}")
        console.print(f"  Monitoring Enabled: {system_info['monitoring_enabled']}")
        console.print(f"  Data Retention: {system_info['data_retention_days']} days")
    
    def _show_user_status(self, username: str, users: Dict[str, User]):
        """Show detailed status for a specific user"""
        if username not in users:
            console.print(f"[red]User '{username}' not found[/red]")
            return
        
        user = users[username]
        status = self.enforcer.get_restriction_status(user)
        
        # Create a panel for user info
        user_info = Text()
        user_info.append(f"Username: {user.username}\n", style="cyan")
        user_info.append(f"Display Name: {user.display_name or '-'}\n", style="green")
        user_info.append(f"Age: {user.age or '-'}\n", style="yellow")
        user_info.append(f"Role: {user.role.value}\n", style="magenta")
        user_info.append(f"Enabled: {'Yes' if user.enabled else 'No'}\n", style="yellow")
        
        console.print(Panel(user_info, title="[bold blue]User Information[/bold blue]"))
        
        # Time limits
        time_limits = Text()
        if user.time_limits.daily:
            daily_usage = self.tracker.get_total_usage(username, days=1)
            remaining = user.time_limits.daily - daily_usage
            time_limits.append(f"Daily: {format_duration(daily_usage)} / {format_duration(user.time_limits.daily)}")
            if remaining > timedelta(0):
                time_limits.append(f" (Remaining: {format_duration(remaining)})")
            time_limits.append("\n")
        
        if user.time_limits.weekly:
            weekly_usage = self.tracker.get_total_usage(username, days=7)
            remaining = user.time_limits.weekly - weekly_usage
            time_limits.append(f"Weekly: {format_duration(weekly_usage)} / {format_duration(user.time_limits.weekly)}")
            if remaining > timedelta(0):
                time_limits.append(f" (Remaining: {format_duration(remaining)})")
            time_limits.append("\n")
        
        if user.time_limits.monthly:
            monthly_usage = self.tracker.get_total_usage(username, days=30)
            remaining = user.time_limits.monthly - monthly_usage
            time_limits.append(f"Monthly: {format_duration(monthly_usage)} / {format_duration(user.time_limits.monthly)}")
            if remaining > timedelta(0):
                time_limits.append(f" (Remaining: {format_duration(remaining)})")
        
        console.print(Panel(time_limits, title="[bold blue]Time Limits[/bold blue]"))
        
        # Bedtime schedule
        bedtime_info = Text()
        bedtime_info.append(f"Enabled: {'Yes' if user.bedtime.enabled else 'No'}\n")
        bedtime_info.append(f"Start: {user.bedtime.start.strftime('%H:%M')}\n")
        bedtime_info.append(f"End: {user.bedtime.end.strftime('%H:%M')}\n")
        bedtime_info.append(f"Strict: {'Yes' if user.bedtime.strict else 'No'}\n")
        bedtime_info.append(f"Active Now: {'Yes' if user.bedtime.is_active(datetime.now()) else 'No'}")
        
        console.print(Panel(bedtime_info, title="[bold blue]Bedtime Schedule[/bold blue]"))
        
        # Restriction status
        status_text = Text()
        status_text.append(f"Restricted: {'Yes' if status['restricted'] else 'No'}\n", 
                           style="red" if status['restricted'] else "green")
        if status['reasons']:
            status_text.append(f"Reasons: {', '.join(status['reasons'])}\n")
        
        console.print(Panel(status_text, title="[bold blue]Restriction Status[/bold blue]"))
        
        # App restrictions
        if user.app_restrictions:
            app_table = Table(title="App Restrictions", show_header=True)
            app_table.add_column("App ID", style="cyan")
            app_table.add_column("Type", style="magenta")
            app_table.add_column("Allowed", style="yellow")
            app_table.add_column("Time Limit", style="blue")
            
            for restriction in user.app_restrictions:
                time_limit_str = format_duration(restriction.time_limit) if restriction.time_limit else "-"
                app_table.add_row(
                    restriction.app_id,
                    restriction.restriction_type.value,
                    "Yes" if restriction.allowed else "No",
                    time_limit_str
                )
            
            console.print(app_table)
        
        # Allowed/Restricted apps
        if user.allowed_apps or user.restricted_apps:
            apps_info = Text()
            if user.allowed_apps:
                apps_info.append(f"Allowed Apps: {', '.join(user.allowed_apps)}\n")
            if user.restricted_apps:
                apps_info.append(f"Restricted Apps: {', '.join(user.restricted_apps)}")
            console.print(Panel(apps_info, title="[bold blue]App Lists[/bold blue]"))
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system configuration info"""
        system_config = self.config_manager.system_config
        return {
            "enforcement_method": system_config.enforcement_method.value,
            "monitoring_enabled": "Yes" if system_config.monitoring_enabled else "No",
            "grace_period": format_duration(system_config.grace_period),
            "data_retention_days": system_config.data_retention_days
        }
    
    def add_user(self, username: str, display_name: Optional[str] = None, 
                 age: Optional[int] = None, role: str = "child",
                 daily_limit: Optional[str] = None, weekly_limit: Optional[str] = None,
                 bedtime_start: Optional[str] = None, bedtime_end: Optional[str] = None):
        """Add a new user"""
        try:
            # Validate username
            if not username:
                console.print("[red]Error: Username is required[/red]")
                return False
            
            # Check if user already exists
            self.config_manager.load()
            users = self.config_manager.users
            if username in users:
                console.print(f"[red]Error: User '{username}' already exists[/red]")
                return False
            
            # Parse time limits
            daily_timedelta = parse_time_duration(daily_limit) if daily_limit else None
            weekly_timedelta = parse_time_duration(weekly_limit) if weekly_limit else None
            
            # Parse bedtime
            try:
                start_time = self._parse_time(bedtime_start) if bedtime_start else time(21, 0)
                end_time = self._parse_time(bedtime_end) if bedtime_end else time(7, 0)
            except ValueError as e:
                console.print(f"[red]Error: Invalid time format: {e}[/red]")
                return False
            
            # Create user
            user = User(
                username=username,
                display_name=display_name,
                age=age,
                role=UserRole(role),
                time_limits=TimeLimit(
                    daily=daily_timedelta,
                    weekly=weekly_timedelta
                ),
                bedtime=BedtimeSchedule(
                    enabled=True,
                    start=start_time,
                    end=end_time
                )
            )
            
            # Add user to config
            self.config_manager.add_user(user)
            console.print(f"[green]Added user: {username}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]Error adding user: {e}[/red]")
            return False
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string into time object"""
        if ":" in time_str:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return time(hour, minute)
        else:
            hour = int(time_str)
            return time(hour, 0)
    
    def remove_user(self, username: str):
        """Remove a user"""
        try:
            self.config_manager.load()
            self.config_manager.remove_user(username)
            console.print(f"[green]Removed user: {username}[/green]")
            return True
            
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Error removing user: {e}[/red]")
            return False
    
    def restrict_app(self, username: str, app_id: str, limit: Optional[str] = None,
                     restriction_type: str = "limit", allowed: bool = True):
        """Add or update an app restriction for a user"""
        try:
            self.config_manager.load()
            user = self.config_manager.get_user(username)
            
            if not user:
                console.print(f"[red]Error: User '{username}' not found[/red]")
                return False
            
            # Parse time limit
            time_limit = parse_time_duration(limit) if limit else None
            
            # Create or update restriction
            restriction = AppRestriction(
                app_id=app_id,
                restriction_type=RestrictionType(restriction_type),
                time_limit=time_limit,
                allowed=allowed
            )
            
            # Update user's app restrictions
            # Remove existing restriction for this app
            user.app_restrictions = [
                r for r in user.app_restrictions if r.app_id != app_id
            ]
            
            # Add new restriction
            user.app_restrictions.append(restriction)
            
            # Update user in config
            self.config_manager.update_user(username, user.to_dict())
            console.print(f"[green]Added app restriction: {username} -> {app_id} ({restriction_type})[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]Error adding app restriction: {e}[/red]")
            return False
    
    def bedtime(self, username: str, start: Optional[str] = None, 
                end: Optional[str] = None, enabled: Optional[bool] = None,
                strict: Optional[bool] = None):
        """Configure bedtime for a user"""
        try:
            self.config_manager.load()
            user = self.config_manager.get_user(username)
            
            if not user:
                console.print(f"[red]Error: User '{username}' not found[/red]")
                return False
            
            # Update bedtime settings
            if start:
                user.bedtime.start = self._parse_time(start)
            if end:
                user.bedtime.end = self._parse_time(end)
            if enabled is not None:
                user.bedtime.enabled = enabled
            if strict is not None:
                user.bedtime.strict = strict
            
            # Update user in config
            self.config_manager.update_user(username, user.to_dict())
            console.print(f"[green]Updated bedtime for user: {username}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]Error updating bedtime: {e}[/red]")
            return False
    
    def report(self, username: Optional[str] = None, days: int = 7, 
               app: Optional[str] = None):
        """Generate usage reports"""
        try:
            self.config_manager.load()
            
            if username:
                # Report for specific user
                self._show_user_report(username, days, app)
            else:
                # Report for all users
                users = self.config_manager.users
                for username, user in users.items():
                    self._show_user_report(username, days, app)
                    console.print()
                    
        except Exception as e:
            console.print(f"[red]Error generating report: {e}[/red]")
    
    def _show_user_report(self, username: str, days: int, app: Optional[str]):
        """Show usage report for a user"""
        if app:
            # Report for specific app
            app_usage = self.tracker.get_app_usage(username, app, days=days)
            console.print(f"[bold blue]Usage Report for {username} - {app}[/bold blue]")
            console.print(f"  Last {days} days: {format_duration(app_usage)}")
        else:
            # Report for all apps
            usage_records = self.tracker.get_usage_for_user(username, days=days)
            
            if not usage_records:
                console.print(f"[yellow]No usage data for {username} in the last {days} days[/yellow]")
                return
            
            console.print(f"[bold blue]Usage Report for {username} - Last {days} days[/bold blue]")
            
            # Group by app
            app_usage: Dict[str, timedelta] = {}
            for record in usage_records:
                if record.app_id not in app_usage:
                    app_usage[record.app_id] = timedelta(0)
                if record.duration:
                    app_usage[record.app_id] += record.duration
            
            # Sort by usage time (descending)
            sorted_apps = sorted(app_usage.items(), key=lambda x: x[1].total_seconds(), reverse=True)
            
            # Display as table
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("App ID", style="cyan")
            table.add_column("App Name", style="green")
            table.add_column("Usage Time", style="magenta")
            
            for app_id, duration in sorted_apps:
                # Get app name from records
                app_name = "-"
                for record in usage_records:
                    if record.app_id == app_id and record.app_name:
                        app_name = record.app_name
                        break
                
                table.add_row(app_id, app_name, format_duration(duration))
            
            # Add total
            total_usage = sum(duration for _, duration in sorted_apps)
            table.add_row("[bold]TOTAL[/bold]", "", f"[bold]{format_duration(total_usage)}[/bold]")
            
            console.print(table)
    
    def enable_user(self, username: str, enabled: bool = True):
        """Enable or disable restrictions for a user"""
        try:
            self.config_manager.load()
            user = self.config_manager.get_user(username)
            
            if not user:
                console.print(f"[red]Error: User '{username}' not found[/red]")
                return False
            
            user.enabled = enabled
            self.config_manager.update_user(username, user.to_dict())
            
            action = "enabled" if enabled else "disabled"
            console.print(f"[green]Restrictions {action} for user: {username}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]Error updating user: {e}[/red]")
            return False
    
    def cleanup(self, days: int = 30):
        """Clean up old usage data"""
        try:
            self.tracker.cleanup_old_data(days)
            console.print(f"[green]Cleaned up usage data older than {days} days[/green]")
            return True
        except Exception as e:
            console.print(f"[red]Error cleaning up data: {e}[/red]")
            return False


# Click command group
@click.group()
@click.option('--config', default='/etc/komp-timetracker/config.yaml', 
              help='Path to configuration file')
@click.option('--db', default='/var/lib/komp-timetracker/usage.db', 
              help='Path to usage database')
@click.pass_context
def cli(ctx, config, db):
    """Komp TimeTracker - Parental Control for Bazzite Linux"""
    ctx.obj = KompControlCLI(config, db)


# Status command
@cli.command()
@click.argument('user', required=False)
@click.pass_context
def status(ctx, user):
    """Show status of parental controls"""
    ctx.obj.status(user)


# Add user command
@cli.command()
@click.argument('username')
@click.option('--name', 'display_name', help='Display name')
@click.option('--age', type=int, help='User age')
@click.option('--role', default='child', help='User role (child, teen, adult, parent)')
@click.option('--daily-limit', help='Daily time limit (e.g., 2h, 30m)')
@click.option('--weekly-limit', help='Weekly time limit (e.g., 10h, 1d)')
@click.option('--bedtime-start', help='Bedtime start time (e.g., 21:00)')
@click.option('--bedtime-end', help='Bedtime end time (e.g., 7:00)')
@click.pass_context
def add_user(ctx, username, display_name, age, role, daily_limit, weekly_limit, bedtime_start, bedtime_end):
    """Add a new user"""
    ctx.obj.add_user(
        username=username,
        display_name=display_name,
        age=age,
        role=role,
        daily_limit=daily_limit,
        weekly_limit=weekly_limit,
        bedtime_start=bedtime_start,
        bedtime_end=bedtime_end
    )


# Remove user command
@cli.command()
@click.argument('username')
@click.pass_context
def remove_user(ctx, username):
    """Remove a user"""
    ctx.obj.remove_user(username)


# Restrict app command
@cli.command()
@click.argument('username')
@click.argument('app')
@click.option('--limit', help='Time limit for the app (e.g., 1h, 30m)')
@click.option('--type', 'restriction_type', default='limit', 
              help='Restriction type (block, limit, allow)')
@click.option('--allowed/--blocked', default=True, help='Whether the app is allowed')
@click.pass_context
def restrict_app(ctx, username, app, limit, restriction_type, allowed):
    """Add or update an app restriction for a user"""
    ctx.obj.restrict_app(
        username=username,
        app_id=app,
        limit=limit,
        restriction_type=restriction_type,
        allowed=allowed
    )


# Bedtime command
@cli.command()
@click.argument('username')
@click.option('--start', help='Bedtime start time (e.g., 21:00)')
@click.option('--end', help='Bedtime end time (e.g., 7:00)')
@click.option('--enabled/--disabled', default=None, help='Enable or disable bedtime')
@click.option('--strict/--no-strict', default=None, help='Strict bedtime enforcement')
@click.pass_context
def bedtime(ctx, username, start, end, enabled, strict):
    """Configure bedtime for a user"""
    ctx.obj.bedtime(
        username=username,
        start=start,
        end=end,
        enabled=enabled,
        strict=strict
    )


# Report command
@cli.command()
@click.argument('user', required=False)
@click.option('--days', default=7, type=int, help='Number of days to report')
@click.option('--app', help='Report for specific app only')
@click.pass_context
def report(ctx, user, days, app):
    """Generate usage reports"""
    ctx.obj.report(username=user, days=days, app=app)


# Enable/Disable command
@cli.command()
@click.argument('username')
@click.option('--enable/--disable', default=True, help='Enable or disable restrictions')
@click.pass_context
def enable(ctx, username, enable):
    """Enable or disable restrictions for a user"""
    ctx.obj.enable_user(username, enable)


# Cleanup command
@cli.command()
@click.option('--days', default=30, type=int, help='Days of data to keep')
@click.pass_context
def cleanup(ctx, days):
    """Clean up old usage data"""
    ctx.obj.cleanup(days)


def main():
    """Main entry point for the CLI"""
    cli(obj={})


if __name__ == "__main__":
    main()
