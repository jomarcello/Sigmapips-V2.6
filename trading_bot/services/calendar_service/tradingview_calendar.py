import os
import sys
import logging
import asyncio
import json
import pandas as pd
import aiohttp
import http.client
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import re

# Configure logging first, before any imports that use it
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import onze custom mock data generator
try:
    from trading_bot.services.calendar_service._generate_mock_calendar_data import generate_mock_calendar_data
    HAS_CUSTOM_MOCK_DATA = True
except ImportError:
    HAS_CUSTOM_MOCK_DATA = False
    logger.warning("Custom mock calendar data not available, using default mock data")

# Import our chronological formatter
try:
    from trading_bot.services.calendar_service.chronological_formatter import (
        format_calendar_events_chronologically,
        format_calendar_events_by_currency,
        format_tradingview_calendar
    )
    HAS_CHRONOLOGICAL_FORMATTER = True
    logger.info("Successfully imported chronological calendar formatter")
except ImportError:
    HAS_CHRONOLOGICAL_FORMATTER = False
    logger.warning("Chronological calendar formatter not available")

# Map of major currencies to country codes for TradingView API
CURRENCY_COUNTRY_MAP = {
    "USD": "US",
    "EUR": "EU",
    "GBP": "GB",
    "JPY": "JP",
    "CHF": "CH",
    "AUD": "AU",
    "NZD": "NZ",
    "CAD": "CA",
    # Extra landen toevoegen die op TradingView worden getoond
    "CNY": "CN",  # China
    "HKD": "HK",  # Hong Kong
    "SGD": "SG",  # Singapore
    "INR": "IN",  # India
    "BRL": "BR",  # Brazilië
    "MXN": "MX",  # Mexico
    "ZAR": "ZA",  # Zuid-Afrika
    "SEK": "SE",  # Zweden
    "NOK": "NO",  # Noorwegen
    "DKK": "DK",  # Denemarken
    "PLN": "PL",  # Polen
    "TRY": "TR",  # Turkije
    "RUB": "RU",  # Rusland
    "KRW": "KR",  # Zuid-Korea
    "ILS": "IL",  # Israël
    # Ontbrekende landen die op TradingView worden getoond
    "IDR": "ID",  # Indonesië
    "SAR": "SA",  # Saudi Arabië
    "THB": "TH",  # Thailand
    "MYR": "MY",  # Maleisië
    "PHP": "PH",  # Filipijnen
    "VND": "VN",  # Vietnam
    "UAH": "UA",  # Oekraïne
    "AED": "AE",  # Verenigde Arabische Emiraten
    "QAR": "QA",  # Qatar
    "CZK": "CZ",  # Tsjechië
    "HUF": "HU",  # Hongarije
    "RON": "RO",  # Roemenië
    "CLP": "CL",  # Chili
    "COP": "CO",  # Colombia
    "PEN": "PE",  # Peru
    "ARS": "AR"   # Argentinië
}

# Impact levels and their emoji representations
IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
    "Low": "🟢"
}

# Definieer de major currencies die we altijd willen tonen
MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]

