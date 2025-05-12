#!/usr/bin/env python3
import os
import sys
import time
import signal
import requests
import subprocess
import argparse
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = "7328581013:AAGDFJyvipmQsV5UQLjUeLQmX2CWIU2VMjk"

def print_header(message):
    """Print a formatted header message"""
    logger.info("\n" + "=" * 80)
    logger.info(f"  {message}")
    logger.info("=" * 80)

def kill_all_bot_processes():
    """Kill all python processes that might be running the bot"""
    print_header("Killing all bot processes")
    
    # Get our own PID to avoid killing this script
    our_pid = os.getpid()
    logger.info(f"Our PID: {our_pid} (will not be killed)")
    
    try:
        # Find all Python processes
        cmd = "ps aux | grep python | grep -v grep"
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
        
        if not result.stdout.strip():
            logger.info("No Python processes found")
            return
        
        # Look for bot-related processes
        bot_processes = []
        for line in result.stdout.splitlines():
            if (
                ("bot.py" in line or 
                "main.py" in line or 
                "trading_bot" in line or 
                "start_bot" in line or
                "telegram" in line) and 
                "grep" not in line
            ):
                parts = line.split()
                if len(parts) > 1:
                    pid = int(parts[1])
                    # Don't kill ourselves
                    if pid != our_pid and not str(line).endswith(f"start_with_cleanup.py --script={bot_script}"):
                        bot_processes.append(pid)
        
        # Kill each process
        if bot_processes:
            logger.info(f"Found {len(bot_processes)} bot processes to kill")
            for pid in bot_processes:
                try:
                    logger.info(f"Killing process {pid}")
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.5)  # Give it time to terminate
                except Exception as e:
                    logger.error(f"Error killing process {pid}: {str(e)}")
                    try:
                        # Try harder
                        os.kill(pid, signal.SIGKILL)
                    except:
                        pass
            
            # Verify all are gone
            time.sleep(1)
            check_cmd = "ps aux | grep python | grep -v grep"
            check_result = subprocess.run(check_cmd, shell=True, text=True, capture_output=True)
            remaining = []
            for line in check_result.stdout.splitlines():
                for pid in bot_processes:
                    if str(pid) in line:
                        remaining.append(pid)
            
            if remaining:
                logger.warning(f"{len(remaining)} processes still running: {remaining}")
                # Force kill them
                for pid in remaining:
                    try:
                        if pid != our_pid:  # Double-check not to kill ourselves
                            os.kill(pid, signal.SIGKILL)
                            logger.info(f"Force killed process {pid}")
                    except:
                        pass
            else:
                logger.info("All bot processes successfully terminated")
        else:
            logger.info("No bot processes found to kill")
    
    except Exception as e:
        logger.error(f"Error killing bot processes: {str(e)}")

def delete_webhook():
    """Delete any active webhook for the bot"""
    print_header("Deleting Telegram webhook")
    
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    
    try:
        response = requests.post(api_url)
        result = response.json()
        
        if result.get('ok', False):
            logger.info("✅ Webhook successfully deleted")
        else:
            logger.error(f"❌ Failed to delete webhook: {result.get('description', 'Unknown error')}")
    except Exception as e:
        logger.error(f"❌ Error deleting webhook: {str(e)}")

def get_webhook_info():
    """Get information about any configured webhook"""
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    
    try:
        response = requests.get(api_url)
        result = response.json()
        
        if result.get('ok', False):
            webhook_url = result.get('result', {}).get('url', '')
            if webhook_url:
                logger.info(f"Webhook is configured: {webhook_url}")
                return webhook_url
            else:
                logger.info("No webhook is configured")
                return None
        else:
            logger.error(f"Error getting webhook info: {result.get('description', 'Unknown error')}")
            return None
    except Exception as e:
        logger.error(f"Error checking webhook: {str(e)}")
        return None

def check_railway_status():
    """Check if the bot is running on Railway"""
    print_header("Checking for Railway deployment")
    
    railway_env = os.environ.get("RAILWAY_ENVIRONMENT", "")
    railway_service = os.environ.get("RAILWAY_SERVICE_NAME", "")
    railway_id = os.environ.get("RAILWAY_SERVICE_ID", "")
    
    if railway_env or railway_service or railway_id:
        logger.info(f"Bot appears to be running on Railway: {railway_env} / {railway_service}")
        return True
    
    # Check if we can connect to Railway
    webhook_url = get_webhook_info()
    if webhook_url and "railway.app" in webhook_url:
        logger.info(f"Bot appears to be deployed on Railway at {webhook_url}")
        return True
    
    logger.info("No Railway deployment detected")
    return False

