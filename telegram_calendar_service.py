#!/usr/bin/env python3
"""
Telegram Economic Calendar Service

This script provides a service to send economic calendar updates to Telegram
using our standalone economic_calendar.py script.
"""

import os
import sys
import asyncio
import logging
import argparse
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Import the economic_calendar module
try:
    import economic_calendar
    logger.info("Successfully imported economic_calendar module")
except ImportError:
    logger.error("Failed to import economic_calendar module. Make sure it's in the same directory.")
    sys.exit(1)

class TelegramCalendarService:
    """Service to send economic calendar updates to Telegram"""
    
    def __init__(self, bot_token=None, chat_id=None):
        """Initialize the service
        
        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        
        if not self.bot_token:
            logger.error("No Telegram bot token provided")
            raise ValueError("Telegram bot token is required")
        
        if not self.chat_id:
            logger.error("No Telegram chat ID provided")
            raise ValueError("Telegram chat ID is required")
        
        logger.info("TelegramCalendarService initialized")
    
    async def send_calendar(self, days_ahead=0, all_currencies=False):
        """Send economic calendar to Telegram
        
        Args:
            days_ahead: Number of days ahead to fetch events (0=today, 1=tomorrow, etc.)
            all_currencies: Whether to include all currencies or only major ones
        """
        logger.info(f"Sending economic calendar to Telegram (days_ahead={days_ahead}, all_currencies={all_currencies})")
        
        # Get events from economic_calendar
        events = await economic_calendar.get_tradingview_calendar_events(days_ahead=days_ahead)
        
        # Format events for Telegram
        _, telegram_output = economic_calendar.format_events_for_display(events, only_major=not all_currencies)
        
        # Send to Telegram
        success = await economic_calendar.send_to_telegram(
            telegram_output,
            self.bot_token,
            self.chat_id
        )
        
        if success:
            logger.info("Successfully sent economic calendar to Telegram")
        else:
            logger.error("Failed to send economic calendar to Telegram")
        
        return success
    
    async def send_daily_update(self):
        """Send daily economic calendar update
        
        This sends today's calendar in the morning and tomorrow's calendar in the evening.
        """
        current_hour = datetime.now().hour
        
        if current_hour < 12:
            # Morning update - send today's calendar
            logger.info("Sending morning update with today's calendar")
            await self.send_calendar(days_ahead=0)
        else:
            # Evening update - send tomorrow's calendar
            logger.info("Sending evening update with tomorrow's calendar")
            await self.send_calendar(days_ahead=1)
    
    async def send_weekly_update(self):
        """Send weekly economic calendar update
        
        This sends the calendar for the next 5 days.
        """
        logger.info("Sending weekly calendar update")
        
        for days in range(5):
            logger.info(f"Sending calendar for day {days}")
            await self.send_calendar(days_ahead=days)
            # Wait a bit between messages to avoid rate limiting
            await asyncio.sleep(2)

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Send economic calendar updates to Telegram")
    parser.add_argument("--bot-token", type=str, help="Telegram bot token")
    parser.add_argument("--chat-id", type=str, help="Telegram chat ID")
    parser.add_argument("--days", type=int, default=0, help="Number of days ahead (0=today, 1=tomorrow, etc.)")
    parser.add_argument("--all-currencies", action="store_true", help="Include all currencies (default: only major currencies)")
    parser.add_argument("--daily", action="store_true", help="Send daily update (today's calendar in the morning, tomorrow's in the evening)")
    parser.add_argument("--weekly", action="store_true", help="Send weekly update (next 5 days)")
    args = parser.parse_args()
    
    try:
        service = TelegramCalendarService(args.bot_token, args.chat_id)
        
        if args.daily:
            await service.send_daily_update()
        elif args.weekly:
            await service.send_weekly_update()
        else:
            await service.send_calendar(days_ahead=args.days, all_currencies=args.all_currencies)
        
        logger.info("Done!")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 