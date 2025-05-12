# Calendar service package
# This file should be kept minimal to avoid import cycles

import os
import ssl
import asyncio
import logging
import aiohttp
import redis
import json
from typing import Dict, Any, List, Optional
import base64
import time
import re
import random
from datetime import datetime, timedelta
import socket
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    CallbackContext,
    MessageHandler,
    filters,
    PicklePersistence
)
from telegram.constants import ParseMode

from trading_bot.services.database.db import Database
from trading_bot.services.chart_service.chart import ChartService
from trading_bot.services.sentiment_service.sentiment import MarketSentimentService
from trading_bot.services.payment_service.stripe_service import StripeService
from trading_bot.services.payment_service.stripe_config import get_subscription_features

# Import ForexFactory calendar service
try:
    from trading_bot.services.calendar_service.forexfactory_calendar import ForexFactoryCalendarService
    logger.info("Successfully imported ForexFactoryCalendarService")
    HAS_FOREXFACTORY = True
except ImportError:
    logger.error("Failed to import ForexFactoryCalendarService")
    HAS_FOREXFACTORY = False
    ForexFactoryCalendarService = None

# Fallback to TradingView calendar service if ForexFactory is not available
if not HAS_FOREXFACTORY:
    try:
        from trading_bot.services.calendar_service.tradingview_calendar import TradingViewCalendarService
        logger.info("Successfully imported TradingViewCalendarService as fallback")
    except ImportError:
        logger.error("Failed to import TradingViewCalendarService")
        TradingViewCalendarService = None

# Import chronological formatter if available
try:
    from trading_bot.services.calendar_service.chronological_formatter import (
        format_calendar_events_chronologically,
        format_calendar_events_by_currency,
        ChronologicalFormatter
    )
    HAS_CHRONOLOGICAL_FORMATTER = True
    logger.info("Successfully imported chronological calendar formatter")
except ImportError:
    HAS_CHRONOLOGICAL_FORMATTER = False
    logger.warning("Chronological calendar formatter not available")

# Callback data constants
CALLBACK_ANALYSIS_TECHNICAL = "analysis_technical"
CALLBACK_ANALYSIS_SENTIMENT = "analysis_sentiment"
CALLBACK_ANALYSIS_CALENDAR = "analysis_calendar"
# ... rest of constants

# Major currencies for consistent handling
MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]

# Map of instruments to their corresponding currencies
INSTRUMENT_CURRENCY_MAP = {
    # Special case for global view
    "GLOBAL": MAJOR_CURRENCIES,
    
    # Forex
    "EURUSD": ["EUR", "USD"],
    "GBPUSD": ["GBP", "USD"],
    "USDJPY": ["USD", "JPY"],
    "USDCHF": ["USD", "CHF"],
    "AUDUSD": ["AUD", "USD"],
    "NZDUSD": ["NZD", "USD"],
    "USDCAD": ["USD", "CAD"],
    "EURGBP": ["EUR", "GBP"],
    "EURJPY": ["EUR", "JPY"],
    "GBPJPY": ["GBP", "JPY"],
    
    # Indices (mapped to their related currencies)
    "US30": ["USD"],
    "US100": ["USD"],
    "US500": ["USD"],
    "UK100": ["GBP"],
    "GER40": ["EUR"],
    "FRA40": ["EUR"],
    "ESP35": ["EUR"],
    "JP225": ["JPY"],
    "AUS200": ["AUD"],
    
    # Commodities (mapped to USD primarily)
    "XAUUSD": ["USD", "XAU"],  # Gold
    "XAGUSD": ["USD", "XAG"],  # Silver
    "USOIL": ["USD"],          # Oil (WTI)
    "UKOIL": ["USD", "GBP"],   # Oil (Brent)
    
    # Crypto
    "BTCUSD": ["USD", "BTC"],
    "ETHUSD": ["USD", "ETH"],
    "LTCUSD": ["USD", "LTC"],
    "XRPUSD": ["USD", "XRP"],

    # Additional currency pairs
    "EURCHF": ["EUR", "CHF"],
    "GBPCHF": ["GBP", "CHF"],
    "AUDNZD": ["AUD", "NZD"],
    "AUDCAD": ["AUD", "CAD"],
    "AUDCHF": ["AUD", "CHF"],
    "AUDJPY": ["AUD", "JPY"],
    "CADCHF": ["CAD", "CHF"],
    "CADJPY": ["CAD", "JPY"],
    "EURAUD": ["EUR", "AUD"],
    "EURCAD": ["EUR", "CAD"],
    "EURNZD": ["EUR", "NZD"],
    "GBPAUD": ["GBP", "AUD"],
    "GBPCAD": ["GBP", "CAD"],
    "GBPNZD": ["GBP", "NZD"],
    "NZDCAD": ["NZD", "CAD"],
    "NZDCHF": ["NZD", "CHF"],
    "NZDJPY": ["NZD", "JPY"],
}

