#!/bin/bash
# Script to send economic calendar to Telegram

# Set your Telegram bot token and chat ID here
# or use environment variables
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-"your_bot_token_here"}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID:-"your_chat_id_here"}

# Default values
DAYS=0
ALL_CURRENCIES=false
DEBUG=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --days=*)
      DAYS="${1#*=}"
      shift
      ;;
    --all-currencies)
      ALL_CURRENCIES=true
      shift
      ;;
    --debug)
      DEBUG=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--days=N] [--all-currencies] [--debug]"
      exit 1
      ;;
  esac
done

# Build command
CMD="python economic_calendar.py --telegram --days=$DAYS"

if [ "$ALL_CURRENCIES" = true ]; then
  CMD="$CMD --all-currencies"
fi

if [ "$DEBUG" = true ]; then
  CMD="$CMD --debug"
fi

# Execute command
echo "Executing: $CMD"
eval $CMD

echo "Done!" 