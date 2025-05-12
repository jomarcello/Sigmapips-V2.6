#!/usr/bin/env python3
"""
Test script for the simplified Economic Calendar service
"""

import os
import sys
import logging
import asyncio
import json
from datetime import datetime

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

async def test_calendar_config():
    """Test the simplified calendar service configuration"""
    try:
        # Print environment variables
        logger.info("=== Environment Variables ===")
        env_vars = {
            "CALENDAR_FALLBACK": os.environ.get("CALENDAR_FALLBACK"),
            "DEBUG": os.environ.get("DEBUG"),
        }
        
        for key, value in env_vars.items():
            logger.info(f"{key}: {value or '[not set]'}")
        
        # Initialize the calendar service
        logger.info("=== Initializing Calendar Service ===")
        service = EconomicCalendarService()
        
        # Print service info
        logger.info(f"Using service: TradingView API")
        logger.info(f"Fallback mode: {'Enabled' if service.use_fallback else 'Disabled'}")
        
        # Test getting calendar events
        logger.info("=== Retrieving Calendar Data ===")
        logger.info("Fetching calendar events...")
        events = await service.get_calendar(days_ahead=0, min_impact="Low")
        logger.info(f"Retrieved {len(events)} events")
        
        # Print first 3 events
        if events:
            logger.info("First 3 events:")
            for i, event in enumerate(events[:3]):
                event_info = []
                for key, value in event.items():
                    if key != 'datetime':  # Skip datetime objects for cleaner output
                        event_info.append(f"{key}: {value}")
                logger.info(f"Event {i+1}: {', '.join(event_info)}")
        else:
            logger.warning("No events found. This could be normal if there are no economic events today.")
        
        # Test formatting
        logger.info("=== Formatting Calendar ===")
        formatted = await service.get_economic_calendar(
            currencies=["USD", "EUR", "GBP"],
            days_ahead=0, 
            min_impact="Low"
        )
        logger.info(f"Formatted calendar length: {len(formatted)}")
        if formatted:
            logger.info(f"Formatted calendar preview: {formatted[:200]}...")
        else:
            logger.warning("Formatted calendar is empty")
        
        # Test instrument-specific calendar
        logger.info("=== Testing Instrument Calendar ===")
        instrument = "EURUSD"
        logger.info(f"Getting calendar for {instrument}")
        instrument_calendar = await service.get_instrument_calendar(
            instrument=instrument,
            days_ahead=0,
            min_impact="Low"
        )
        logger.info(f"Instrument calendar length: {len(instrument_calendar)}")
        if instrument_calendar:
            logger.info(f"Instrument calendar preview: {instrument_calendar[:200]}...")
        else:
            logger.warning(f"No calendar events found for {instrument}")
        
        logger.info("✅ Calendar service test completed successfully!")
        return True
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Error testing calendar service: {str(e)}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(test_calendar_config())
    sys.exit(0 if success else 1) 