#!/usr/bin/env python3
"""
Script to send an economic calendar update to Telegram using the simplified calendar service.
This script uses the direct TradingView API without fallback.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Try to import the calendar service
try:
    from trading_bot.services.calendar_service.calendar import EconomicCalendarService
    logger.info("Successfully imported EconomicCalendarService")
except ImportError:
    logger.error("Failed to import EconomicCalendarService. Make sure you're in the correct directory.")
    sys.exit(1)

# Try to import Telegram components
try:
    from telegram import Bot
    from telegram.constants import ParseMode
    logger.info("Successfully imported Telegram components")
except ImportError:
    logger.error("Failed to import Telegram components. Make sure python-telegram-bot is installed.")
    sys.exit(1)

async def send_calendar_to_telegram(bot_token, chat_id, days_ahead=0, min_impact="Low", currencies=None):
    """Send economic calendar to Telegram"""
    if not bot_token or not chat_id:
        logger.error("Bot token and chat ID are required")
        return False
        
    try:
        # Initialize the bot
        bot = Bot(token=bot_token)
        
        # Initialize the calendar service
        logger.info("Initializing calendar service...")
        calendar_service = EconomicCalendarService()
        
        # Get formatted calendar
        logger.info(f"Getting economic calendar (days_ahead={days_ahead}, min_impact={min_impact}, currencies={currencies})")
        formatted_calendar = await calendar_service.get_economic_calendar(
            currencies=currencies or ["USD", "EUR", "GBP", "JPY"],
            days_ahead=days_ahead,
            min_impact=min_impact
        )
        
        # Send message to Telegram
        logger.info(f"Sending calendar to chat ID: {chat_id}")
        await bot.send_message(
            chat_id=chat_id,
            text=formatted_calendar,
            parse_mode=ParseMode.HTML
        )
        
        logger.info("Calendar sent successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error sending calendar to Telegram: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Send economic calendar to Telegram')
    parser.add_argument('--days', type=int, default=0, help='Days ahead (0=today, 1=tomorrow, etc.)')
    parser.add_argument('--impact', type=str, default="Low", choices=["Low", "Medium", "High"], 
                        help='Minimum impact level')
    parser.add_argument('--currencies', type=str, default="USD,EUR,GBP,JPY", 
                        help='Comma-separated list of currencies')
    parser.add_argument('--bot-token', type=str, default=os.environ.get("TELEGRAM_BOT_TOKEN"),
                        help='Telegram bot token (or set TELEGRAM_BOT_TOKEN env var)')
    parser.add_argument('--chat-id', type=str, default=os.environ.get("TELEGRAM_CHAT_ID"),
                        help='Telegram chat ID (or set TELEGRAM_CHAT_ID env var)')
    parser.add_argument('--test', action='store_true', help='Test mode - print to console instead of sending')
    
    args = parser.parse_args()
    
    # Disable fallback mode to test direct API
    os.environ["CALENDAR_FALLBACK"] = "false"
    
    # Parse currencies
    currencies = args.currencies.split(",") if args.currencies else None
    
    # Check if we have the required credentials
    if not args.test and (not args.bot_token or not args.chat_id):
        logger.error("Bot token and chat ID are required. Set them as environment variables or use --bot-token and --chat-id")
        sys.exit(1)
    
    if args.test:
        # Test mode - just print the calendar
        logger.info("Running in test mode - will print calendar instead of sending")
        calendar_service = EconomicCalendarService()
        formatted_calendar = await calendar_service.get_economic_calendar(
            currencies=currencies,
            days_ahead=args.days,
            min_impact=args.impact
        )
        print("\n" + "=" * 50)
        print("ECONOMIC CALENDAR")
        print("=" * 50)
        print(formatted_calendar)
        print("=" * 50)
    else:
        # Send to Telegram
        success = await send_calendar_to_telegram(
            args.bot_token,
            args.chat_id,
            days_ahead=args.days,
            min_impact=args.impact,
            currencies=currencies
        )
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main()) 