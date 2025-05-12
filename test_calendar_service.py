#!/usr/bin/env python3
import asyncio
import logging
import os
from trading_bot.services.calendar_service.calendar import EconomicCalendarService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def test_calendar_service():
    """Test the EconomicCalendarService."""
    logger.info("Initializing EconomicCalendarService")
    service = EconomicCalendarService()
    
    # Print service info
    logger.info(f"Calendar service fallback enabled: {service.use_fallback}")
    
    # Get calendar events
    logger.info("Getting calendar events")
    events = await service.get_calendar(days_ahead=0, min_impact="Low")
    logger.info(f"Retrieved {len(events)} events")
    
    # Print first 5 events
    logger.info("First 5 events:")
    for i, event in enumerate(events[:5]):
        logger.info(f"Event {i+1}: {event}")
    
    # Format calendar
    logger.info("Getting formatted calendar")
    formatted = await service.get_economic_calendar(days_ahead=0, min_impact="Low")
    logger.info(f"Formatted calendar length: {len(formatted)}")
    logger.info(f"Formatted calendar preview: {formatted[:200]}...")
    
    # Test the calendar service with a specific currency
    logger.info("Getting calendar events for USD")
    usd_events = await service.get_calendar(days_ahead=0, min_impact="Low", currency="USD")
    logger.info(f"Retrieved {len(usd_events)} USD events")
    
    # Print first 5 USD events
    logger.info("First 5 USD events:")
    for i, event in enumerate(usd_events[:5]):
        logger.info(f"USD Event {i+1}: {event}")
    
    # Test instrument-specific calendar
    logger.info("Getting instrument calendar for EURUSD")
    eurusd_calendar = await service.get_instrument_calendar("EURUSD", days_ahead=0, min_impact="Low")
    logger.info(f"EURUSD calendar length: {len(eurusd_calendar)}")
    logger.info(f"EURUSD calendar preview: {eurusd_calendar[:200]}...")

if __name__ == "__main__":
    asyncio.run(test_calendar_service()) 