#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def main():
    try:
        # Import the calendar service directly
        logger.info("Importing TradingViewCalendarService...")
        from trading_bot.services.calendar_service.tradingview_calendar import TradingViewCalendarService
        
        # Create an instance of the calendar service
        logger.info("Creating TradingViewCalendarService instance...")
        calendar_service = TradingViewCalendarService()
        
        # Log environment variables
        logger.info("Environment variables:")
        logger.info(f"USE_SCRAPINGANT: {os.environ.get('USE_SCRAPINGANT', 'not set')}")
        logger.info(f"SCRAPINGANT_API_KEY: {'set' if os.environ.get('SCRAPINGANT_API_KEY') else 'not set'}")
        logger.info(f"RAILWAY_ENVIRONMENT: {os.environ.get('RAILWAY_ENVIRONMENT', 'not set')}")
        
        # Get calendar data
        logger.info("Fetching calendar data...")
        events = await calendar_service.get_calendar(days_ahead=0, min_impact="Low")
        
        # Print results
        logger.info(f"Retrieved {len(events)} events")
        
        if events:
            logger.info("Sample events:")
            for i, event in enumerate(events[:3]):  # Show first 3 events
                logger.info(f"Event {i+1}: {event}")
        else:
            logger.info("No events retrieved")
        
        # Format the calendar for Telegram
        logger.info("Formatting calendar for Telegram...")
        from trading_bot.services.calendar_service.tradingview_calendar import format_calendar_for_telegram
        formatted_calendar = await format_calendar_for_telegram(events)
        logger.info(f"Formatted calendar length: {len(formatted_calendar)} characters")
        logger.info(f"First 200 characters of formatted calendar: {formatted_calendar[:200]}...")
        
        # Run a debug check on the API connection
        logger.info("Running API connection debug...")
        debug_info = await calendar_service.debug_api_connection()
        logger.info(f"API health: {debug_info.get('api_health')}")
        logger.info(f"Events retrieved: {debug_info.get('events_retrieved')}")
        
        logger.info("Debug complete")
        
    except Exception as e:
        logger.error(f"Error in debug script: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main()) 