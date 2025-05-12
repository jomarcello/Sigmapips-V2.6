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
        
        # Check ScrapingAnt configuratie
        self.use_scrapingant = os.environ.get("USE_SCRAPINGANT", "").lower() in ("true", "1", "yes")
        self.scrapingant_api_key = os.environ.get("SCRAPINGANT_API_KEY", "")
        
        # Log ScrapingAnt configuratie
        if self.use_scrapingant:
            if self.scrapingant_api_key:
                masked_key = f"{self.scrapingant_api_key[:5]}...{self.scrapingant_api_key[-3:]}" if len(self.scrapingant_api_key) > 8 else "[masked]"
                logger.info(f"ScrapingAnt is enabled with API key: {masked_key}")
            else:
                logger.warning("ScrapingAnt is enabled but no API key is set")
        else:
            logger.info("ScrapingAnt is disabled, using direct API access")
            
        # ScrapingAnt API endpoint
        self.scrapingant_url = "https://api.scrapingant.com/v2/general"
        
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
            
            # Add headers for better API compatibility - moderne user-agent en headers
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
            
            # Controleer of we ScrapingAnt moeten gebruiken
            if self.use_scrapingant and self.scrapingant_api_key:
                logger.info("Using ScrapingAnt for API health check")
                try:
                    # Gebruik de ScrapingAnt proxy voor de TradingView API gezondheidscheck
                    response_text = await self._make_scrapingant_request(self.base_url, params)
                    
                    if response_text and (response_text.strip().startswith('[') or response_text.strip().startswith('{')):
                        logger.info("API health check via ScrapingAnt succeeded")
                        return True
                    else:
                        logger.error("API health check via ScrapingAnt returned invalid data")
                        return False
                except Exception as e:
                    logger.error(f"ScrapingAnt API health check failed: {str(e)}")
                    return False
            
            # Direct API call als ScrapingAnt niet wordt gebruikt
            # Make request to TradingView
            full_url = f"{self.base_url}"
            logger.info(f"Checking API health: {full_url}")
            
            async with self.session.get(full_url, params=params, headers=headers) as response:
                logger.info(f"Health check response status: {response.status}")
                response_text = await response.text()
                logger.info(f"Health check response preview: {response_text[:100]}...")
                
                if response.status == 200:
                    # Dubbel check dat de response daadwerkelijk JSON data bevat
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

    async def _make_scrapingant_request(self, url: str, params: dict) -> str:
        """Make a request using ScrapingAnt proxy service"""
        if not self.scrapingant_api_key:
            logger.error("No ScrapingAnt API key provided")
            return None
        
        logger.info(f"Making ScrapingAnt request to {url}")
        
        # Bouw de volledige URL met query parameters
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"
        
        # Log the full URL for debugging
        logger.info(f"Full URL for ScrapingAnt request: {full_url}")
        
        # Log the API key to verify it's not empty
        masked_key = f"{self.scrapingant_api_key[:5]}...{self.scrapingant_api_key[-3:]}" if len(self.scrapingant_api_key) > 8 else "[masked]"
        logger.info(f"Using ScrapingAnt API key: {masked_key}")
        
        # Bereid ScrapingAnt request parameters voor - zorg dat 'url' correct is
        scrapingant_params = {
            "url": urllib.parse.quote(full_url, safe=''),  # Ensure URL is properly encoded
            "browser": True,
            "return_page_source": True,
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://www.tradingview.com",
                "Referer": "https://www.tradingview.com/economic-calendar/"
            }
        }
        
        # Log de parameters voor debugging (zonder API key)
        logger.info(f"ScrapingAnt parameters: {json.dumps(scrapingant_params, ensure_ascii=False)}")
        
        # Maak request naar ScrapingAnt
        await self._ensure_session()
        try:
            # According to ScrapingAnt docs, the API key should be passed as a query parameter
            # Add API key to the URL as a query parameter
            scrapingant_url_with_key = f"{self.scrapingant_url}?x-api-key={self.scrapingant_api_key}"
            
            # Validate the JSON request body before sending
            try:
                # Ensure the request body is valid JSON
                request_json = json.dumps(scrapingant_params)
                json.loads(request_json)  # Validate JSON
                logger.info("ScrapingAnt request body validated as valid JSON")
            except json.JSONDecodeError as je:
                logger.error(f"Invalid JSON in ScrapingAnt request body: {je}")
                return None
            
            async with self.session.post(
                scrapingant_url_with_key,
                json=scrapingant_params,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                logger.info(f"ScrapingAnt response status: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"ScrapingAnt error: {error_text[:200]}")
                    return None
                    
                response_data = await response.json()
                
                # Controleer of we een text of html response hebben
                if "text" in response_data:
                    logger.info("ScrapingAnt returned text content")
                    return response_data["text"]
                elif "html" in response_data:
                    logger.info("ScrapingAnt returned HTML content")
                    return response_data["html"]
                else:
                    logger.error("ScrapingAnt response doesn't contain text or HTML")
                    logger.error(f"Response keys: {list(response_data.keys())}")
                    return None
        
        except Exception as e:
            logger.error(f"Error making ScrapingAnt request: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    async def get_calendar(self, days_ahead: int = 0, min_impact: str = "Low", currency: str = None) -> List[Dict[str, Any]]:
        """
        Fetch calendar events from TradingView
        
        Args:
            days_ahead: Number of days to look ahead (0 = today only, 1 = today + tomorrow, etc.)
            min_impact: Minimum impact level to include (Low, Medium, High)
            currency: Optional currency to filter events by
            
        Returns:
            List of calendar events
        """
        try:
            logger.info(f"Getting calendar data (days_ahead={days_ahead}, min_impact={min_impact}, currency={currency})")
            
            # First check if the API is healthy
            is_healthy = await self._check_api_health()
            if not is_healthy:
                logger.warning("API health check failed, using fallback data")
                return self._generate_fallback_events(currency)
            
            await self._ensure_session()
            
            # Calculate date range - start from current time (not midnight)
            # This is crucial for getting today's events that haven't happened yet
            current_time = datetime.now()
            
            # For today's data, start from 8 hours ago to make sure we get all of today's events
            # This ensures we don't miss events that happened earlier today
            start_date = current_time - timedelta(hours=8)
            end_date = current_time + timedelta(days=days_ahead)
            
            logger.info(f"Date range: {start_date.isoformat()} to {end_date.isoformat()}")
            
            # Map major currencies to country codes for API request
            currency_to_country = {
                'USD': 'US',
                'EUR': 'EU',
                'GBP': 'GB',
                'JPY': 'JP',
                'CHF': 'CH',
                'AUD': 'AU',
                'NZD': 'NZ',
                'CAD': 'CA'
            }
            
            # Prepare request parameters
            params = {
                'from': self._format_date(start_date),
                'to': self._format_date(end_date),
                'limit': 1000  # Increased limit to ensure we get all events
            }
            
            # Filter by specific currency if provided
            if currency and currency in currency_to_country:
                params['countries'] = currency_to_country[currency]
                logger.info(f"Filtering by currency: {currency} (country code: {params['countries']})")
            elif currency:
                logger.warning(f"Currency {currency} not found in mapping, using all major currencies")
            
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
            
            # Determine whether to use ScrapingAnt or direct API access
            if self.use_scrapingant and self.scrapingant_api_key:
                logger.info("Using ScrapingAnt for calendar data")
                try:
                    # Use ScrapingAnt proxy for TradingView API
                    response_text = await self._make_scrapingant_request(self.base_url, params)
                    
                    if not response_text:
                        logger.error("Empty response from ScrapingAnt")
                        return self._generate_fallback_events(currency)
                        
                    # Process response
                    events = await self._process_response_text(response_text, min_impact, currency)
                    
                    # Update last successful call timestamp
                    self.last_successful_call = datetime.now()
                    
                    return events
                    
                except Exception as e:
                    logger.error(f"ScrapingAnt request failed: {str(e)}")
                    return self._generate_fallback_events(currency)
            
            # Direct API call if ScrapingAnt is not used
            logger.info(f"Making direct API request to: {self.base_url}")
            
            # Use a longer timeout to prevent hanging
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with self.session.get(self.base_url, params=params, headers=headers, timeout=timeout) as response:
                logger.info(f"Got response with status: {response.status}")
                
                if response.status != 200:
                    logger.error(f"Error response from TradingView (status {response.status})")
                    return self._generate_fallback_events(currency)
                    
                # Process response
                response_text = await response.text()
                
                # Check if the API returns valid JSON response
                if not response_text or not (response_text.strip().startswith('[') or response_text.strip().startswith('{')):
                    logger.error("API returned invalid or empty response")
                    return self._generate_fallback_events(currency)
                
                # Process response
                events = await self._process_response_text(response_text, min_impact, currency)
                
                # Update last successful call timestamp
                self.last_successful_call = datetime.now()
                
                return events
                
        except Exception as e:
            logger.error(f"Error in get_calendar: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self._generate_fallback_events(currency)
        finally:
            # Don't close the session here as it might be reused
            pass

    def _generate_fallback_events(self, currency=None) -> List[Dict]:
        """Generate fallback economic events based on day of week"""
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
        
        # If currency is specified, only include that currency's events
        if currency and currency not in active_currencies:
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
        
        # Add events for active currencies
        for curr in active_currencies:
            if curr in currency_events:
                for event_info in currency_events[curr]:
                    event = {
                        "country": curr,
                        "time": event_info["time"],
                        "event": event_info["event"],
                        "impact": event_info["impact"]
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
        """
        Process the API response text and extract calendar events
        
        Args:
            response_text: The raw API response text
            min_impact: Minimum impact level to include
            currency: Optional currency to filter events by
            
        Returns:
            List of processed calendar events
        """
        events = []
        
        try:
            # Parse de JSON-respons
            data = json.loads(response_text)
            
            # Debug logging to see the actual structure
            logger.info(f"API Response Type: {type(data)}")
            logger.info(f"API Response Keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}")
            logger.info(f"API Response Sample: {str(data)[:500]}...")
            
            # Check of de response de juiste structuur heeft - Updated for new API response format
            if isinstance(data, dict) and 'result' in data:
                # The TradingView API now returns a 'result' key containing the events
                items = data.get('result', [])
                logger.info(f"Found events in 'result' key: {len(items)} items")
            elif isinstance(data, dict) and 'data' in data:
                # Keep backward compatibility with old format
                items = data.get('data', [])
                logger.info(f"Found events in 'data' key: {len(items)} items")
            elif isinstance(data, list):
                # Direct list of events
                items = data
                logger.info(f"Found events in direct list: {len(items)} items")
            else:
                logger.warning(f"Unexpected response format: {type(data)}")
                # Try to extract data from the actual structure
                if isinstance(data, dict):
                    # Check for common keys that might contain events
                    for potential_key in ['events', 'items', 'calendar', 'result']:
                        if potential_key in data and isinstance(data[potential_key], list):
                            items = data[potential_key]
                            logger.info(f"Found events in key: {potential_key}")
                            break
                    else:
                        # If no known keys, try the first list value we find
                        for key, value in data.items():
                            if isinstance(value, list) and value:
                                items = value
                                logger.info(f"Using list from key: {key}")
                                break
                        else:
                            logger.error("Could not find any suitable list in response")
                            return []
                else:
                    return []
            
            if not items:
                logger.warning("No events found in the response")
                return []
            
            logger.info(f"Found {len(items)} raw events in the response")
            
            # Map impact levels to numeric values for comparison
            impact_levels = {
                "Low": 1,
                "Medium": 2,
                "High": 3
            }
            min_impact_value = impact_levels.get(min_impact, 1)
            
            # Verwerk elk event
            for item in items:
                try:
                    # Debug log the item structure
                    logger.info(f"Event item structure: {item.keys() if isinstance(item, dict) else 'Not a dict'}")
                    
                    # Extract relevante informatie
                    country_code = item.get('country')
                    if not country_code:
                        continue
                    
                    # Controleer op valutafilter
                    if currency and country_code != currency:
                        continue
                    
                    # Extract tijd en datum
                    event_time = item.get('date', '')
                    if not event_time:
                        continue
                    
                    # Extraheert de tijdinformatie
                    try:
                        event_datetime = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                        event_time_str = event_datetime.strftime('%H:%M')
                    except Exception as e:
                        logger.warning(f"Failed to parse event time '{event_time}': {e}")
                        event_time_str = "00:00"  # Standaard tijd als parsing faalt
                    
                    # Extraheert impact level
                    impact = item.get('importance', 'Low')
                    if isinstance(impact, int):
                        # Convert numeric impact to string
                        impact = {1: "Low", 2: "Medium", 3: "High"}.get(impact, "Low")
                    
                    # Filter op basis van impact
                    impact_value = impact_levels.get(impact, 0)
                    if impact_value < min_impact_value:
                        continue
                    
                    # Extract event title - First try 'title' field, then fall back to 'indicator'
                    event_title = 'Unknown Event'
                    if 'title' in item and item['title']:
                        event_title = item['title']
                    elif 'indicator' in item and item['indicator']:
                        event_title = item['indicator']
                    
                    # Create event object
                    event = {
                        "country": country_code,
                        "time": event_time_str,
                        "event": event_title,
                        "impact": impact,
                        "forecast": item.get('forecast', ''),
                        "previous": item.get('previous', ''),
                        "actual": item.get('actual', '')
                    }
                    
                    # Voeg event toe aan de lijst
                    events.append(event)
                    
                except Exception as e:
                    logger.warning(f"Error processing event: {e}")
                    continue
            
            # Sorteer events op tijd
            events.sort(key=lambda x: x["time"])
            
            logger.info(f"Processed {len(events)} events after filtering")
            return events
            
        except json.JSONDecodeError:
            logger.error("Failed to parse response as JSON")
            logger.debug(f"Invalid JSON response: {response_text[:200]}...")
            return []
        except Exception as e:
            logger.error(f"Error in processing response text: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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
            "scrapingant_enabled": self.use_scrapingant,
            "scrapingant_api_key_set": bool(self.scrapingant_api_key)
        }
        
        try:
            # Log alle configuratie en omgevingsvariabelen
            logger.info("Environment variables:")
            logger.info(f"- USE_SCRAPINGANT: {os.environ.get('USE_SCRAPINGANT', 'not set')}")
            logger.info(f"- USE_CALENDAR_FALLBACK: {os.environ.get('USE_CALENDAR_FALLBACK', 'not set')}")
            if self.scrapingant_api_key:
                masked_key = f"{self.scrapingant_api_key[:5]}...{self.scrapingant_api_key[-3:]}" if len(self.scrapingant_api_key) > 8 else "[masked]"
                logger.info(f"- SCRAPINGANT_API_KEY: {masked_key}")
            else:
                logger.info("- SCRAPINGANT_API_KEY: not set")
            
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
                if self.use_scrapingant and self.scrapingant_api_key:
                    logger.info("API health check failed, trying ScrapingAnt directly")
                    
                    try:
                        # Voer direct een ScrapingAnt request uit
                        start_date = datetime.now()
                        end_date = start_date + timedelta(days=1)
                        
                        params = {
                            'from': self._format_date(start_date),
                            'to': self._format_date(end_date),
                            'countries': 'US,EU,GB,JP,CH,AU,NZ,CA',
                            'limit': 10  # Beperkt aantal voor debug
                        }
                        
                        response_text = await self._make_scrapingant_request(self.base_url, params)
                        if response_text:
                            debug_info["scrapingant_response"] = response_text[:200] + "..."  # Eerste 200 tekens
                            
                            # Verwerk de respons als die er goed uitziet
                            if response_text.strip().startswith('[') or response_text.strip().startswith('{'):
                                events = await self._process_response_text(response_text, "Low", None)
                                debug_info["scrapingant_events_retrieved"] = len(events)
                                debug_info["scrapingant_sample_events"] = events[:3] if events else []
                    except Exception as e:
                        logger.error(f"Error during ScrapingAnt debug request: {str(e)}")
                        debug_info["scrapingant_error"] = str(e)
            
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
        """
        Fetch and format economic calendar events for multiple currencies
        
        Args:
            currencies: List of currency codes to filter events by (e.g. ["EUR", "USD"])
            days_ahead: Number of days to look ahead
            min_impact: Minimum impact level to include (Low, Medium, High)
            
        Returns:
            Formatted HTML string with calendar data
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
            return "<b>📅 Economic Calendar</b>\n\nSorry, there was an error retrieving the economic calendar data."

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
    
    # Log all events to help diagnose issues
    logger.info(f"Events to format: {json.dumps(events[:5], indent=2)}")
    
    # Sort events by time if not already sorted
    try:
        # Verbeterde sortering met datetime objecten
        def parse_time_for_sorting(event):
            time_str = event.get("time", "00:00")
            try:
                if ":" in time_str:
                    hours, minutes = time_str.split(":")
                    # Strip any AM/PM/timezone indicators
                    hours = hours.strip()
                    if " " in minutes:
                        minutes = minutes.split(" ")[0]
                    return int(hours) * 60 + int(minutes)
                return 0
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
    
    # Group events by country for better readability
    events_by_country = {}
    for event in sorted_events:
        country = event.get("country", "")
        if country not in events_by_country:
            events_by_country[country] = []
        events_by_country[country].append(event)
    
    # Display events grouped by country
    for country, country_events in events_by_country.items():
        # Add country header
        message += f" {country}\n"
        
        # Add events for this country
        for i, event in enumerate(country_events):
            try:
                time = event.get("time", "")
                title = event.get("event", "")
                impact = event.get("impact", "Low")
                impact_emoji = impact_emoji_map.get(impact, "🟢")
                
                # Check if this event is highlighted (specific to the requested currency)
                is_highlighted = event.get("highlighted", False)
                if is_highlighted:
                    event_counts["highlighted"] += 1
                
                # Log each event being processed for debugging
                if i < 5:
                    logger.debug(f"Processing event {i+1} for {country}: {json.dumps(event)}")
                
                # Controleer of alle benodigde velden aanwezig zijn
                if not time or not title:
                    missing = []
                    if not time: missing.append("time") 
                    if not title: missing.append("event")
                    
                    logger.warning(f"Event {i+1} missing fields: {', '.join(missing)}: {json.dumps(event)}")
                    event_counts["missing_fields"] += 1
                    continue
                
                # Format the line with enhanced visibility
                event_line = f"{time} - {impact_emoji} {title}"
                
                # Add previous/forecast/actual values if available
                values = []
                if "previous" in event and event["previous"] is not None:
                    values.append(f"{event['previous']}")
                if "forecast" in event and event["forecast"] is not None:
                    values.append(f"Fcst: {event['forecast']}")
                if "actual" in event and event["actual"] is not None:
                    values.append(f"Act: {event['actual']}")
                    
                if values:
                    event_line += f" ({', '.join(values)})"
                    
                message += event_line + "\n"
                event_counts["valid"] += 1
                
            except Exception as e:
                logger.error(f"Error formatting event {i+1}: {str(e)}")
                logger.error(f"Problematic event: {json.dumps(event)}")
                continue
    
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
