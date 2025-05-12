#!/usr/bin/env python3
import os
import sys
import time
import uuid
import socket
import logging
import argparse
import threading
import subprocess
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

class BotInstanceManager:
    """Manages bot instances to ensure only one is active at a time"""
    
    def __init__(self, force_activation=False):
        """
        Initialize the instance manager
        
        Args:
            force_activation: If True, force this instance to be active
        """
        self.instance_id = self._generate_instance_id()
        self.force_activation = force_activation
        self.is_active = False
        self.heartbeat_thread = None
        self.stop_heartbeat = threading.Event()
        
        # Initialize database connection
        try:
            from trading_bot.services.database.db import Database
            self.db = Database()
            logger.info("Database connection initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            self.db = None
            
    def _generate_instance_id(self):
        """Generate a unique instance ID"""
        hostname = socket.gethostname()
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{hostname}-{timestamp}-{unique_id}"
        
    def _heartbeat_updater(self):
        """Update the heartbeat in the database periodically"""
        while not self.stop_heartbeat.is_set():
            try:
                if self.db:
                    # Update heartbeat
                    self.db.execute_query(
                        "UPDATE bot_instances SET last_heartbeat = %s WHERE instance_id = %s",
                        [datetime.now(), self.instance_id]
                    )
                    logger.debug(f"Updated heartbeat for instance {self.instance_id}")
            except Exception as e:
                logger.error(f"Failed to update heartbeat: {e}")
                
            # Wait for next update (every 30 seconds)
            self.stop_heartbeat.wait(30)
            
    def start_heartbeat(self):
        """Start the heartbeat updater thread"""
        if self.heartbeat_thread is None:
            self.stop_heartbeat.clear()
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_updater)
            self.heartbeat_thread.daemon = True
            self.heartbeat_thread.start()
            logger.info(f"Started heartbeat updater for instance {self.instance_id}")
            
    def stop_heartbeat(self):
        """Stop the heartbeat updater thread"""
        if self.heartbeat_thread:
            self.stop_heartbeat.set()
            self.heartbeat_thread.join(timeout=2)
            self.heartbeat_thread = None
            logger.info(f"Stopped heartbeat updater for instance {self.instance_id}")
            
    def register_instance(self):
        """Register this instance in the database and check if it should be active"""
        if not self.db:
            logger.warning("No database connection, assuming this instance should be active")
            return True
            
        try:
            # Force deactivation of other instances if requested
            if self.force_activation:
                logger.info("Force activation requested, deactivating other instances")
                self.db.execute_query(
                    "UPDATE bot_instances SET is_active = FALSE WHERE instance_id != %s",
                    [self.instance_id]
                )
                
            # Check and register this instance
            is_new, is_active = self.db.check_bot_instance(self.instance_id)
            
            if is_new:
                if is_active:
                    logger.info(f"Registered new instance {self.instance_id} as ACTIVE")
                else:
                    logger.info(f"Registered new instance {self.instance_id} as INACTIVE (another instance is active)")
            else:
                logger.info(f"Instance {self.instance_id} already registered, active status: {is_active}")
                
            self.is_active = is_active
            
            # Start heartbeat if active
            if is_active:
                self.start_heartbeat()
                
            return is_active
            
        except Exception as e:
            logger.error(f"Failed to register instance: {e}")
            # Default to active in case of error
            return True
            
    def deactivate_instance(self):
        """Deactivate this instance in the database"""
        if not self.db:
            return
            
        try:
            # Stop heartbeat
            self.stop_heartbeat()
            
            # Update database
            self.db.execute_query(
                "UPDATE bot_instances SET is_active = FALSE WHERE instance_id = %s",
                [self.instance_id]
            )
            logger.info(f"Deactivated instance {self.instance_id}")
            
        except Exception as e:
            logger.error(f"Failed to deactivate instance: {e}")

def main():
    """Main function to check for running bot and start a new instance if needed"""
    parser = argparse.ArgumentParser(description="Manage bot instances")
    parser.add_argument("--force-activate", action="store_true", help="Force this instance to be active")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    args = parser.parse_args()
    
    # Set log level
    logger.setLevel(getattr(logging, args.log_level.upper()))
    
    # Create instance manager
    manager = BotInstanceManager(force_activation=args.force_activate)
    
    # Register instance and check if it should be active
    is_active = manager.register_instance()
    
    if is_active:
        logger.info("This instance is active, starting bot")
        
        try:
            # Build command to start the bot
            cmd = [sys.executable, "-m", "trading_bot.main"]
            
            if args.debug:
                cmd.append("--debug")
            
            if args.log_level:
                cmd.extend(["--log-level", args.log_level])
            
            logger.info(f"Starting bot with command: {' '.join(cmd)}")
            
            # Start the bot process
            process = subprocess.Popen(cmd)
            logger.info(f"Bot started with PID {process.pid}")
            
            # Wait for the process to complete
            process.wait()
            
            # Deactivate instance when bot exits
            manager.deactivate_instance()
            
            # Exit with the same code as the bot
            sys.exit(process.returncode)
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            manager.deactivate_instance()
            sys.exit(1)
    else:
        logger.info("This instance is not active (another instance is running)")
        sys.exit(0)

if __name__ == "__main__":
    main() 