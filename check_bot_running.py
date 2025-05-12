#!/usr/bin/env python3
import os
import sys
import psutil
import logging
import argparse
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def is_bot_running():
    """Check if the trading bot is already running"""
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Skip the current process
            if proc.info['pid'] == current_pid:
                continue
                
            # Check if it's a Python process
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any('trading_bot' in cmd for cmd in cmdline):
                    logger.warning(f"Found existing bot process: PID {proc.info['pid']}, cmdline: {' '.join(cmdline)}")
                    return True, proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    return False, None

def kill_existing_bot(pid):
    """Kill an existing bot process"""
    try:
        process = psutil.Process(pid)
        process.terminate()
        logger.info(f"Terminated existing bot process with PID {pid}")
        
        # Wait for the process to actually terminate
        try:
            process.wait(timeout=5)
            logger.info(f"Process {pid} terminated successfully")
            return True
        except psutil.TimeoutExpired:
            logger.warning(f"Process {pid} did not terminate within timeout, forcing kill")
            process.kill()
            return True
    except psutil.NoSuchProcess:
        logger.info(f"Process {pid} no longer exists")
        return True
    except Exception as e:
        logger.error(f"Failed to kill process {pid}: {e}")
        return False

def main():
    """Main function to check for running bot and start a new instance if needed"""
    parser = argparse.ArgumentParser(description="Check and start trading bot")
    parser.add_argument("--force-kill", action="store_true", help="Force kill any existing bot processes")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    args = parser.parse_args()
    
    # Set log level
    logger.setLevel(getattr(logging, args.log_level.upper()))
    
    # Check if bot is already running
    is_running, pid = is_bot_running()
    
    if is_running:
        logger.warning(f"Bot is already running with PID {pid}")
        
        if args.force_kill:
            logger.info("Force kill option enabled, terminating existing process")
            if kill_existing_bot(pid):
                logger.info("Starting new bot instance after killing old one")
                # Wait a moment to ensure the process is fully terminated
                import time
                time.sleep(2)
                start_bot(args)
            else:
                logger.error("Failed to kill existing process, not starting new instance")
                sys.exit(1)
        else:
            logger.info("Not starting new instance. Use --force-kill to terminate existing process")
            sys.exit(1)
    else:
        logger.info("No existing bot instance found, starting new one")
        start_bot(args)

def start_bot(args):
    """Start the trading bot with the given arguments"""
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
        
        # Exit with success
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 