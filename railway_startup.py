#!/usr/bin/env python3
import os
import sys
import time
import uuid
import socket
import logging
import subprocess
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def get_instance_id():
    """Generate a unique instance ID for Railway deployment"""
    # Use Railway environment variables if available
    railway_env = os.environ.get("RAILWAY_ENVIRONMENT_NAME", "")
    railway_service = os.environ.get("RAILWAY_SERVICE_NAME", "")
    railway_id = os.environ.get("RAILWAY_SERVICE_ID", "")
    
    # Generate unique components
    hostname = socket.gethostname()
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Combine into a unique instance ID
    if railway_env and railway_service:
        return f"railway-{railway_env}-{railway_service}-{timestamp}-{unique_id}"
    else:
        return f"{hostname}-{timestamp}-{unique_id}"

def deactivate_old_instances():
    """Deactivate old instances in the database"""
    try:
        # Import database
        from trading_bot.services.database.db import Database
        db = Database()
        
        # Deactivate instances that haven't sent a heartbeat in 2 minutes
        db.execute_query("""
            UPDATE bot_instances 
            SET is_active = FALSE 
            WHERE last_heartbeat < NOW() - INTERVAL '2 minutes'
        """)
        
        logger.info("Deactivated old instances")
        return True
    except Exception as e:
        logger.error(f"Failed to deactivate old instances: {e}")
        return False

def register_instance(instance_id, force_active=True):
    """Register this instance in the database"""
    try:
        # Import database
        from trading_bot.services.database.db import Database
        db = Database()
        
        # Create the bot_instances table if it doesn't exist
        db.execute_query("""
            CREATE TABLE IF NOT EXISTS bot_instances (
                instance_id VARCHAR(255) PRIMARY KEY,
                start_time TIMESTAMP NOT NULL,
                last_heartbeat TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # If force_active, deactivate all other instances
        if force_active:
            db.execute_query("UPDATE bot_instances SET is_active = FALSE")
            
        # Register this instance
        current_time = datetime.now()
        db.execute_query(
            """
            INSERT INTO bot_instances 
            (instance_id, start_time, last_heartbeat, is_active) 
            VALUES (%s, %s, %s, %s)
            """,
            [instance_id, current_time, current_time, force_active]
        )
        
        logger.info(f"Registered instance {instance_id} with active={force_active}")
        return True
    except Exception as e:
        logger.error(f"Failed to register instance: {e}")
        return False

def main():
    """Main function for Railway startup"""
    logger.info("Starting Railway deployment process")
    
    # Generate instance ID
    instance_id = get_instance_id()
    logger.info(f"Generated instance ID: {instance_id}")
    
    # Deactivate old instances
    deactivate_old_instances()
    
    # Register this instance (force active for Railway)
    register_instance(instance_id, force_active=True)
    
    # Start the bot using our instance manager
    logger.info("Starting bot with instance manager")
    cmd = [sys.executable, "instance_manager.py", "--force-activate"]
    
    # Execute the command
    try:
        process = subprocess.Popen(cmd)
        logger.info(f"Started instance manager with PID {process.pid}")
        
        # Wait for the process to complete
        process.wait()
        
        # Exit with the same code
        sys.exit(process.returncode)
    except Exception as e:
        logger.error(f"Failed to start instance manager: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 