#!/usr/bin/env python3
import asyncio
import logging
import os
from trading_bot.services.calendar_service.tradingview_calendar import TradingViewCalendarService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def test_tradingview_calendar():
    """Test the TradingView calendar service with our fixes."""
    logger.info("Initializing TradingViewCalendarService")
    service = TradingViewCalendarService()
    
    # Test API health
    logger.info("Testing API health")
    is_healthy = await service._check_api_health()
    logger.info(f"API health check result: {is_healthy}")
    
    # Get calendar data
    logger.info("Getting calendar data")
    events = await service.get_calendar(days_ahead=0, min_impact="Low")
    logger.info(f"Retrieved {len(events)} events")
    
    # Print first 5 events
    logger.info("First 5 events:")
    for i, event in enumerate(events[:5]):
        logger.info(f"Event {i+1}: {event}")
    
    # Close the session
    await service._close_session()

if __name__ == "__main__":
    asyncio.run(test_tradingview_calendar()) 