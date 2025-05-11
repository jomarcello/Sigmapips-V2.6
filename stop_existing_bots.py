#!/usr/bin/env python3
"""
Script to check for and stop any existing bot instances.
Run this before starting a new bot to avoid Telegram API conflicts.
"""

import os
import sys
import psutil
import logging
import time
import json
import signal
import subprocess
import httpx
import asyncio
import datetime
from telegram import Bot
from telegram.error import TelegramError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# File to store the lock information
LOCK_FILE = '/tmp/telegbot_instance.lock'
BOT_TOKEN = os.environ.get('BOT_TOKEN') or '7328581013:AAGDFJyvipmQsV5UQLjUeLQmX2CWIU2VMjk'

def get_bot_token_from_env():
    """Get bot token from environment variable"""
    return BOT_TOKEN

async def clear_telegram_sessions(bot_token=None):
    """Clear any lingering Telegram bot sessions by making API calls"""
    if not bot_token:
        bot_token = get_bot_token_from_env()
    
    if not bot_token:
        logger.error("No bot token found in environment variables")
        return False
    
    try:
        # First check webhook status
        webhook_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url)
            logger.info(f"Webhook info response: {response.status_code}")
        
        # Then send a dummy getUpdates request with minimal timeout to clear any sessions
        logger.info("Sending dummy getUpdates request to clear sessions...")
        updates_url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        async with httpx.AsyncClient() as client:
            params = {'timeout': 1, 'offset': -1, 'limit': 1}
            response = await client.post(updates_url, params=params)
            logger.info("Dummy getUpdates request completed")
        
        # Wait a moment to ensure sessions are cleared
        await asyncio.sleep(1)
        
        return True
    except Exception as e:
        logger.error(f"Error clearing Telegram sessions: {str(e)}")
        return False

def kill_process(pid):
    """Kill a process by PID"""
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
        # Check if the process is still running
        if psutil.pid_exists(pid):
            # If still running, force kill
            os.kill(pid, signal.SIGKILL)
        return True
    except ProcessLookupError:
        return False
    except Exception as e:
        logger.error(f"Error killing process {pid}: {str(e)}")
        return False

def find_bot_processes():
    """Find all running Python processes that might be running our bot"""
    bot_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Look for Python processes running our bot
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if 'trading_bot' in cmdline and 'main.py' in cmdline:
                        # Don't include our own PID
                        if proc.info['pid'] != os.getpid():
                            bot_processes.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    return bot_processes

def check_lock_file():
    """Check if there's a lock file and if the process is still running"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                data = json.load(f)
                pid = data.get('pid')
                if pid and psutil.pid_exists(pid):
                    return pid
                else:
                    logger.info(f"Stale lock file found. PID {pid} is not running.")
                    os.remove(LOCK_FILE)
                    return None
        except Exception as e:
            logger.error(f"Error reading lock file: {str(e)}")
            os.remove(LOCK_FILE)
            return None
    return None

def create_lock_file():
    """Create a lock file with our PID"""
    try:
        with open(LOCK_FILE, 'w') as f:
            data = {
                'pid': os.getpid(),
                'timestamp': datetime.datetime.now().isoformat()
            }
            json.dump(data, f)
        logger.info(f"Created lock file at {LOCK_FILE} with PID {os.getpid()}")
        return True
    except Exception as e:
        logger.error(f"Error creating lock file: {str(e)}")
        return False

async def main():
    """Main function to check and stop any existing bot instances"""
    logger.info("Checking for existing bot instances...")
    
    # Check if there's a lock file
    locked_pid = check_lock_file()
    if locked_pid:
        logger.info(f"Found running bot instance with PID {locked_pid}")
        if kill_process(locked_pid):
            logger.info(f"Successfully terminated bot process with PID {locked_pid}")
        else:
            logger.warning(f"Failed to terminate bot process with PID {locked_pid}")
    
    # Find and kill any bot processes
    bot_processes = find_bot_processes()
    if bot_processes:
        logger.info(f"Found {len(bot_processes)} bot processes: {bot_processes}")
        for pid in bot_processes:
            if kill_process(pid):
                logger.info(f"Successfully terminated bot process with PID {pid}")
            else:
                logger.warning(f"Failed to terminate bot process with PID {pid}")
    else:
        logger.info("No bot processes found running")
    
    # Clear any Telegram API sessions
    logger.info("Attempting to clear Telegram API sessions...")
    await clear_telegram_sessions()
    
    # Create a new lock file
    create_lock_file()
    
    logger.info("Done. It's now safe to start a new bot instance.")

if __name__ == "__main__":
    asyncio.run(main()) 
