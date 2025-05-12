#!/bin/bash
# Script to start the trading bot with OpenAI o4-mini for economic calendar data

# Set environment variables
export USE_SCRAPINGANT="false"
export USE_OPENAI_O4MINI="true"
export USE_TRADINGVIEW_CALENDAR="true"
export USE_CALENDAR_FALLBACK="false"

# Disable BrowserBase to ensure TradingView is used
export BROWSERBASE_API_KEY=""
export BROWSERBASE_PROJECT_ID=""

echo "✅ Setting environment variables for OpenAI o4-mini economic calendar"
echo "✅ USE_SCRAPINGANT=$USE_SCRAPINGANT"
echo "✅ USE_OPENAI_O4MINI=$USE_OPENAI_O4MINI"
echo "✅ USE_TRADINGVIEW_CALENDAR=$USE_TRADINGVIEW_CALENDAR"
echo "✅ USE_CALENDAR_FALLBACK=$USE_CALENDAR_FALLBACK"

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️ OPENAI_API_KEY is not set. Please set it with:"
    echo "export OPENAI_API_KEY=your_api_key"
    exit 1
else
    echo "✅ OPENAI_API_KEY is set"
fi

# Start the bot
echo "Starting trading bot with OpenAI o4-mini for economic calendar..."
python -m trading_bot.main 