class TradingViewCalendarService:
    """Service for retrieving calendar data directly from TradingView"""
    
    def __init__(self):
        # TradingView calendar API endpoint - ensure this is the current working endpoint
        self.base_url = "https://economic-calendar.tradingview.com/events"
        self.session = None
        # Keep track of last successful API call
        self.last_successful_call = None
        
        logger.info("TradingView Calendar Service initialized (direct API access)")
        
    async def _ensure_session(self):
        """Ensure we have an active aiohttp session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            
    async def _close_session(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
            
    def _format_date(self, date: datetime) -> str:
        """Format date for TradingView API"""
        # Remove microseconds and format as expected by the API
        date = date.replace(microsecond=0)
        return date.isoformat() + '.000Z'
        
    async def _check_api_health(self) -> bool:
        """Check if the TradingView API endpoint is working"""
        try:
            await self._ensure_session()
            
            # Simple health check request with minimal parameters
            current_time = datetime.now()
            params = {
                'from': self._format_date(current_time),
                'to': self._format_date(current_time + timedelta(days=1)),
                'limit': 1
            }
            
            # Add headers for better API compatibility
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://www.tradingview.com",
                "Referer": "https://www.tradingview.com/economic-calendar/",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            }
            
            # Make direct API call to TradingView
            full_url = f"{self.base_url}"
            logger.info(f"Checking API health: {full_url}")
            
            async with self.session.get(full_url, params=params, headers=headers) as response:
                logger.info(f"Health check response status: {response.status}")
                response_text = await response.text()
                logger.info(f"Health check response preview: {response_text[:100]}...")
                
                if response.status == 200:
                    # Double check that the response actually contains JSON data
                    if response_text.strip().startswith('[') or response_text.strip().startswith('{'):
                        logger.info("API is healthy and returning valid JSON")
                        return True
                    else:
                        logger.error("API returned 200 but not valid JSON")
                        logger.error(f"First 200 chars of response: {response_text[:200]}")
                        return False
                
                return False
                
        except Exception as e:
            logger.error(f"API health check failed: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    async def get_calendar(self, days_ahead: int = 0, min_impact: str = "Low", currency: str = None, all_currencies: bool = False) -> List[Dict[str, Any]]:
        """Get economic calendar data
        
        Args:
            days_ahead: Number of days to look ahead
            min_impact: Minimum impact level to include (Low, Medium, High)
            currency: Optional currency to filter events by
            all_currencies: If True, include all currencies
            
        Returns:
            List of calendar events
        """
        logger.info(f"Getting calendar data (days_ahead={days_ahead}, min_impact={min_impact}, currency={currency})")
        
        try:
            await self._ensure_session()
            
            # Calculate date range
            current_time = datetime.now()
            
            # If days_ahead is 0, start from current time
            # If days_ahead > 0, start from midnight of that day
            if days_ahead == 0:
                from_date = current_time
            else:
                # Start from midnight of the target day
                from_date = datetime(
                    current_time.year, current_time.month, current_time.day,
                    0, 0, 0
                ) + timedelta(days=days_ahead)
            
            # End date is always the end of the selected day
            to_date = datetime(
                from_date.year, from_date.month, from_date.day,
                23, 59, 59
            ) + timedelta(days=0)
            
            # Log the date range for debugging
            logger.info(f"Date range: {from_date} to {to_date}")
            
            # Format dates for API
            params = {
                'from': self._format_date(from_date),
                'to': self._format_date(to_date)
            }
            
            # Add headers for better API compatibility
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://www.tradingview.com",
                "Referer": "https://www.tradingview.com/economic-calendar/"
            }
            
            # Make direct API call to TradingView
            full_url = f"{self.base_url}"
            logger.info(f"Making direct API request to: {full_url}")
            
            try:
                async with self.session.get(full_url, params=params, headers=headers) as response:
                    logger.info(f"API response status: {response.status}")
                    
                    if response.status == 200:
                        response_text = await response.text()
                        
                        # Check if the response is valid JSON
                        if response_text.strip().startswith('[') or response_text.strip().startswith('{'):
                            logger.info("Successfully retrieved data from TradingView API")
                            
                            # Log a sample of the response for debugging
                            logger.info(f"API Response Type: {type(response_text)}")
                            try:
                                data = json.loads(response_text)
                                if isinstance(data, dict) and 'result' in data:
                                    sample = data['result'][:2] if len(data['result']) > 2 else data['result']
                                elif isinstance(data, list):
                                    sample = data[:2] if len(data) > 2 else data
                                else:
                                    sample = str(data)[:200] + "..."
                                logger.info(f"API Response Sample: {json.dumps(sample, default=str)}")
                            except Exception as e:
                                logger.error(f"Error parsing response sample: {str(e)}")
                            
                            self.last_successful_call = datetime.now()
                            
                            # Process the response
                            events = await self._process_response_text(response_text, min_impact, currency)
                            logger.info(f"Processed {len(events)} events from API response")
                            
                            # If no events were found, use fallback data
                            if not events:
                                logger.warning("No events found in API response, using fallback data")
                                return self._generate_fallback_events(currency, all_currencies)
                                
                            return events
                        else:
                            logger.error("API returned 200 but not valid JSON")
                            logger.error(f"First 200 chars of response: {response_text[:200]}")
                    else:
                        logger.error(f"API request failed with status {response.status}")
            except Exception as e:
                logger.error(f"Error making API call: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
            
            # If API call failed, use fallback data
            logger.warning("API call failed, using fallback data")
            return self._generate_fallback_events(currency, all_currencies)
                
        except Exception as e:
            logger.error(f"Error getting calendar data: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Use fallback data
            return self._generate_fallback_events(currency, all_currencies)

    def _generate_fallback_events(self, currency=None, all_currencies: bool = False) -> List[Dict]:
        """Generate fallback economic events based on day of week
        
        Args:
            currency: Optional currency to filter events by
            all_currencies: If True, include all currencies
            
        Returns:
            List of fallback calendar events
        """
        logger.info("Generating fallback economic events")
        events = []
        
        # Get current date and time
        now = datetime.now()
        current_hour = now.hour
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        
        # Map weekday to currency events
        weekday_events = {
            0: ["USD", "EUR"],           # Monday - USD, EUR
            1: ["GBP", "USD", "AUD"],    # Tuesday - GBP, USD, AUD
            2: ["JPY", "EUR", "USD"],    # Wednesday - JPY, EUR, USD
            3: ["USD", "GBP", "CHF"],    # Thursday - USD, GBP, CHF
            4: ["USD", "CAD", "JPY"],    # Friday - USD, CAD, JPY
            5: ["USD"],                  # Saturday - Limited events
            6: ["USD"]                   # Sunday - Limited events
        }
        
        # Find which currencies have events today
        active_currencies = weekday_events.get(weekday, ["USD"])
        
        # If all_currencies is True, include all major currencies
        if all_currencies:
            active_currencies = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD"]
        # If currency is specified, only include that currency's events
        elif currency and currency not in active_currencies:
            # Add at least one event for the requested currency
            active_currencies = [currency]
        
        # Common economic events for each currency
        currency_events = {
            "USD": [
                {"time": f"{(current_hour + 1) % 24:02d}:30", "event": "Retail Sales", "impact": "Medium"},
                {"time": f"{(current_hour + 2) % 24:02d}:00", "event": "CPI Data", "impact": "High"},
                {"time": f"{(current_hour + 3) % 24:02d}:30", "event": "Unemployment Claims", "impact": "Medium"},
                {"time": f"{(current_hour + 4) % 24:02d}:00", "event": "Fed Chair Speech", "impact": "High"}
            ],
            "EUR": [
                {"time": f"{(current_hour + 1) % 24:02d}:00", "event": "ECB Interest Rate Decision", "impact": "High"},
                {"time": f"{(current_hour + 2) % 24:02d}:30", "event": "German Manufacturing PMI", "impact": "Medium"},
                {"time": f"{(current_hour + 3) % 24:02d}:45", "event": "French CPI", "impact": "Medium"}
            ],
            "GBP": [
                {"time": f"{(current_hour + 2) % 24:02d}:30", "event": "BOE Interest Rate Decision", "impact": "High"},
                {"time": f"{(current_hour + 3) % 24:02d}:00", "event": "UK Employment Change", "impact": "Medium"}
            ],
            "JPY": [
                {"time": f"{(current_hour + 1) % 24:02d}:50", "event": "BOJ Policy Meeting", "impact": "High"},
                {"time": f"{(current_hour + 3) % 24:02d}:30", "event": "Tokyo CPI", "impact": "Medium"}
            ],
            "CHF": [
                {"time": f"{(current_hour + 2) % 24:02d}:15", "event": "SNB Interest Rate Decision", "impact": "High"},
                {"time": f"{(current_hour + 3) % 24:02d}:30", "event": "Trade Balance", "impact": "Low"}
            ],
            "AUD": [
                {"time": f"{(current_hour + 2) % 24:02d}:30", "event": "RBA Interest Rate Decision", "impact": "High"},
                {"time": f"{(current_hour + 4) % 24:02d}:00", "event": "Employment Change", "impact": "Medium"}
            ],
            "CAD": [
                {"time": f"{(current_hour + 1) % 24:02d}:15", "event": "BOC Interest Rate Decision", "impact": "High"},
                {"time": f"{(current_hour + 3) % 24:02d}:30", "event": "Employment Change", "impact": "Medium"}
            ],
            "NZD": [
                {"time": f"{(current_hour + 2) % 24:02d}:00", "event": "RBNZ Interest Rate Decision", "impact": "High"},
                {"time": f"{(current_hour + 3) % 24:02d}:45", "event": "GDP q/q", "impact": "Medium"}
            ]
        }
        
        # Generate date string for today
        today_date_str = now.strftime("%Y-%m-%dT%H:%M:%S")
        
        # Add events for active currencies
        for curr in active_currencies:
            if curr in currency_events:
                for event_info in currency_events[curr]:
                    # Create event time as datetime
                    time_parts = event_info["time"].split(":")
                    event_hour = int(time_parts[0])
                    event_minute = int(time_parts[1])
                    
                    event_datetime = datetime(
                        now.year, now.month, now.day, 
                        event_hour, event_minute, 0
                    )
                    
                    # Format as ISO string
                    event_date_str = event_datetime.strftime("%Y-%m-%dT%H:%M:%S")
                    
                    event = {
                        "country": curr,
                        "time": event_info["time"],
                        "event": event_info["event"],
                        "impact": event_info["impact"],
                        "previous": "1.2%",
                        "forecast": "1.5%",
                        "actual": None,
                        "date": event_date_str,
                        "datetime": event_datetime,
                        "is_fallback": True  # Mark as fallback data
                    }
                    events.append(event)
        
        # Sort by time
        events.sort(key=lambda x: x["time"])
        
        # If a specific currency was requested, highlight its events
        if currency:
            for event in events:
                event["highlighted"] = event.get("country") == currency
        
        logger.info(f"Generated {len(events)} fallback events")
        return events

    # Voeg een nieuwe helper methode toe voor het verwerken van response tekst
    async def _process_response_text(self, response_text: str, min_impact: str = "Low", currency: str = None) -> List[Dict[str, Any]]:
        """Process the API response text into a list of calendar events
        
        Args:
            response_text: The raw API response text
            min_impact: Minimum impact level to include
            currency: Optional currency to filter events by
            
        Returns:
            List of processed calendar events
        """
        events = []
        
        try:
            # Parse the JSON response
            data = json.loads(response_text)
            
            # Check if the data is a list (direct events) or a dict with a result field
            if isinstance(data, dict) and 'result' in data:
                logger.info("API response contains 'result' field")
                items = data['result']
            elif isinstance(data, list):
                logger.info("API response is a direct list of events")
                items = data
            else:
                logger.warning(f"Unexpected API response structure: {type(data)}")
                if isinstance(data, dict):
                    logger.warning(f"API response keys: {data.keys()}")
                return []
            
            # Log the number of items and the structure of the first item
            logger.info(f"Processing {len(items)} events from API")
            if items and len(items) > 0:
                logger.info(f"Event item structure: {items[0].keys()}")
            
            # Process each event
            for item in items:
                # Skip non-dictionary items
                if not isinstance(item, dict):
                    logger.warning(f"Skipping non-dictionary item: {type(item)}")
                    continue
                
                # Log the structure of each item for debugging (but limit to avoid excessive logging)
                if len(events) < 3:
                    logger.info(f"Event item structure: {item.keys()}")
                
                try:
                    # Extract event details with fallbacks for missing fields
                    event_date_str = item.get('date', '')
                    
                    # Skip events without a date
                    if not event_date_str:
                        logger.warning("Skipping event with no date")
                        continue
                    
                    # Parse the date string to a datetime object
                    try:
                        # Handle different date formats
                        if 'T' in event_date_str:
                            # ISO format with T separator
                            event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
                        else:
                            # Try simple date format
                            event_date = datetime.strptime(event_date_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        logger.warning(f"Could not parse date: {event_date_str}")
                        continue
                    
                    # Format the time for display
                    event_time = event_date.strftime('%H:%M')
                    
                    # Get the country/currency with fallbacks
                    event_country = item.get('country', '')
                    
                    # Skip events for other currencies if a specific currency is requested
                    if currency and event_country != currency:
                        continue
                    
                    # Get the title/event name with fallbacks
                    event_title = item.get('title', '')
                    if not event_title and 'indicator' in item:
                        event_title = item.get('indicator', '')
                    
                    # Determine impact level with robust handling
                    impact = "Low"
                    if 'importance' in item:
                        importance = item.get('importance', 0)
                        if isinstance(importance, (int, float)):
                            if importance >= 3:
                                impact = "High"
                            elif importance >= 2:
                                impact = "Medium"
                            else:
                                impact = "Low"
                        elif isinstance(importance, str):
                            # If importance is already a string, use it directly if valid
                            if importance in ["High", "Medium", "Low"]:
                                impact = importance
                    
                    # Skip events with impact lower than min_impact
                    if min_impact == "High" and impact != "High":
                        continue
                    elif min_impact == "Medium" and impact == "Low":
                        continue
                    
                    # Get forecast and previous values with consistent formatting
                    forecast = item.get('forecast', '')
                    if not forecast and 'forecastRaw' in item:
                        forecast_raw = item.get('forecastRaw', '')
                        if forecast_raw not in (None, ''):
                            forecast = str(forecast_raw)
                    
                    previous = item.get('previous', '')
                    if not previous and 'previousRaw' in item:
                        previous_raw = item.get('previousRaw', '')
                        if previous_raw not in (None, ''):
                            previous = str(previous_raw)
                    
                    actual = item.get('actual', '')
                    if not actual and 'actualRaw' in item:
                        actual_raw = item.get('actualRaw', '')
                        if actual_raw not in (None, ''):
                            actual = str(actual_raw)
                    
                    # Create the event object with consistent keys
                    event = {
                        'time': event_time,
                        'country': event_country,
                        'event': event_title,
                        'impact': impact,
                        'forecast': forecast,
                        'previous': previous,
                        'actual': actual,
                        'datetime': event_date,  # Keep the full datetime for sorting
                        'date': event_date_str,  # Keep the original date string
                    }
                    
                    # Add any additional fields that might be useful
                    if 'currency' in item:
                        event['currency'] = item.get('currency', '')
                    
                    if 'unit' in item:
                        event['unit'] = item.get('unit', '')
                    
                    if 'ticker' in item:
                        event['ticker'] = item.get('ticker', '')
                    
                    events.append(event)
                
                except Exception as e:
                    logger.error(f"Error processing event: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue
            
            # Sort events by datetime
            events.sort(key=lambda x: x['datetime'])
            
            # Log the number of events after processing
            logger.info(f"Processed {len(events)} events after filtering")
            
            return events
            
        except json.JSONDecodeError:
            logger.error("Failed to parse API response as JSON")
            logger.error(f"Response preview: {response_text[:200]}...")
            return []
        except Exception as e:
            logger.error(f"Error processing API response: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    async def debug_api_connection(self):
        """Perform detailed API connection debugging"""
        logger.info("Starting TradingView API connection debug")
        debug_info = {
            "api_health": False,
            "connection_error": None,
            "events_retrieved": 0,
            "sample_events": [],
            "last_successful_call": None,
            "test_time": datetime.now().isoformat(),
            "scrapingant_enabled": False,
            "scrapingant_api_key_set": False
        }
        
        try:
            # Log alle configuratie en omgevingsvariabelen
            logger.info("Environment variables:")
            logger.info(f"- USE_SCRAPINGANT: {os.environ.get('USE_SCRAPINGANT', 'not set')}")
            logger.info(f"- USE_CALENDAR_FALLBACK: {os.environ.get('USE_CALENDAR_FALLBACK', 'not set')}")
            
            # Check API health
            await self._ensure_session()
            is_healthy = await self._check_api_health()
            debug_info["api_health"] = is_healthy
            
            if is_healthy:
                # Probeer gegevens op te halen
                logger.info("API is healthy, attempting to retrieve events")
                events = await self.get_calendar(days_ahead=0)
                debug_info["events_retrieved"] = len(events)
                if events:
                    # Include a sample of first 3 events
                    debug_info["sample_events"] = events[:3]
                
                # Record last successful call
                debug_info["last_successful_call"] = self.last_successful_call.isoformat() if self.last_successful_call else None
            else:
                # Als API health check mislukt, probeer alsnog ScrapingAnt als fallback
                logger.info("API health check failed, using fallback data")
            
            logger.info(f"API debug completed: health={debug_info['api_health']}, events={debug_info.get('events_retrieved', 0)}")
            return debug_info
            
        except Exception as e:
            logger.error(f"Error during API debug: {str(e)}")
            debug_info["connection_error"] = str(e)
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return debug_info
        
        finally:
            await self._close_session()

    async def get_economic_calendar(self, currencies: List[str] = None, days_ahead: int = 0, min_impact: str = "Low") -> str:
        """Get economic calendar formatted for Telegram
        
        Args:
            currencies: List of currencies to filter events by
            days_ahead: Number of days to look ahead (0=today, 1=tomorrow, etc.)
            min_impact: Minimum impact level to include ("Low", "Medium", "High")
            
        Returns:
            Formatted calendar string for Telegram
        """
        try:
            logger.info(f"Getting economic calendar for currencies: {currencies}, days_ahead: {days_ahead}")
            
            # Get all events from TradingView (we'll filter by currency ourselves)
            all_events = await self.get_calendar(days_ahead=days_ahead, min_impact=min_impact)
            logger.info(f"Got {len(all_events)} events from TradingView")
            
            # Filter by currencies if provided
            filtered_events = all_events
            if currencies:
                filtered_events = [
                    event for event in all_events 
                    if event.get('country') in currencies
                ]
                logger.info(f"Filtered to {len(filtered_events)} events for currencies: {currencies}")
                
                # If no events found after filtering, try to get events for all major currencies
                if not filtered_events:
                    logger.info(f"No events found for {currencies}, fetching for all major currencies")
                    filtered_events = all_events
            
            # Format the events
            formatted_calendar = await format_calendar_for_telegram(filtered_events)
            
            return formatted_calendar
            
        except Exception as e:
            logger.error(f"Error in get_economic_calendar: {str(e)}")
            logger.exception(e)
            
            # Return a minimal calendar with error message
            return "<b>📅 Economic Calendar</b>\n\nSorry, there was an error retrieving the economic calendar data. Please try again later."

    async def format_calendar_chronologically(self, events: List[Dict], today_formatted: str = None, group_by_currency: bool = False) -> str:
        """
        Format calendar events in chronological order by time.
        
        Args:
            events: List of calendar events from get_calendar()
            today_formatted: Optional formatted date string to use in the header
            group_by_currency: Whether to group events by currency
            
        Returns:
            Formatted calendar text with events in chronological order
        """
        if HAS_CHRONOLOGICAL_FORMATTER:
            # Use our custom formatter if available
            return format_tradingview_calendar(events, group_by_currency, today_formatted)
        else:
            # Fallback to basic formatting if formatter not available
            if not events:
                return "No economic events found."
                
            # Basic chronological formatting
            events_sorted = sorted(events, key=lambda x: x.get("time", "00:00"))
            
            result = []
            for event in events_sorted:
                time = event.get("time", "00:00")
                country = event.get("country", "")
                impact = event.get("impact", "Low")
                title = event.get("event", "Economic Event")
                
                # Format impact with emoji
                impact_emoji = "🔴" if impact == "High" else "🟠" if impact == "Medium" else "🟢"
                
                result.append(f"{time} - {country} - {impact_emoji} {title}")
                
            return "\n".join(result)

async def format_calendar_for_telegram(events: List[Dict]) -> str:
    """Format the calendar data for Telegram display"""
    if not events:
        logger.warning("No events provided to format_calendar_for_telegram")
        return "<b>📅 Economic Calendar</b>\n\nNo economic events found for today."
    
    # Define impact emojis
    impact_emoji_map = {
        "High": "🔴",
        "Medium": "🟠",
        "Low": "🟢"
    }
    
    # Count events per type
    logger.info(f"Formatting {len(events)} events for Telegram")
    event_counts = {"total": len(events), "valid": 0, "missing_fields": 0, "highlighted": 0}
    
    # Log sample events to help diagnose issues
    try:
        sample_events = events[:2]
        logger.info(f"Sample events to format: {json.dumps(sample_events, indent=2, default=str)}")
    except Exception as e:
        logger.error(f"Error logging sample events: {str(e)}")
    
    # Sort events by time if not already sorted
    try:
        # Improved sorting with datetime objects
        def parse_time_for_sorting(event):
            # Try to get time from different possible fields
            time_str = event.get("time", "")
            
            # If no time field, try to extract from datetime or date field
            if not time_str and "datetime" in event:
                try:
                    if isinstance(event["datetime"], datetime):
                        return event["datetime"].hour * 60 + event["datetime"].minute
                    return 0
                except:
                    pass
            
            # If no datetime field, try to extract from date field
            if not time_str and "date" in event:
                try:
                    date_str = event["date"]
                    if 'T' in date_str:
                        # ISO format with T separator
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        return dt.hour * 60 + dt.minute
                except:
                    pass
            
            # Parse time string if available
            try:
                if time_str and ":" in time_str:
                    hours, minutes = time_str.split(":")
                    # Strip any AM/PM/timezone indicators
                    hours = hours.strip()
                    if " " in minutes:
                        minutes = minutes.split(" ")[0]
                    return int(hours) * 60 + int(minutes)
            except Exception as e:
                logger.error(f"Error parsing time for sorting: {str(e)} for time: {time_str}")
            
            return 0
        
        sorted_events = sorted(events, key=parse_time_for_sorting)
        logger.info(f"Sorted {len(sorted_events)} events by time")
    except Exception as e:
        logger.error(f"Error sorting calendar events: {str(e)}")
        sorted_events = events
    
    # Format the message
    message = "<b>📅 Economic Calendar</b>\n\n"
    message += f"Date: {datetime.now().strftime('%b %d, %Y')}\n\n"
    
    # Add impact legend
    message += "<b>Impact:</b> 🔴 High   🟠 Medium   🟢 Low\n\n"
    
    # Group events by country for better organization
    events_by_country = {}
    
    for event in sorted_events:
        # Get country code, with fallbacks
        country = event.get('country', '')
        if not country and 'currency' in event:
            country = event.get('currency', '')
        
        if not country:
            country = 'Unknown'
            
        if country not in events_by_country:
            events_by_country[country] = []
            
        events_by_country[country].append(event)
    
    # Process each country group
    for country, country_events in sorted(events_by_country.items()):
        # Add country header
        message += f"<b>{country}</b>\n"
        
        # Process events for this country
        for i, event in enumerate(country_events):
            try:
                # Extract event details with robust fallbacks
                
                # Get time with fallbacks
                event_time = event.get('time', '')
                if not event_time and 'datetime' in event and isinstance(event['datetime'], datetime):
                    event_time = event['datetime'].strftime('%H:%M')
                if not event_time and 'date' in event:
                    try:
                        date_str = event['date']
                        if 'T' in date_str:
                            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            event_time = dt.strftime('%H:%M')
                    except:
                        pass
                if not event_time:
                    event_time = 'TBA'
                
                # Get event title with more robust fallbacks
                event_title = None
                
                # Try all possible fields where the title might be
                for field in ['event', 'title', 'indicator', 'name', 'description']:
                    if field in event and event[field]:
                        event_title = event[field]
                        break
                
                # If still no title found, use a default
                if not event_title:
                    logger.warning(f"No title found for event: {json.dumps(event, default=str)[:200]}")
                    event_title = 'Unnamed Event'
                
                # Get impact with fallbacks
                impact = event.get('impact', 'Low')
                impact_emoji = impact_emoji_map.get(impact, "🟢")
                
                # Format event line
                event_line = f"{event_time} - {impact_emoji} {event_title}"
                
                # Add values if available
                values = []
                
                # Handle previous, forecast and actual values with robust checks
                previous = None
                if "previous" in event and event["previous"] not in (None, ''):
                    previous = event["previous"]
                elif "previousRaw" in event and event["previousRaw"] not in (None, ''):
                    previous = event["previousRaw"]
                
                forecast = None
                if "forecast" in event and event["forecast"] not in (None, ''):
                    forecast = event["forecast"]
                elif "forecastRaw" in event and event["forecastRaw"] not in (None, ''):
                    forecast = event["forecastRaw"]
                
                actual = None
                if "actual" in event and event["actual"] not in (None, ''):
                    actual = event["actual"]
                elif "actualRaw" in event and event["actualRaw"] not in (None, ''):
                    actual = event["actualRaw"]
                
                # Add values to the event line
                if previous is not None:
                    values.append(f"Prev: {previous}")
                if forecast is not None:
                    values.append(f"Fcst: {forecast}")
                if actual is not None:
                    values.append(f"Act: {actual}")
                    
                if values:
                    event_line += f" ({', '.join(values)})"
                    
                message += event_line + "\n"
                event_counts["valid"] += 1
                
            except Exception as e:
                logger.error(f"Error formatting event {i+1}: {str(e)}")
                try:
                    logger.error(f"Problematic event: {json.dumps(event, default=str)}")
                except:
                    logger.error("Could not log problematic event - serialization error")
                event_counts["missing_fields"] += 1
                continue
        
        # Add spacing between countries
        message += "\n"
    
    if event_counts["valid"] == 0:
        logger.warning("No valid events to display in calendar")
        message += "No valid economic events found for today.\n"
    
    # Log event counts
    logger.info(f"Telegram formatting: {event_counts['valid']} valid events, {event_counts['highlighted']} highlighted events, {event_counts['missing_fields']} skipped due to missing fields")
    logger.info(f"Final message length: {len(message)} characters")
    
    return message

async def main():
    """Test the TradingView calendar service"""
    # Create the service
    service = TradingViewCalendarService()
    
    # Get calendar data
    calendar_data = await service.get_calendar(days_ahead=3)
    
    # Print the results
    logger.info(f"Got {len(calendar_data)} events from TradingView")
    print(json.dumps(calendar_data, indent=2))
    
    # Format the events for Telegram
    telegram_message = await format_calendar_for_telegram(calendar_data)
    print("\nTelegram Message Format:")
    print(telegram_message)

if __name__ == "__main__":
    asyncio.run(main()) 
