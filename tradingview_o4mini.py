#!/usr/bin/env python3
"""
TradingView Economic Calendar met OpenAI o4-mini integratie

Deze module haalt economische kalendergegevens op van TradingView en gebruikt
OpenAI's o4-mini model om de gegevens te verwerken en te formatteren.
"""

import os
import sys
import json
import asyncio
import logging
import aiohttp
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Controleer of OpenAI API key is ingesteld
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.warning("⚠️ OPENAI_API_KEY environment variable is not set")
    print("⚠️ OPENAI_API_KEY environment variable is not set")
    print("Please set it with: export OPENAI_API_KEY=your_api_key")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Map van belangrijke valuta's naar landcodes voor TradingView API
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
}

# Impact levels en emoji's
IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
    "Low": "🟢"
}

# Definieer de major currencies die we altijd willen tonen
MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]

class TradingViewO4MiniCalendarService:
    """Service voor het ophalen van economische kalendergegevens met OpenAI o4-mini"""
    
    def __init__(self):
        # TradingView calendar API endpoint
        self.base_url = "https://economic-calendar.tradingview.com/events"
        self.session = None
        
        # Force OpenAI o4-mini to be enabled
        self.use_o4mini = True
        if not OPENAI_API_KEY:
            logger.warning("OpenAI o4-mini is enabled but no API key is set")
            self.use_o4mini = False
        
        if self.use_o4mini:
            logger.info("OpenAI o4-mini is enabled for economic calendar data")
            print("✅ OpenAI o4-mini is enabled for economic calendar data")
        else:
            logger.info("OpenAI o4-mini is disabled, using direct API access")
            print("⚠️ OpenAI o4-mini is disabled, using direct API access")
    
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
    
    async def get_calendar(self, days_ahead: int = 0, min_impact: str = "Low", currency: str = None, all_currencies: bool = False) -> List[Dict[str, Any]]:
        """Get economic calendar data
        
        Args:
            days_ahead: Number of days to look ahead
            min_impact: Minimum impact level to include (Low, Medium, High)
            currency: Optional currency to filter events by
            all_currencies: If True, show all currencies, otherwise only major currencies
            
        Returns:
            List of calendar events
        """
        logger.info(f"Getting calendar data (days_ahead={days_ahead}, min_impact={min_impact}, currency={currency}, all_currencies={all_currencies})")
        
        try:
            await self._ensure_session()
            
            # Calculate date range
            current_time = datetime.now()
            from_date = current_time
            to_date = current_time + timedelta(days=days_ahead+1)
            
            # Set up API parameters
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
            logger.info(f"Making API request to: {full_url}")
            
            async with self.session.get(full_url, params=params, headers=headers) as response:
                logger.info(f"API response status: {response.status}")
                
                if response.status == 200:
                    response_text = await response.text()
                    
                    # Check if the response is valid JSON
                    if response_text.strip().startswith('[') or response_text.strip().startswith('{'):
                        logger.info("Successfully retrieved data from TradingView API")
                        
                        # Process the response
                        events = await self._process_response(response_text, min_impact, currency)
                        logger.info(f"Processed {len(events)} events from TradingView API")
                        
                        # If we have o4-mini enabled, enhance the data
                        if self.use_o4mini and events:
                            events = await self._enhance_with_o4mini(events)
                        
                        return events
                    else:
                        logger.error("API returned 200 but not valid JSON")
                        logger.error(f"First 200 chars of response: {response_text[:200]}")
                        # Fall back to generating mock data
                        return await self._generate_fallback_events(currency, all_currencies)
                else:
                    logger.error(f"API request failed with status {response.status}")
                    # Fall back to generating mock data
                    return await self._generate_fallback_events(currency, all_currencies)
                    
        except Exception as e:
            logger.error(f"Error getting calendar data: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Fall back to generating mock data
            return await self._generate_fallback_events(currency, all_currencies)
    
    async def _process_response(self, response_text: str, min_impact: str = "Low", currency: str = None) -> List[Dict[str, Any]]:
        """Process the API response and extract calendar events
        
        Args:
            response_text: JSON response from the API
            min_impact: Minimum impact level to include
            currency: Optional currency to filter events by
            
        Returns:
            List of processed calendar events
        """
        try:
            # Parse the JSON response
            data = json.loads(response_text)
            
            # Debug logging to see the actual structure
            logger.info(f"API Response Type: {type(data)}")
            if isinstance(data, dict):
                logger.info(f"API Response Keys: {list(data.keys())}")
            
            # Check if the response has the correct structure
            items = []
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
            
            # Impact level mapping
            impact_levels = {
                "Low": 1,
                "Medium": 2,
                "High": 3
            }
            
            min_impact_level = impact_levels.get(min_impact, 1)
            
            # Get today's date for filtering
            today = datetime.now().date()
            logger.info(f"Filtering events for today's date: {today}")
            
            # Process each event
            events = []
            for item in items:
                try:
                    # Check if item is a dictionary
                    if not isinstance(item, dict):
                        logger.warning(f"Item is not a dictionary: {type(item)}")
                        continue
                        
                    # Extract event details
                    event_time = item.get('date', '')
                    event_country = item.get('country', '')
                    event_currency = self._country_to_currency(event_country)
                    event_title = item.get('title', '')
                    event_importance = item.get('importance', 0)
                    
                    # Skip if not a major currency
                    if event_currency not in MAJOR_CURRENCIES:
                        continue
                    
                    # Map importance to impact level
                    impact = "Low"
                    if event_importance >= 3:
                        impact = "High"
                    elif event_importance >= 2:
                        impact = "Medium"
                    
                    # Skip if below minimum impact level
                    if impact_levels.get(impact, 0) < min_impact_level:
                        continue
                    
                    # Apply currency filter if provided
                    if currency and event_currency != currency:
                        continue
                    
                    # Parse the event date to check if it's today
                    try:
                        event_datetime = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                        event_date = event_datetime.date()
                        
                        # Skip if not today
                        if event_date != today:
                            continue
                    except Exception as e:
                        logger.warning(f"Error parsing event date: {str(e)}")
                        # If we can't parse the date, include it anyway
                    
                    # Format time
                    time_str = self._format_event_time(event_time)
                    
                    # Create formatted event
                    formatted_event = {
                        "time": time_str,
                        "country": event_country,
                        "currency": event_currency,
                        "event": event_title,
                        "impact": impact,
                        "impact_emoji": IMPACT_EMOJI.get(impact, "🟢"),
                        "forecast": item.get('forecast', ''),
                        "previous": item.get('previous', ''),
                        "actual": item.get('actual', ''),
                        "datetime": event_time
                    }
                    
                    events.append(formatted_event)
                except Exception as e:
                    logger.warning(f"Error processing event: {str(e)}")
                    continue
            
            # Sort events by time
            events.sort(key=lambda x: x.get("datetime", ""))
            
            logger.info(f"Processed {len(events)} events from TradingView API (filtered for major currencies and today's date)")
            return events
            
        except Exception as e:
            logger.error(f"Error processing API response: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def _country_to_currency(self, country: str) -> str:
        """Convert country code to currency code"""
        # Reverse mapping from country to currency
        for currency, country_code in CURRENCY_COUNTRY_MAP.items():
            if country_code == country:
                return currency
        return country
    
    def _format_event_time(self, datetime_str: str) -> str:
        """Format event time for display"""
        try:
            # Parse ISO datetime string
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            
            # Format as HH:MM
            return dt.strftime("%H:%M")
        except Exception:
            return datetime_str
    
    async def _enhance_with_o4mini(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhance calendar events with OpenAI o4-mini
        
        Args:
            events: List of calendar events
            
        Returns:
            Enhanced list of calendar events
        """
        if not events:
            return events
        
        try:
            logger.info("Enhancing calendar events with OpenAI o4-mini...")
            
            # Format events for the prompt
            events_text = ""
            for i, event in enumerate(events):
                events_text += f"Event {i+1}:\n"
                events_text += f"Time: {event.get('time', 'N/A')}\n"
                events_text += f"Currency: {event.get('currency', 'N/A')}\n"
                events_text += f"Country: {event.get('country', 'N/A')}\n"
                events_text += f"Impact: {event.get('impact', 'N/A')}\n"
                events_text += f"Event: {event.get('event', 'N/A')}\n"
                events_text += f"Forecast: {event.get('forecast', 'N/A')}\n"
                events_text += f"Previous: {event.get('previous', 'N/A')}\n"
                events_text += f"Actual: {event.get('actual', 'N/A')}\n"
                events_text += "---\n"
            
            # Create the prompt for o4-mini
            prompt = f"""
            Here is a list of economic calendar events:
            
            {events_text}
            
            For each event, please provide:
            1. A brief description of what the event means
            2. The potential market impact (how it might affect the currency)
            3. What traders should watch for
            
            Format your response as a JSON array with the following structure for each event:
            [
                {{
                    "event_index": 0,  // Index of the event in the original list
                    "description": "Brief description of what this economic indicator means",
                    "market_impact": "How this event might impact the market",
                    "watch_for": "What traders should watch for with this event"
                }},
                // More events...
            ]
            
            Only include the JSON array in your response, nothing else.
            """
            
            # Call OpenAI API
            response = client.chat.completions.create(
                model="o4-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful economic calendar analyst for forex traders."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=2000
            )
            
            # Process the response
            if response and hasattr(response, 'choices') and len(response.choices) > 0:
                content = response.choices[0].message.content
                
                try:
                    # Extract JSON array from response
                    json_match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        enhancements = json.loads(json_str)
                    else:
                        enhancements = json.loads(content)
                    
                    # Add enhancements to original events
                    for enhancement in enhancements:
                        event_index = enhancement.get('event_index', 0)
                        if 0 <= event_index < len(events):
                            events[event_index]['description'] = enhancement.get('description', '')
                            events[event_index]['market_impact'] = enhancement.get('market_impact', '')
                            events[event_index]['watch_for'] = enhancement.get('watch_for', '')
                    
                    logger.info("Successfully enhanced calendar events with OpenAI o4-mini")
                    
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON response from OpenAI")
                    logger.error(f"Response content: {content}")
            
            return events
            
        except Exception as e:
            logger.error(f"Error enhancing calendar events with OpenAI o4-mini: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return events
    
    async def _generate_fallback_events(self, currency=None, all_currencies: bool = False) -> List[Dict]:
        """Generate fallback economic events when API fails
        
        Args:
            currency: Optional currency to filter events by
            all_currencies: If True, show all currencies, otherwise only major currencies
            
        Returns:
            List of fallback calendar events
        """
        logger.info("Generating fallback economic events")
        
        # Get current time
        current_time = datetime.now()
        current_hour = current_time.hour
        
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
            "NZD": [
                {"time": f"{(current_hour + 1) % 24:02d}:45", "event": "RBNZ Interest Rate Decision", "impact": "High"},
                {"time": f"{(current_hour + 3) % 24:02d}:00", "event": "GDP", "impact": "Medium"}
            ],
            "CAD": [
                {"time": f"{(current_hour + 2) % 24:02d}:30", "event": "BOC Interest Rate Decision", "impact": "High"},
                {"time": f"{(current_hour + 4) % 24:02d}:15", "event": "Employment Change", "impact": "Medium"}
            ]
        }
        
        # Filter by currency if provided
        if currency:
            if currency in currency_events:
                selected_currencies = [currency]
            else:
                # If currency not found, return empty list
                return []
        else:
            # Use all major currencies or all currencies based on parameter
            if all_currencies:
                selected_currencies = list(currency_events.keys())
            else:
                selected_currencies = MAJOR_CURRENCIES
        
        # Generate events
        events = []
        for curr in selected_currencies:
            if curr in currency_events:
                for event_data in currency_events[curr]:
                    event = {
                        "time": event_data["time"],
                        "country": CURRENCY_COUNTRY_MAP.get(curr, curr),
                        "currency": curr,
                        "event": event_data["event"],
                        "impact": event_data["impact"],
                        "impact_emoji": IMPACT_EMOJI.get(event_data["impact"], "🟢"),
                        "forecast": "",
                        "previous": "",
                        "actual": "",
                        "is_fallback": True
                    }
                    events.append(event)
        
        # Sort events by time
        events.sort(key=lambda x: x["time"])
        
        logger.info(f"Generated {len(events)} fallback events")
        return events
    
    async def format_calendar_for_display(self, events: List[Dict], group_by_currency: bool = False) -> str:
        """Format calendar events for display
        
        Args:
            events: List of calendar events
            group_by_currency: Whether to group events by currency
            
        Returns:
            Formatted calendar string
        """
        if not events:
            return "No economic events found for the selected period."
        
        # Format the header
        today = datetime.now().strftime("%A, %d %B %Y")
        header = f"📅 <b>Economic Calendar for {today}</b>\n\n"
        header += "Impact: 🔴 High   🟠 Medium   🟢 Low\n\n"
        
        if group_by_currency:
            # Group events by currency
            events_by_currency = {}
            for event in events:
                currency = event.get("currency", "")
                if currency not in events_by_currency:
                    events_by_currency[currency] = []
                events_by_currency[currency].append(event)
            
            # Format events by currency
            output = header
            for currency in sorted(events_by_currency.keys()):
                output += f"<b>{currency}</b>:\n"
                
                for event in sorted(events_by_currency[currency], key=lambda x: x.get("time", "")):
                    time = event.get("time", "")
                    name = event.get("event", "")
                    impact_emoji = event.get("impact_emoji", "🟢")
                    
                    # Format event line
                    event_line = f"{time} - {impact_emoji} {name}"
                    
                    # Add values if available
                    values = []
                    if event.get("previous"):
                        values.append(f"P: {event['previous']}")
                    if event.get("forecast"):
                        values.append(f"F: {event['forecast']}")
                    if event.get("actual"):
                        values.append(f"A: {event['actual']}")
                    
                    if values:
                        event_line += f" ({', '.join(values)})"
                    
                    # Add fallback indicator if applicable
                    if event.get("is_fallback", False):
                        event_line += " [Est]"
                    
                    output += event_line + "\n"
                
                output += "\n"
        else:
            # Format events chronologically
            output = header
            for event in sorted(events, key=lambda x: x.get("time", "")):
                time = event.get("time", "")
                currency = event.get("currency", "")
                name = event.get("event", "")
                impact_emoji = event.get("impact_emoji", "🟢")
                
                # Format event line
                event_line = f"{time} - {currency} - {impact_emoji} {name}"
                
                # Add values if available
                values = []
                if event.get("previous"):
                    values.append(f"P: {event['previous']}")
                if event.get("forecast"):
                    values.append(f"F: {event['forecast']}")
                if event.get("actual"):
                    values.append(f"A: {event['actual']}")
                
                if values:
                    event_line += f" ({', '.join(values)})"
                
                # Add fallback indicator if applicable
                if event.get("is_fallback", False):
                    event_line += " [Est]"
                
                # Add enhanced information if available
                if event.get("description") or event.get("market_impact") or event.get("watch_for"):
                    event_line += "\n"
                    if event.get("description"):
                        event_line += f"  • <i>{event['description']}</i>\n"
                    if event.get("market_impact"):
                        event_line += f"  • <i>Impact: {event['market_impact']}</i>\n"
                    if event.get("watch_for"):
                        event_line += f"  • <i>Watch for: {event['watch_for']}</i>\n"
                
                output += event_line + "\n\n"
        
        return output

async def main():
    """Test the TradingView calendar service"""
    service = TradingViewO4MiniCalendarService()
    
    try:
        # Get calendar data
        print("Getting calendar data for today (major currencies only)...")
        events = await service.get_calendar(days_ahead=0, min_impact="Low", all_currencies=False)
        print(f"Retrieved {len(events)} calendar events")
        
        # Format the calendar
        print("\nFormatting calendar chronologically...")
        chronological = await service.format_calendar_for_display(events, group_by_currency=False)
        print(chronological)
        
        print("\nFormatting calendar by currency...")
        by_currency = await service.format_calendar_for_display(events, group_by_currency=True)
        print(by_currency)
    
    finally:
        # Close the session
        await service._close_session()

if __name__ == "__main__":
    asyncio.run(main()) 