# This package contains calendar services
# Explicitly export classes for external use

import logging
import traceback
import os
import sys
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)
logger.info("Initializing calendar service module...")

# Configure an additional handler for calendar-related logs
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Detect if we're running in Railway
RUNNING_IN_RAILWAY = os.environ.get("RAILWAY_ENVIRONMENT") is not None
HOSTNAME = socket.gethostname()

logger.info(f"Running on host: {HOSTNAME}")
logger.info(f"Running in Railway: {RUNNING_IN_RAILWAY}")

# IMPORTANT: Force settings for TradingView calendar
# Explicitly disable investing.com (investing has been removed)
os.environ["USE_INVESTING_CALENDAR"] = "false"
logger.info("⚠️ Investing.com calendar is no longer available")

# Calendar fallback only enabled if explicitly requested
use_fallback = os.environ.get("CALENDAR_FALLBACK", "").lower() in ("true", "1", "yes")
os.environ["USE_CALENDAR_FALLBACK"] = "true" if use_fallback else "false"
logger.info(f"Calendar fallback mode is {'enabled' if use_fallback else 'disabled'}")

# Disable all alternative services
os.environ["USE_SCRAPINGANT"] = "false"
os.environ["USE_OPENAI_O4MINI"] = "false"
logger.info("✅ Using only direct TradingView API (no ScrapingAnt or OpenAI)")

# Force the use of TradingView calendar service
os.environ["USE_TRADINGVIEW_CALENDAR"] = "true"
# IMPORTANT: Explicitly disable ForexFactory calendar to prevent errors
os.environ["USE_FOREXFACTORY_CALENDAR"] = "false"
logger.info("✅ Using TradingView economic calendar (ForexFactory disabled)")

# Disable BrowserBase services
os.environ["BROWSERBASE_API_KEY"] = ""
os.environ["BROWSERBASE_PROJECT_ID"] = ""
logger.info("✅ BrowserBase services disabled")

# Import the TradingViewCalendarService first
try:
    from trading_bot.services.calendar_service.tradingview_calendar import TradingViewCalendarService
    logger.info("Successfully imported TradingViewCalendarService")
    HAS_TRADINGVIEW = True
except ImportError as e:
    logger.error(f"Failed to import TradingViewCalendarService: {str(e)}")
    logger.error(traceback.format_exc())
    HAS_TRADINGVIEW = False

# Import the EconomicCalendarService class
try:
    from trading_bot.services.calendar_service.calendar import EconomicCalendarService
    logger.info("Successfully imported EconomicCalendarService")
except ImportError as e:
    logger.error(f"Failed to import EconomicCalendarService: {str(e)}")
    logger.error(traceback.format_exc())
    # Define a placeholder class if import fails
    class EconomicCalendarService:
        def __init__(self):
            self.logger = logging.getLogger(__name__)
            self.logger.error("Using placeholder EconomicCalendarService (import failed)")
            # Initialize TradingView service directly if available
            self.calendar_service = TradingViewCalendarService() if HAS_TRADINGVIEW else None
        
        async def get_calendar(self, *args, **kwargs):
            if self.calendar_service:
                return await self.calendar_service.get_calendar(*args, **kwargs)
            self.logger.error("Placeholder get_calendar called")
            return []
        
        async def get_economic_calendar(self, *args, **kwargs):
            if self.calendar_service:
                return await self.calendar_service.get_economic_calendar(*args, **kwargs)
            self.logger.error("Placeholder get_economic_calendar called")
            return "Economic calendar service is not available."

# Define impact emoji mapping for use in formatting functions
IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
    "Medium-Low": "🟡",
    "Low": "🟢"
}

# Export TradingView debug function if available
if HAS_TRADINGVIEW:
    # Create a global function to run the debug
    async def debug_tradingview_api():
        """Run a debug check on the TradingView API"""
        logger.info("Running TradingView API debug check")
        service = TradingViewCalendarService()
        return await service.debug_api_connection()

    # Add a function to get all calendar events without filtering
    async def get_all_calendar_events():
        """Get all calendar events without filtering"""
        logger.info("Getting all calendar events without filtering")
        service = TradingViewCalendarService()
        events = await service.get_calendar(days_ahead=0, min_impact="Low")
        logger.info(f"Retrieved {len(events)} total events")
        return events

    __all__ = ['EconomicCalendarService', 'TradingViewCalendarService', 'debug_tradingview_api', 'get_all_calendar_events', 'IMPACT_EMOJI']
else:
    # If the import fails, only export the EconomicCalendarService
    logger.error(f"Failed to import TradingViewCalendarService")
    __all__ = ['EconomicCalendarService', 'IMPACT_EMOJI']
