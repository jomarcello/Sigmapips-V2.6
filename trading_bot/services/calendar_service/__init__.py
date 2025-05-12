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

# Configureer een extra handlertje voor kalender gerelateerde logs
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Detecteer of we in Railway draaien
RUNNING_IN_RAILWAY = os.environ.get("RAILWAY_ENVIRONMENT") is not None
HOSTNAME = socket.gethostname()

logger.info(f"Running on host: {HOSTNAME}")
logger.info(f"Running in Railway: {RUNNING_IN_RAILWAY}")

# BELANGRIJK: Force instellingen voor TradingView calendar
# Expliciet investing.com uitschakelen (investing is verwijderd)
os.environ["USE_INVESTING_CALENDAR"] = "false"
logger.info("⚠️ Investing.com calendar is verwijderd en niet meer beschikbaar")
print("⚠️ Investing.com calendar is verwijderd en niet meer beschikbaar")

# Calendar fallback uitschakelen - we willen echte data
os.environ["USE_CALENDAR_FALLBACK"] = "false"
logger.info("⚠️ Forcing USE_CALENDAR_FALLBACK=false to use real data")
print("⚠️ Forcing USE_CALENDAR_FALLBACK=false to use real data")

# ScrapingAnt uitschakelen en OpenAI o4-mini inschakelen
os.environ["USE_SCRAPINGANT"] = "false"
os.environ["USE_OPENAI_O4MINI"] = "true"
logger.info("⚠️ Disabling ScrapingAnt and enabling OpenAI o4-mini for economic calendar data")
print("⚠️ Disabling ScrapingAnt and enabling OpenAI o4-mini for economic calendar data")

# Force the use of TradingView calendar service
os.environ["USE_TRADINGVIEW_CALENDAR"] = "true"
logger.info("⚠️ Forcing USE_TRADINGVIEW_CALENDAR=true to use TradingView economic calendar")
print("⚠️ Forcing USE_TRADINGVIEW_CALENDAR=true to use TradingView economic calendar")

# Disable BrowserBase services
os.environ["BROWSERBASE_API_KEY"] = ""
os.environ["BROWSERBASE_PROJECT_ID"] = ""
logger.info("⚠️ Disabling BrowserBase services to ensure TradingView is used")
print("⚠️ Disabling BrowserBase services to ensure TradingView is used")

# Controleer of OpenAI API key is ingesteld
if os.environ.get("OPENAI_API_KEY") is None:
    logger.warning("⚠️ OPENAI_API_KEY is not set, some features may not work correctly")
    print("⚠️ OPENAI_API_KEY is not set, some features may not work correctly")
else:
    logger.info("✅ OPENAI_API_KEY is set and will be used for o4-mini integration")
    print("✅ OPENAI_API_KEY is set and will be used for o4-mini integration")

# Check of er iets expliciets in de omgeving is ingesteld voor fallback
USE_FALLBACK = False  # We willen de echte implementatie gebruiken, niet de fallback

# Ingebouwde fallback EconomicCalendarService voor het geval de echte niet werkt
class InternalFallbackCalendarService:
    """Interne fallback implementatie van EconomicCalendarService"""
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.logger.warning("Internal fallback EconomicCalendarService is being used!")
        print("⚠️ INTERNAL FALLBACK CALENDAR SERVICE IS ACTIVE ⚠️")
        
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

# Log duidelijk naar de console of we fallback gebruiken of niet
if USE_FALLBACK:
    logger.info("⚠️ USE_CALENDAR_FALLBACK is set to True, using fallback implementation")
    print("⚠️ Calendar fallback mode is ENABLED via environment variable")
    print(f"⚠️ Check environment value: '{os.environ.get('USE_CALENDAR_FALLBACK', '')}'")
    # Gebruik interne fallback
    EconomicCalendarService = InternalFallbackCalendarService
    logger.info("Successfully initialized internal fallback EconomicCalendarService")
else:
    # Probeer eerst de volledige implementatie
    logger.info("✅ USE_CALENDAR_FALLBACK is set to False, will use real implementation")
    print("✅ Calendar fallback mode is DISABLED")
    print(f"✅ Environment value: '{os.environ.get('USE_CALENDAR_FALLBACK', '')}'")
    
    try:
        logger.info("Attempting to import EconomicCalendarService from calendar.py...")
        from trading_bot.services.calendar_service.calendar import EconomicCalendarService
        logger.info("Successfully imported EconomicCalendarService from calendar.py")
        
        # Test importeren van TradingView kalender
        try:
            from trading_bot.services.calendar_service.tradingview_calendar import TradingViewCalendarService
            logger.info("Successfully imported TradingViewCalendarService")
            
            # Check if using OpenAI o4-mini
            use_o4mini = os.environ.get("USE_OPENAI_O4MINI", "").lower() in ("true", "1", "yes")
            logger.info(f"Using OpenAI o4-mini for calendar data: {use_o4mini}")
            
            if use_o4mini:
                print("✅ Using OpenAI o4-mini for economic calendar data")
            else:
                print("⚠️ OpenAI o4-mini is disabled, using direct connection")
            
        except Exception as e:
            logger.warning(f"TradingViewCalendarService import failed: {e}")
            logger.debug(traceback.format_exc())
            print("⚠️ TradingView calendar service could not be imported")

    except Exception as e:
        # Als de import faalt, gebruiken we onze interne fallback implementatie
        logger.error(f"Could not import EconomicCalendarService from calendar.py: {str(e)}")
        logger.debug(traceback.format_exc())
        logger.warning("Using internal fallback implementation")
        print("⚠️ Could not import real calendar service, using internal fallback")
        
        # Gebruik interne fallback
        EconomicCalendarService = InternalFallbackCalendarService
        
        # Log dat we de fallback gebruiken
        logger.info("Successfully initialized internal fallback EconomicCalendarService")

# Exporteer TradingView debug functie als die beschikbaar is
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
    # Als de import faalt, exporteren we alleen de EconomicCalendarService
    __all__ = ['EconomicCalendarService']
