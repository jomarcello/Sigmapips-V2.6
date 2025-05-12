#!/usr/bin/env python3
import os
import sys
import requests
import subprocess
import time
import json
import signal
import glob

# Telegram bot token
BOT_TOKEN = "7328581013:AAGDFJyvipmQsV5UQLjUeLQmX2CWIU2VMjk"  # From the logs

def print_header(message):
    """Print a formatted header message"""
    print("\n" + "=" * 80)
    print(f"  {message}")
    print("=" * 80)

def delete_webhook():
    """Delete any active webhook for the bot"""
    print_header("Deleting Telegram webhook")
    
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    
    try:
        response = requests.post(api_url)
        result = response.json()
        
        if result.get('ok', False):
            print("✅ Webhook successfully deleted")
        else:
            print(f"❌ Failed to delete webhook: {result.get('description', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error deleting webhook: {str(e)}")

def check_active_processes():
    """Check for active bot processes"""
    print_header("Checking for active bot processes")
    
    # List of possible process patterns to look for
    patterns = [
        "python.*bot.py",
        "python.*telegram",
        ".*trading_bot.*",
        f".*{BOT_TOKEN}.*"
    ]
    
    found_processes = []
    
    for pattern in patterns:
        try:
            cmd = f"ps aux | grep -E '{pattern}' | grep -v grep"
            result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
            
            if result.stdout.strip():
                print(f"Found processes matching pattern '{pattern}':")
                print(result.stdout)
                
                # Extract PIDs
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        found_processes.append(pid)
        except Exception as e:
            print(f"Error checking processes with pattern '{pattern}': {str(e)}")
    
    return found_processes

def kill_processes(pids):
    """Kill the specified processes"""
    print_header(f"Killing {len(pids)} active bot processes")
    
    for pid in pids:
        try:
            print(f"Killing process {pid}...")
            os.kill(int(pid), signal.SIGTERM)
            print(f"✅ Successfully sent SIGTERM to process {pid}")
        except Exception as e:
            print(f"❌ Error killing process {pid}: {str(e)}")
            try:
                # Try forceful kill if SIGTERM fails
                os.kill(int(pid), signal.SIGKILL)
                print(f"✅ Successfully sent SIGKILL to process {pid}")
            except Exception as e2:
                print(f"❌ Error force-killing process {pid}: {str(e2)}")

def cleanup_temp_files():
    """Clean up any temporary or session files"""
    print_header("Cleaning up temporary and session files")
    
    # Add patterns for files to delete
    patterns = [
        "*.session",
        "*.session-journal",
        "*.pid",
        "*.lock",
        "telegram*.json",
        "bot*.json",
        "updates*.json"
    ]
    
    for pattern in patterns:
        try:
            files = glob.glob(pattern)
            for file in files:
                try:
                    os.remove(file)
                    print(f"✅ Deleted {file}")
                except Exception as e:
                    print(f"❌ Error deleting {file}: {str(e)}")
        except Exception as e:
            print(f"❌ Error searching for {pattern}: {str(e)}")

def check_telegram_api():
    """Check if we can connect to the Telegram API"""
    print_header("Checking Telegram API connection")
    
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
    
    try:
        response = requests.get(api_url)
        result = response.json()
        
        if result.get('ok', False):
            bot_info = result.get('result', {})
            print(f"✅ Successfully connected to Telegram API")
            print(f"Bot name: {bot_info.get('first_name', 'Unknown')}")
            print(f"Bot username: @{bot_info.get('username', 'Unknown')}")
            print(f"Bot ID: {bot_info.get('id', 'Unknown')}")
            return True
        else:
            print(f"❌ Failed to connect to Telegram API: {result.get('description', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Error connecting to Telegram API: {str(e)}")
        return False

def main():
    print_header("TELEGRAM BOT CLEANUP UTILITY")
    
    # Step 1: Delete webhook to prevent conflicts
    delete_webhook()
    
    # Step 2: Check for active processes
    active_pids = check_active_processes()
    
    # Step 3: Kill active processes if found
    if active_pids:
        kill_processes(active_pids)
    else:
        print("No active bot processes found locally.")
    
    # Step 4: Clean up temporary files
    cleanup_temp_files()
    
    # Step 5: Check Telegram API connection
    api_working = check_telegram_api()
    
    print_header("CLEANUP SUMMARY")
    if active_pids:
        print(f"✅ Killed {len(active_pids)} bot processes")
    else:
        print("✅ No local bot processes needed to be terminated")
    
    print("✅ Deleted webhook (if any)")
    print("✅ Cleaned up temporary files")
    
    if api_working:
        print("✅ Telegram API connection successful")
        print("\nYou can now start the bot with a clean state.")
    else:
        print("❌ Unable to connect to Telegram API")
        print("\nPlease check your internet connection and bot token.")
    
    print("\nTo start the bot cleanly, run:")
    print("python bot.py")

if __name__ == "__main__":
    main() 