#!/usr/bin/env python3

import asyncio
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_forexfactory")

# Add current directory to path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

async def main():
    logger.info("Testing ForexFactory calendar service...")
    
    # Try to import the service
    try:
        from trading_bot.services.calendar_service.forexfactory_calendar import ForexFactoryCalendarService
        logger.info("Successfully imported ForexFactoryCalendarService")
        
        # Initialize the service
        service = ForexFactoryCalendarService()
        logger.info("Service initialized successfully")
        
        # Get calendar data
        calendar = await service.get_economic_calendar()
        logger.info(f"Calendar data: {calendar[:200]}...")  # Show first 200 chars
        
        logger.info("Test successful!")
    except Exception as e:
        logger.error(f"Error testing ForexFactory calendar: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
if __name__ == "__main__":
    asyncio.run(main()) 