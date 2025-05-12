#!/bin/bash

echo "Starting bot deployment process..."

# Wait a moment to ensure any previous deployment has completed its shutdown
sleep 5

# Check for existing Python processes running the trading bot
echo "Checking for existing bot processes..."
BOT_PIDS=$(pgrep -f "python.*trading_bot.main")

if [ ! -z "$BOT_PIDS" ]; then
    echo "Found existing bot processes: $BOT_PIDS"
    echo "Terminating existing processes..."
    
    # First try graceful termination
    kill $BOT_PIDS 2>/dev/null
    
    # Wait a moment for processes to terminate
    sleep 2
    
    # Check if processes are still running
    REMAINING_PIDS=$(pgrep -f "python.*trading_bot.main")
    if [ ! -z "$REMAINING_PIDS" ]; then
        echo "Forcing termination of remaining processes: $REMAINING_PIDS"
        kill -9 $REMAINING_PIDS 2>/dev/null
    fi
else
    echo "No existing bot processes found."
fi

# Start the bot with proper environment
echo "Starting new bot instance..."
exec python -m trading_bot.main 