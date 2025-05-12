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

# IMPORTANT: Force settings for ForexFactory calendar
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
logger.info("✅ Using only ForexFactory calendar (no ScrapingAnt or OpenAI)")

# Force the use of ForexFactory calendar service only
os.environ["USE_TRADINGVIEW_CALENDAR"] = "false"
os.environ["USE_FOREXFACTORY_CALENDAR"] = "true"
logger.info("✅ Using only ForexFactory economic calendar (TradingView disabled)")

# Disable BrowserBase services
os.environ["BROWSERBASE_API_KEY"] = ""
os.environ["BROWSERBASE_PROJECT_ID"] = ""
logger.info("✅ BrowserBase services disabled")

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
        
        async def get_calendar(self, *args, **kwargs):
            self.logger.error("Placeholder get_calendar called")
            return []
        
        async def get_economic_calendar(self, *args, **kwargs):
            self.logger.error("Placeholder get_economic_calendar called")
            return "Economic calendar service is not available."

# Define impact emoji mapping for use in formatting functions
IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
    "Medium-Low": "🟡",
    "Low": "🟢"
}

# Export only the EconomicCalendarService
__all__ = ['EconomicCalendarService', 'IMPACT_EMOJI']
