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
    Economic calendar service that provides economic event data.
    
    This service uses ForexFactory as the primary data source.
    """

    def __init__(self):
        """
        Initialize the calendar service with the ForexFactory implementation.
        
        Sets up the ForexFactory calendar service and configures caching and
        fallback options based on environment variables.
        """
        self.logger = logging.getLogger(__name__)
        
        # Initialize ForexFactory calendar service
        self.forexfactory_service = None
        
        # Enable fallback mode if environment variable is set
        self.use_fallback = os.environ.get("CALENDAR_FALLBACK", "").lower() in ("true", "1", "yes")
        if self.use_fallback:
            self.logger.info("Calendar fallback mode is enabled")
        
        # Initialize ForexFactory calendar service
        try:
            from trading_bot.services.calendar_service.forexfactory_calendar import ForexFactoryCalendarService
            self.forexfactory_service = ForexFactoryCalendarService()
            self.logger.info("ForexFactory calendar service initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize ForexFactory calendar service: {str(e)}")
            self.logger.error(traceback.format_exc())
        
        # Set the primary calendar service
        self.calendar_service = self.forexfactory_service
        self.logger.info("Using ForexFactory for economic calendar")
    
    async def get_calendar(self, days_ahead: int = 0, min_impact: str = "Low", currency: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get economic calendar events.
        
        Args:
            days_ahead: Number of days ahead to fetch events for
            min_impact: Minimum impact level to include (Low, Medium, High)
            currency: Filter by currency code (e.g., USD, EUR)
        
        Returns:
            List of economic calendar events
        """
        self.logger.info(f"Getting calendar (days_ahead={days_ahead}, min_impact={min_impact}, currency={currency})")
        
        if not self.calendar_service:
            self.logger.error("No calendar service available")
            return []
        
        try:
            events = await self.calendar_service.get_calendar(days_ahead, min_impact, currency)
            self.logger.info(f"Retrieved {len(events)} events from ForexFactory")
            return events
        except Exception as e:
            self.logger.error(f"Error getting calendar: {str(e)}")
            self.logger.error(traceback.format_exc())
            return []
    
    async def get_economic_calendar(self, days_ahead: int = 0, min_impact: str = "Low", currency: Optional[str] = None) -> str:
        """
        Get formatted economic calendar as a string.
        
        Args:
            days_ahead: Number of days ahead to fetch events for
            min_impact: Minimum impact level to include (Low, Medium, High)
            currency: Filter by currency code (e.g., USD, EUR)
        
        Returns:
            Formatted economic calendar as a string
        """
        events = await self.get_calendar(days_ahead, min_impact, currency)
        
        if not events:
            return "No economic events found."
        
        # Format the calendar
        from trading_bot.services.calendar_service import IMPACT_EMOJI
        
        # Get today's date for highlighting today's events
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Format the calendar
        calendar_text = "📅 *Economic Calendar*\n\n"
        
        # Group events by date
        events_by_date = {}
        for event in events:
            date = event.get("date", "Unknown")
            if date not in events_by_date:
                events_by_date[date] = []
            events_by_date[date].append(event)
        
        # Sort dates
        sorted_dates = sorted(events_by_date.keys())
        
        # Format events by date
        for date in sorted_dates:
            date_events = events_by_date[date]
            
            # Add date header
            is_today = date == today
            date_header = f"*{date}* {'(Today)' if is_today else ''}"
            calendar_text += f"📆 {date_header}\n"
            
            # Add impact legend
            calendar_text += "Impact: 🔴 High   🟠 Medium   🟢 Low\n\n"
            
            # Sort events by time
            date_events.sort(key=lambda e: e.get("time", "00:00"))
            
            # Add events
            for event in date_events:
                time = event.get("time", "")
                currency = event.get("currency", "")
                country = event.get("country", "")
                impact = event.get("impact", "Low")
                title = event.get("title", "")
                forecast = event.get("forecast", "")
                previous = event.get("previous", "")
                
                # Get emoji for impact
                impact_emoji = IMPACT_EMOJI.get(impact, "⚪")
                
                # Format the event
                event_text = f"{time} - {impact_emoji} "
                
                # Add country/flag if available
                if country:
                    event_text += f"{country} "
                
                # Add title and details
                event_text += f"{title}"
                if forecast and forecast != "N/A":
                    event_text += f" (Forecast: {forecast})"
                if previous and previous != "N/A":
                    event_text += f" (Previous: {previous})"
                
                calendar_text += f"{event_text}\n"
            
            # Add separator between dates
            calendar_text += "\n"
        
        return calendar_text

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