# Impact levels and their emoji representations
IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
    "Low": "🟢"
}

class EconomicCalendarService:
    """
    Service for retrieving economic calendar data from ForexFactory or TradingView API.
    
    This service provides methods to fetch and format economic calendar events
    for display in various formats. It uses the ForexFactory as the primary
    data source with fallback to TradingView API.
    """
    
    def __init__(self):
        """
        Initialize the calendar service with the ForexFactory implementation.
        
        Sets up the ForexFactory calendar service and configures caching and
        fallback options based on environment variables.
        """
        self.logger = logging.getLogger(__name__)
        
        # Initialize ForexFactory calendar service with fallback to TradingView
        self.forexfactory_service = None
        self.tradingview_service = None
        
        # Enable fallback mode if environment variable is set
        self.use_fallback = os.environ.get("CALENDAR_FALLBACK", "").lower() in ("true", "1", "yes")
        if self.use_fallback:
            self.logger.info("Calendar fallback mode is enabled")
        
        # Check if ForexFactory is explicitly disabled
        use_forexfactory = os.environ.get("USE_FOREXFACTORY_CALENDAR", "").lower() not in ("false", "0", "no")
        
        # Try to initialize TradingView calendar service first
        try:
            from trading_bot.services.calendar_service.tradingview_calendar import TradingViewCalendarService
            self.tradingview_service = TradingViewCalendarService()
            self.logger.info("TradingView calendar service initialized")
        except Exception as e:
            self.logger.warning(f"Could not initialize TradingView calendar service: {str(e)}")
            self.logger.debug(traceback.format_exc())
        
        # Try to initialize ForexFactory calendar service if not disabled
        if use_forexfactory and HAS_FOREXFACTORY:
            try:
                self.forexfactory_service = ForexFactoryCalendarService()
                self.logger.info("ForexFactory calendar service initialized")
            except Exception as e:
                self.logger.warning(f"Could not initialize ForexFactory calendar service: {str(e)}")
                self.logger.debug(traceback.format_exc())
        
        # Use TradingView as primary, with ForexFactory as fallback
        if self.tradingview_service:
            self.calendar_service = self.tradingview_service
            self.logger.info("Using TradingView API for economic calendar")
        elif self.forexfactory_service:
            self.calendar_service = self.forexfactory_service
            self.logger.info("Using ForexFactory for economic calendar")
        else:
            self.logger.error("No calendar service available!")
            self.calendar_service = None
        
        # Setup caching
        self.cache = {}
        self.cache_time = {}
        self.cache_expiry = 3600  # 1 hour in seconds
        
        # Define loading GIF URLs
        self.loading_gif = "https://media.giphy.com/media/dpjUltnOPye7azvAhH/giphy.gif"
    
    def _get_service_name(self, service):
        """
        Get the name of the service for logging purposes.
        
        Args:
            service: The service instance to get the name for
            
        Returns:
            String name of the service
        """
        if service is None:
            return "None"
        elif isinstance(service, ForexFactoryCalendarService):
            return "ForexFactory"
        else:
            return "TradingView"
    
    def get_loading_gif(self) -> str:
        """
        Get the URL for the loading GIF to display during API calls.
        
        Returns:
            URL string for the loading GIF
        """
        return self.loading_gif
        
    async def get_economic_calendar(self, currencies: List[str] = None, days_ahead: int = 0, min_impact: str = "Low") -> str:
        """
        Get the economic calendar formatted for display.
        
        Args:
            currencies: List of currencies to filter events by
            days_ahead: Number of days to look ahead (0=today, 1=tomorrow, etc.)
            min_impact: Minimum impact level to include ("Low", "Medium", "High")
            
        Returns:
            Formatted calendar string for display
        """
        self.logger.info(f"Getting economic calendar (currencies={currencies}, days_ahead={days_ahead}, min_impact={min_impact})")
        
        if self.calendar_service is None:
            self.logger.error("No calendar service available")
            return "❌ Economic calendar service is not available."
        
        try:
            # Get calendar events
            events = await self.get_calendar(days_ahead, min_impact, currencies[0] if currencies and len(currencies) == 1 else None)
            
            if not events:
                self.logger.warning("No calendar events found")
                return "No economic events found for the selected criteria."
            
            # Format calendar events
            if HAS_CHRONOLOGICAL_FORMATTER:
                # Use chronological formatter if available
                today_formatted = datetime.now().strftime("%A, %d %B %Y")
                
                # If we have a single currency, use chronological format
                # If we have multiple currencies, group by currency
                group_by_currency = currencies is not None and len(currencies) > 1
                
                formatted_calendar = await self.calendar_service.format_calendar_chronologically(
                    events, today_formatted, group_by_currency)
            else:
                # Fall back to simple formatting
                formatted_calendar = await format_calendar_for_telegram(events)
            
            return formatted_calendar
            
        except Exception as e:
            self.logger.error(f"Error getting economic calendar: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return f"❌ Error retrieving economic calendar: {str(e)}"
    
    async def get_calendar(self, days_ahead: int = 0, min_impact: str = "Low", currency: str = None) -> List[Dict]:
        """
        Get calendar events from the API or cache.
        
        Args:
            days_ahead: Number of days to look ahead (0=today, 1=tomorrow, etc.)
            min_impact: Minimum impact level to include ("Low", "Medium", "High")
            currency: Optional currency to filter events by
            
        Returns:
            List of calendar events as dictionaries
        """
        self.logger.info(f"Getting calendar (days_ahead={days_ahead}, min_impact={min_impact}, currency={currency})")
        
        if self.calendar_service is None:
            self.logger.error("No calendar service available")
            return []
        
        # Check cache
        cache_key = f"{days_ahead}_{min_impact}_{currency}"
        if cache_key in self.cache and cache_key in self.cache_time:
            if time.time() - self.cache_time[cache_key] < self.cache_expiry:
                self.logger.info(f"Using cached calendar data for {cache_key}")
                return self.cache[cache_key]
        
        try:
            # Get events from calendar service
            events = await self.calendar_service.get_calendar(days_ahead, min_impact, currency)
            
            # Cache results
            self.cache[cache_key] = events
            self.cache_time[cache_key] = time.time()
            
            return events
        except Exception as e:
            self.logger.error(f"Error getting calendar: {str(e)}")
            self.logger.debug(traceback.format_exc())
            
            # If fallback is enabled, generate fallback events
            if self.use_fallback:
                self.logger.info("Using fallback calendar data")
                return self._generate_fallback_events(currency)
            
            return []
    
    def _generate_fallback_events(self, currency=None) -> List[Dict]:
        """
        Generate fallback events for when the API is unavailable.
        
        Args:
            currency: Optional currency to filter events by
            
        Returns:
            List of fallback events as dictionaries
        """
        self.logger.info(f"Generating fallback events for currency {currency}")
        
        # If the calendar service has a fallback method, use it
        if hasattr(self.calendar_service, '_generate_fallback_events'):
            return self.calendar_service._generate_fallback_events(currency)
        
        # Otherwise, generate simple fallback events
        now = datetime.now()
        events = []
        
        # Generate a few events for today
        currencies = [currency] if currency else MAJOR_CURRENCIES
        
        for curr in currencies[:3]:  # Limit to 3 currencies to avoid too many events
            events.append({
                'title': f"{curr} Fallback Economic Data",
                'country': curr[:2],  # First two letters as country code
                'currency': curr,
                'date': now.strftime("%Y-%m-%dT%H:%M:%S"),
                'impact': "Medium",
                'forecast': "N/A",
                'previous': "N/A",
                'actual': "N/A"
            })
        
        return events
    
    async def get_events_for_instrument(self, instrument: str, days_ahead: int = 0, min_impact: str = "Low") -> Dict[str, Any]:
        """
        Get events for a specific trading instrument.
        
        Args:
            instrument: The instrument to get events for (e.g., "EURUSD")
            days_ahead: Number of days to look ahead
            min_impact: Minimum impact level to include
            
        Returns:
            Dictionary with events grouped by currency
        """
        self.logger.info(f"Getting events for instrument {instrument}")
        
        # Get currencies for instrument
        currencies = INSTRUMENT_CURRENCY_MAP.get(instrument, [])
        if not currencies:
            self.logger.warning(f"No currencies found for instrument {instrument}")
            return {"events": [], "explanation": f"No currency data available for {instrument}"}
        
        # Get events for each currency
        result = {"events": [], "currencies": currencies, "explanation": f"Economic events for {instrument}"}
        for currency in currencies:
            events = await self.get_calendar(days_ahead, min_impact, currency)
            if events:
                result["events"].extend(events)
        
        return result
    
    async def get_instrument_calendar(self, instrument: str, days_ahead: int = 0, min_impact: str = "Low") -> str:
        """
        Get formatted calendar for a specific trading instrument.
        
        Args:
            instrument: The instrument to get events for (e.g., "EURUSD")
            days_ahead: Number of days to look ahead
            min_impact: Minimum impact level to include
            
        Returns:
            Formatted calendar string for display
        """
        self.logger.info(f"Getting instrument calendar for {instrument}")
        
        # Get currencies for instrument
        currencies = INSTRUMENT_CURRENCY_MAP.get(instrument, [])
        if not currencies:
            return f"No currency data available for {instrument}."
        
        # Get economic calendar for these currencies
        return await self.get_economic_calendar(currencies, days_ahead, min_impact)

# Telegram service class for sending calendar updates
class TelegramService:
    """Service for sending calendar updates via Telegram"""
    
    def __init__(self, db: Database, stripe_service=None):
        """Initialize the Telegram service"""
        self.db = db
        self.stripe_service = stripe_service
        self.calendar_service = EconomicCalendarService()
        self.logger = logging.getLogger(__name__)

# Helper function to get Tavily service
def get_tavily_service():
    """Get Tavily service instance if available"""
    return None

# Helper function to format calendar for Telegram
async def format_calendar_for_telegram(events: List[Dict]) -> str:
    """
    Format calendar events for Telegram display.
    
    Args:
        events: List of calendar events as dictionaries
        
    Returns:
        Formatted calendar string for Telegram
    """
    if not events:
        return "No economic events found."
    
    # Group events by date
    events_by_date = {}
    for event in events:
        event_date = event.get('date', '')
        if not event_date:
            continue
        
        # Parse date
        try:
            dt = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
            date_key = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            continue
        
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        
        events_by_date[date_key].append({
            'time': time_str,
            'currency': event.get('currency', ''),
            'title': event.get('title', ''),
            'impact': event.get('impact', 'Low'),
            'forecast': event.get('forecast', 'N/A'),
            'previous': event.get('previous', 'N/A'),
            'actual': event.get('actual', 'N/A')
        })
    
    # Sort events by time
    for date_key in events_by_date:
        events_by_date[date_key].sort(key=lambda x: x['time'])
    
    # Format output
    output = []
    for date_key in sorted(events_by_date.keys()):
        try:
            date_obj = datetime.strptime(date_key, "%Y-%m-%d")
            date_str = date_obj.strftime("%A, %d %B %Y")
            output.append(f"📅 *{date_str}*\n")
        except ValueError:
            output.append(f"📅 *{date_key}*\n")
        
        for event in events_by_date[date_key]:
            impact = event['impact']
            impact_emoji = IMPACT_EMOJI.get(impact, "⚪")
            currency = event['currency']
            title = event['title']
            time = event['time']
            forecast = event['forecast']
            previous = event['previous']
            
            # Format event line
            event_line = f"{impact_emoji} {time} *{currency}*: {title}"
            if forecast != 'N/A':
                event_line += f" | Forecast: {forecast}"
            if previous != 'N/A':
                event_line += f" | Previous: {previous}"
            
            output.append(event_line + "\n")
    
    return "\n".join(output)
