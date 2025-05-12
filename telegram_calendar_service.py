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

# Import the required modules
try:
    import economic_calendar
    import tradingview_o4mini
    logger.info("Successfully imported economic_calendar and tradingview_o4mini modules")
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Make sure economic_calendar.py and tradingview_o4mini.py are in the same directory.")
    sys.exit(1)

class TelegramCalendarService:
    """Service to send economic calendar updates to Telegram"""
    
    def __init__(self, bot_token=None, chat_id=None, debug=False, test_mode=False):
        """Initialize the service
        
        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID
            debug: Enable debug mode
            test_mode: Run in test mode without sending to Telegram
        """
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        self.debug = debug
        self.test_mode = test_mode
        self.calendar_service = None
        
        if debug:
            logger.setLevel(logging.DEBUG)
            os.environ["DEBUG"] = "1"
            logger.debug("Debug mode enabled")
        
        if test_mode:
            logger.info("Running in TEST MODE - will not send to Telegram")
        else:
            if not self.bot_token:
                logger.error("No Telegram bot token provided")
                raise ValueError("Telegram bot token is required")
            
            if not self.chat_id:
                logger.error("No Telegram chat ID provided")
                raise ValueError("Telegram chat ID is required")
        
        logger.info("TelegramCalendarService initialized")
    
    async def _ensure_calendar_service(self):
        """Ensure we have an initialized calendar service"""
        if self.calendar_service is None:
            logger.info("Initializing TradingViewO4MiniCalendarService")
            self.calendar_service = tradingview_o4mini.TradingViewO4MiniCalendarService()
    
    async def send_calendar(self, days_ahead=0, all_currencies=False):
        """Send economic calendar to Telegram
        
        Args:
            days_ahead: Number of days ahead to fetch events (0=today, 1=tomorrow, etc.)
            all_currencies: Whether to include all currencies or only major ones
        """
        logger.info(f"Fetching economic calendar (days_ahead={days_ahead}, all_currencies={all_currencies})")
        
        # Initialize calendar service if needed
        await self._ensure_calendar_service()
        
        # Get events using TradingViewO4MiniCalendarService
        events = await self.calendar_service.get_calendar(
            days_ahead=days_ahead,
            min_impact="Low",
            all_currencies=all_currencies
        )
        
        if self.debug:
            logger.debug(f"Retrieved {len(events)} events")
            if events and len(events) > 0:
                logger.debug(f"First event: {events[0]}")
        
        # Format events for Telegram
        telegram_output = await self.calendar_service.format_calendar_for_display(
            events, 
            group_by_currency=True
        )
        
        # Format events for console
        console_output = await self.calendar_service.format_calendar_for_display(
            events, 
            group_by_currency=False
        )
        
        if self.test_mode:
            logger.info("TEST MODE: Displaying output instead of sending to Telegram")
            print("\n" + "-" * 80)
            print("CONSOLE OUTPUT:")
            print(console_output)
            print("\n" + "-" * 80)
            print("TELEGRAM OUTPUT (HTML):")
            print(telegram_output)
            print("-" * 80)
            return True
        
        if self.debug:
            logger.debug(f"Telegram output preview: {telegram_output[:200]}...")
        
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
    
    async def close(self):
        """Close the calendar service"""
        if self.calendar_service:
            await self.calendar_service._close_session()
            logger.info("Closed calendar service session")

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Send economic calendar updates to Telegram")
    parser.add_argument("--bot-token", type=str, help="Telegram bot token")
    parser.add_argument("--chat-id", type=str, help="Telegram chat ID")
    parser.add_argument("--days", type=int, default=0, help="Number of days ahead (0=today, 1=tomorrow, etc.)")
    parser.add_argument("--all-currencies", action="store_true", help="Include all currencies (default: only major currencies)")
    parser.add_argument("--daily", action="store_true", help="Send daily update (today's calendar in the morning, tomorrow's in the evening)")
    parser.add_argument("--weekly", action="store_true", help="Send weekly update (next 5 days)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with verbose output")
    parser.add_argument("--test", action="store_true", help="Test mode - don't send to Telegram, just show output")
    args = parser.parse_args()
    
    try:
        service = TelegramCalendarService(args.bot_token, args.chat_id, args.debug, args.test)
        
        if args.daily:
            await service.send_daily_update()
        elif args.weekly:
            await service.send_weekly_update()
        else:
            await service.send_calendar(days_ahead=args.days, all_currencies=args.all_currencies)
        
        # Close the service
        await service.close()
        logger.info("Done!")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 