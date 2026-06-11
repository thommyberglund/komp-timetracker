"""
Main service module for Komp TimeTracker
This runs as a systemd service to manage the parental control system
"""

import os
import sys
import logging
import time
from datetime import datetime
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from config.manager import ConfigManager, ConfigFileNotFoundError, InvalidConfigError
from monitor.tracker import UsageTracker
from monitor.process import ProcessMonitor
from restrict.enforcer import RestrictionEnforcer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/komp-timetracker/service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Main service entry point"""
    logger.info("Starting Komp TimeTracker service")
    
    # Initialize components
    config_path = os.environ.get('KOMP_CONFIG', '/etc/komp-timetracker/config.yaml')
    db_path = os.environ.get('KOMP_DB', '/var/lib/komp-timetracker/usage.db')
    
    try:
        # Load configuration
        config_manager = ConfigManager(config_path)
        config_manager.load()
        logger.info(f"Loaded configuration from {config_path}")
        
        # Initialize tracker
        tracker = UsageTracker(db_path)
        logger.info(f"Initialized usage tracker with database at {db_path}")
        
        # Initialize enforcer
        enforcer = RestrictionEnforcer(config_manager, tracker)
        logger.info("Initialized restriction enforcer")
        
        # Initialize process monitor
        process_monitor = ProcessMonitor(tracker, config_manager)
        logger.info("Initialized process monitor")
        
        # Main service loop
        logger.info("Starting main service loop")
        
        while True:
            try:
                # Check and enforce restrictions for all users
                enforcer.check_all_users()
                
                # Scan processes and track usage
                process_monitor.scan_processes()
                
                # Clean up old data periodically (once per day)
                if datetime.now().hour == 0 and datetime.now().minute == 0:
                    retention_days = config_manager.system_config.data_retention_days
                    tracker.cleanup_old_data(retention_days)
                
                # Sleep for a while
                time.sleep(60)
                
            except KeyboardInterrupt:
                logger.info("Service stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main service loop: {e}")
                time.sleep(60)  # Wait before retrying
        
    except ConfigFileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        # Create default config
        config_manager = ConfigManager(config_path)
        config_manager.load(create_default=True)
        logger.info("Created default configuration")
        main()  # Retry
        
    except InvalidConfigError as e:
        logger.error(f"Invalid configuration: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error in service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