def check_and_clear_railway():
    """Recommend steps to clear Railway instance if needed"""
    is_railway = check_railway_status()
    
    if is_railway:
        print_header("RAILWAY DEPLOYMENT DETECTED")
        logger.warning("You appear to have a Railway deployment using this bot token.")
        logger.warning("To fix the conflict:")
        logger.warning("1. Log in to Railway")
        logger.warning("2. Stop the service or set TELEGRAM_BOT_TOKEN to a different value")
        logger.warning("3. Or, use a different bot token locally")
        
        # Ask user what to do
        logger.info("\nOptions:")
        logger.info("1. Continue anyway (might have conflicts)")
        logger.info("2. Exit and fix Railway first")
        
        choice = input("Enter choice (1 or 2): ")
        if choice == "2":
            logger.info("Exiting. Please fix Railway deployment first.")
            sys.exit(0)
    
    # If we're continuing, force delete webhook
    delete_webhook()

def fix_calendar_script():
    """Make sure the calendar script works properly"""
    print_header("Fixing ForexFactory calendar script")
    
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "get_today_events.py")
    
    if not os.path.exists(script_path):
        logger.warning(f"Calendar script not found at {script_path}")
        return
    
    logger.info(f"Making calendar script executable: {script_path}")
    try:
        subprocess.run(["chmod", "+x", script_path])
        
        # Check if it has the right shebang
        with open(script_path, 'r') as f:
            content = f.read()
        
        if not content.startswith("#!/usr/bin/env python"):
            logger.info("Adding proper shebang line")
            with open(script_path, 'w') as f:
                f.write("#!/usr/bin/env python3\n" + content)
        
        logger.info("✅ Calendar script fixed and ready to use")
    except Exception as e:
        logger.error(f"Error fixing calendar script: {str(e)}")

def start_bot(bot_script, debug=False, force_polling=True):
    """Start the bot with proper environment setup"""
    print_header(f"STARTING BOT: {os.path.basename(bot_script)}")
    
    # Set up environment variables
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    if debug:
        env["DEBUG"] = "1"
        env["LOG_LEVEL"] = "DEBUG"
    
    if force_polling:
        # Environment variables to force polling mode
        env["TELEGRAM_WEBHOOK_ACTIVE"] = "0"
        env["FORCE_POLLING"] = "1"
        env["USE_POLLING"] = "1"
    
    # Prepare command
    cmd = [sys.executable, bot_script]
    
    logger.info(f"Starting bot with command: {' '.join(cmd)}")
    logger.info("Press Ctrl+C to stop the bot")
    
    try:
        # Start the bot process
        bot_process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Read and print output
        while True:
            output_line = bot_process.stdout.readline()
            if output_line == '' and bot_process.poll() is not None:
                break
            if output_line:
                print(output_line.strip())
            
            # Check if process is still running
            if bot_process.poll() is not None:
                logger.info(f"Bot process exited with code {bot_process.returncode}")
                break
    except KeyboardInterrupt:
        logger.info("\nKeyboard interrupt received, stopping bot...")
        try:
            bot_process.send_signal(signal.SIGTERM)
            bot_process.wait(timeout=5)
            logger.info("Bot stopped gracefully")
        except subprocess.TimeoutExpired:
            logger.info("Bot didn't stop gracefully, force killing...")
            bot_process.kill()
    except Exception as e:
        logger.error(f"Error running bot: {str(e)}")

def find_bot_script():
    """Find the main bot script"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check for common bot script names
    candidates = [
        os.path.join(current_dir, "bot.py"),
        os.path.join(current_dir, "main.py"),
        os.path.join(current_dir, "trading_bot", "main.py"),
        os.path.join(current_dir, "trading_bot", "bot.py"),
    ]
    
    # Check if any candidate exists
    for script in candidates:
        if os.path.exists(script):
            return script
    
    # If no standard names, look for files with bot in the name
    for file in os.listdir(current_dir):
        if file.endswith('.py') and ('bot' in file.lower() or 'main' in file.lower()):
            return os.path.join(current_dir, file)
    
    # If nothing found in root, check trading_bot dir
    trading_bot_dir = os.path.join(current_dir, 'trading_bot')
    if os.path.exists(trading_bot_dir):
        for file in os.listdir(trading_bot_dir):
            if file.endswith('.py') and ('bot' in file.lower() or 'main' in file.lower()):
                return os.path.join(trading_bot_dir, file)
    
    # Still nothing? Return None
    return None

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Start the Telegram bot with clean environment')
    parser.add_argument('--script', help='Path to the bot script')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--skip-railway-check', action='store_true', help='Skip Railway deployment check')
    parser.add_argument('--skip-kill', action='store_true', help='Skip killing existing processes')
    args = parser.parse_args()
    
    # Find bot script
    global bot_script  # Make it accessible in kill_all_bot_processes
    bot_script = args.script if args.script else find_bot_script()
    
    if not bot_script:
        logger.error("No bot script found. Please specify the path using --script.")
        sys.exit(1)
    
    logger.info(f"Found bot script: {bot_script}")
    
    # Kill existing processes
    if not args.skip_kill:
        kill_all_bot_processes()
    
    # Fix calendar script
    fix_calendar_script()
    
    # Check Railway status
    if not args.skip_railway_check:
        check_and_clear_railway()
    
    # Start the bot
    start_bot(bot_script, debug=args.debug, force_polling=True)

if __name__ == "__main__":
    main() 