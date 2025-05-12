#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import signal
import requests
import argparse

# Bot token
BOT_TOKEN = "7328581013:AAGDFJyvipmQsV5UQLjUeLQmX2CWIU2VMjk"

def print_header(message):
    """Print a formatted header message"""
    print("\n" + "=" * 80)
    print(f"  {message}")
    print("=" * 80)

def delete_webhook():
    """Delete the Telegram webhook to ensure polling mode works"""
    print("Deleting Telegram webhook...")
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

def get_bot_script():
    """Find the main bot script"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Check for potential bot scripts
    candidates = [
        os.path.join(current_dir, "bot.py"),
        os.path.join(current_dir, "main.py"),
        os.path.join(current_dir, "run.py"),
        os.path.join(current_dir, "app.py"),
    ]
    
    # Check if any of the candidates exist
    for script in candidates:
        if os.path.exists(script):
            return script
    
    # If no candidate found, look for files containing "bot" in the name
    for file in os.listdir(current_dir):
        if file.endswith('.py') and 'bot' in file.lower():
            return os.path.join(current_dir, file)
    
    # If still not found, search in trading_bot directory
    trading_bot_dir = os.path.join(current_dir, 'trading_bot')
    if os.path.exists(trading_bot_dir):
        for file in os.listdir(trading_bot_dir):
            if file.endswith('.py') and ('bot' in file.lower() or 'main' in file.lower()):
                return os.path.join(trading_bot_dir, file)
    
    # Return None if no bot script found
    return None

def fix_calendar_script():
    """Make sure the calendar script is ready to run"""
    calendar_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "get_today_events.py")
    
    if not os.path.exists(calendar_script):
        print("Calendar script not found, skipping calendar fix")
        return
    
    print("Fixing calendar script permissions...")
    try:
        # Make sure it's executable
        subprocess.run(["chmod", "+x", calendar_script])
        print("✅ Calendar script permissions fixed")
    except Exception as e:
        print(f"❌ Error fixing calendar script: {str(e)}")

def start_bot(bot_script, debug=False, test_mode=False):
    """Start the bot with proper environment setup"""
    if not bot_script:
        print("❌ No bot script found. Please specify the path to the bot script.")
        return
    
    print_header(f"STARTING BOT: {os.path.basename(bot_script)}")
    
    # Set up environment variables
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"  # Ensure output is not buffered
    
    if debug:
        env["DEBUG"] = "1"
        env["LOG_LEVEL"] = "DEBUG"
    
    if test_mode:
        env["TEST_MODE"] = "1"
    
    # Prepare command
    cmd = [sys.executable, bot_script]
    
    print(f"Starting bot with command: {' '.join(cmd)}")
    print("Press Ctrl+C to stop the bot")
    
    try:
        # Start the bot process
        bot_process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1  # Line buffered
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
                print(f"Bot process exited with code {bot_process.returncode}")
                break
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received, stopping bot...")
        try:
            bot_process.send_signal(signal.SIGTERM)
            bot_process.wait(timeout=5)
            print("Bot stopped gracefully")
        except subprocess.TimeoutExpired:
            print("Bot didn't stop gracefully, force killing...")
            bot_process.kill()
    except Exception as e:
        print(f"Error running bot: {str(e)}")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Start the Telegram bot with clean environment')
    parser.add_argument('--script', help='Path to the bot script')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--test', action='store_true', help='Enable test mode')
    args = parser.parse_args()
    
    # Find the bot script
    bot_script = args.script if args.script else get_bot_script()
    
    # Clean environment before starting
    delete_webhook()
    fix_calendar_script()
    
    # Start the bot
    if bot_script:
        start_bot(bot_script, debug=args.debug, test_mode=args.test)
    else:
        print("❌ Bot script not found. Please specify the path to the bot script using --script option.")

if __name__ == "__main__":
    main() 