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
logger.info("✅ Using TradingView economic calendar")

# Disable BrowserBase services
os.environ["BROWSERBASE_API_KEY"] = ""
os.environ["BROWSERBASE_PROJECT_ID"] = ""
logger.info("✅ BrowserBase services disabled")

# Built-in fallback EconomicCalendarService in case the real one doesn't work
class InternalFallbackCalendarService:
    """Internal fallback implementation of EconomicCalendarService"""
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.logger.warning("Internal fallback EconomicCalendarService is being used!")
        
    async def get_calendar(self, days_ahead: int = 0, min_impact: str = "Low", currency: str = None) -> List[Dict]:
        """Return empty calendar data"""
        self.logger.info(f"Internal fallback get_calendar called")
        return []
    
    async def get_economic_calendar(self, currencies: List[str] = None, days_ahead: int = 0, min_impact: str = "Low") -> str:
        """Return empty economic calendar message"""
        return "<b>📅 Economic Calendar</b>\n\nNo economic events available (using internal fallback)."
        
    async def get_events_for_instrument(self, instrument: str, *args, **kwargs) -> Dict[str, Any]:
        """Return empty events for an instrument"""
        return {
            "events": [], 
            "explanation": f"No calendar events available (using internal fallback)"
        }
        
    async def get_instrument_calendar(self, instrument: str, *args, **kwargs) -> str:
        """Return empty calendar for an instrument"""
        return "<b>📅 Economic Calendar</b>\n\nNo calendar events available (using internal fallback)."

# Log clearly whether we're using fallback or not
USE_FALLBACK = os.environ.get("USE_CALENDAR_FALLBACK", "").lower() in ("true", "1", "yes")
if USE_FALLBACK:
    logger.info("⚠️ Calendar fallback mode is enabled, using fallback implementation")
    # Use internal fallback
    EconomicCalendarService = InternalFallbackCalendarService
    logger.info("Successfully initialized internal fallback EconomicCalendarService")
else:
    # Try the full implementation first
    logger.info("✅ Calendar fallback mode is disabled, will use real implementation")
    
    try:
        logger.info("Attempting to import EconomicCalendarService from calendar.py...")
        from trading_bot.services.calendar_service.calendar import EconomicCalendarService
        logger.info("Successfully imported EconomicCalendarService from calendar.py")
        
        # Test importing TradingView calendar
        try:
            from trading_bot.services.calendar_service.tradingview_calendar import TradingViewCalendarService
            logger.info("Successfully imported TradingViewCalendarService")
            logger.info("Using direct TradingView API for calendar data")
            
        except Exception as e:
            logger.warning(f"TradingViewCalendarService import failed: {e}")
            logger.debug(traceback.format_exc())
            logger.warning("TradingView calendar service could not be imported")

    except Exception as e:
        # If the import fails, use our internal fallback implementation
        logger.error(f"Could not import EconomicCalendarService from calendar.py: {str(e)}")
        logger.debug(traceback.format_exc())
        logger.warning("Using internal fallback implementation")
        
        # Use internal fallback
        EconomicCalendarService = InternalFallbackCalendarService
        
        # Log that we're using the fallback
        logger.info("Successfully initialized internal fallback EconomicCalendarService")

# Export TradingView debug function if available
try:
    from trading_bot.services.calendar_service.tradingview_calendar import TradingViewCalendarService
    
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

    __all__ = ['EconomicCalendarService', 'debug_tradingview_api', 'get_all_calendar_events']
except Exception:
    # If the import fails, only export the EconomicCalendarService
    __all__ = ['EconomicCalendarService']
