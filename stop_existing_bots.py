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
BOT_TOKEN = os.environ.get('BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN') or '7328581013:AAGDFJyvipmQsV5UQLjUeLQmX2CWIU2VMjk'

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
            
            # If webhook is set, delete it
            webhook_data = response.json()
            if webhook_data.get('result', {}).get('url'):
                logger.info(f"Found webhook URL: {webhook_data['result']['url']}, deleting...")
                delete_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook?drop_pending_updates=true"
                delete_response = await client.post(delete_url)
                logger.info(f"Delete webhook response: {delete_response.status_code}")
        
        # Then send a dummy getUpdates request with minimal timeout to clear any sessions
        logger.info("Sending dummy getUpdates request to clear sessions...")
        updates_url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        async with httpx.AsyncClient() as client:
            # First try to clear with offset=-1
            params = {'timeout': 1, 'offset': -1, 'limit': 1}
            response = await client.post(updates_url, params=params)
            logger.info(f"Dummy getUpdates request completed: {response.status_code}")
            
            # Then try with explicit drop_pending_updates
            params = {'timeout': 1, 'offset': -1, 'limit': 1, 'drop_pending_updates': True}
            response = await client.post(updates_url, params=params)
            logger.info(f"Dummy getUpdates with drop_pending_updates completed: {response.status_code}")
        
        # Wait a moment to ensure sessions are cleared
        await asyncio.sleep(2)
        
        return True
    except Exception as e:
        logger.error(f"Error clearing Telegram sessions: {str(e)}")
        return False

def kill_process(pid, force=False):
    """Kill a process by PID"""
    try:
        if force:
            os.kill(pid, signal.SIGKILL)
            logger.info(f"Force killed process {pid}")
            return True
        
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
        # Check if the process is still running
        if psutil.pid_exists(pid):
            # If still running, force kill
            os.kill(pid, signal.SIGKILL)
            logger.info(f"Process {pid} did not terminate with SIGTERM, sent SIGKILL")
        return True
    except ProcessLookupError:
        logger.info(f"Process {pid} not found")
        return False
    except Exception as e:
        logger.error(f"Error killing process {pid}: {str(e)}")
        return False

def find_bot_processes():
    """Find all running Python processes that might be running our bot"""
    bot_processes = []
    
    # More aggressive search for bot processes
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'username']):
        try:
            # Look for Python processes
            if proc.info['name'] and ('python' in proc.info['name'].lower() or 'python3' in proc.info['name'].lower()):
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    # Check for various indicators of our bot
                    if any(keyword in cmdline for keyword in ['trading_bot', 'main.py', 'telegram', 'bot', 'sigmapips']):
                        # Don't include our own PID
                        if proc.info['pid'] != os.getpid():
                            logger.info(f"Found potential bot process: {proc.info['pid']} with command: {cmdline[:100]}...")
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
        if kill_process(locked_pid, force=True):
            logger.info(f"Successfully terminated bot process with PID {locked_pid}")
        else:
            logger.warning(f"Failed to terminate bot process with PID {locked_pid}")
    
    # Find and kill any bot processes
    bot_processes = find_bot_processes()
    if bot_processes:
        logger.info(f"Found {len(bot_processes)} bot processes: {bot_processes}")
        for pid in bot_processes:
            if kill_process(pid, force=True):
                logger.info(f"Successfully terminated bot process with PID {pid}")
            else:
                logger.warning(f"Failed to terminate bot process with PID {pid}")
    else:
        logger.info("No bot processes found running")
    
    # Clear any Telegram API sessions
    logger.info("Attempting to clear Telegram API sessions...")
    await clear_telegram_sessions()
    
    # Wait a bit to ensure everything is cleared
    logger.info("Waiting for 5 seconds to ensure all processes are terminated...")
    await asyncio.sleep(5)
    
    # Create a new lock file
    create_lock_file()
    
    logger.info("Done. It's now safe to start a new bot instance.")

if __name__ == "__main__":
    asyncio.run(main()) 
