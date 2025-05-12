import os
import sys
import logging
import asyncio
import json
import subprocess
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import pytz

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Currency flag emoji mapping
CURRENCY_FLAGS = {
    "USD": "🇺🇸",
    "EUR": "🇪🇺",
    "GBP": "🇬🇧",
    "JPY": "🇯🇵",
    "CHF": "🇨🇭",
    "AUD": "🇦🇺",
    "NZD": "🇳🇿",
    "CAD": "🇨🇦",
    "CNY": "🇨🇳",
    "HKD": "🇭🇰",
}

# Impact levels and their emoji representations
IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
    "Low": "🟡"
}

# Major currencies
MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]

class ForexFactoryCalendarService:
    """Service for retrieving calendar data from ForexFactory using the get_today_events.py script"""
    
    def __init__(self):
        self.base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.script_path = os.path.join(self.base_path, "get_today_events.py")
        
        # Check if the script exists
        if not os.path.exists(self.script_path):
            logger.error(f"ForexFactory calendar script not found at {self.script_path}")
            raise FileNotFoundError(f"ForexFactory calendar script not found at {self.script_path}")
        
        self.singapore_tz = pytz.timezone('Asia/Singapore')  # GMT+8
        logger.info("ForexFactory Calendar Service initialized")
    
    async def get_calendar(self, days_ahead: int = 0, min_impact: str = "Low", currency: str = None) -> List[Dict[str, Any]]:
        """Get economic calendar data from ForexFactory
        
        Args:
            days_ahead: Number of days to look ahead
            min_impact: Minimum impact level to include (Low, Medium, High)
            currency: Optional currency to filter events by
            
        Returns:
            List of calendar events
        """
        logger.info(f"Getting calendar data (days_ahead={days_ahead}, min_impact={min_impact}, currency={currency})")
        
        try:
            # Calculate the target date
            current_time = datetime.now(self.singapore_tz)
            target_date = current_time + timedelta(days=days_ahead)
            date_str = target_date.strftime("%Y-%m-%d")
            
            # Determine the JSON file path
            json_file = os.path.join(self.base_path, f"forex_factory_data_{date_str}.json")
            
            # If the file doesn't exist or is older than 1 hour, run the script
            should_refresh = not os.path.exists(json_file)
            if not should_refresh:
                file_time = datetime.fromtimestamp(os.path.getmtime(json_file), self.singapore_tz)
                if (current_time - file_time).total_seconds() > 3600:  # 1 hour
                    should_refresh = True
            
            if should_refresh:
                logger.info(f"Running ForexFactory calendar script for date {date_str}")
                # Run the script to fetch fresh data
                process = await asyncio.create_subprocess_exec(
                    "python",
                    self.script_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    logger.error(f"Failed to run ForexFactory script: {stderr.decode()}")
                    # Try to use existing file if available
                    if not os.path.exists(json_file):
                        return []
            
            # Read the JSON file
            if os.path.exists(json_file):
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                # Process and filter the data
                events = []
                
                # Check if data is a list or a dict with events
                if isinstance(data, list):
                    # Each event is a dictionary in the list
                    raw_events = data
                elif isinstance(data, dict) and 'events' in data:
                    # The data is in the format {"date": "...", "events": [...]}
                    raw_events = data['events']
                else:
                    logger.error(f"Unexpected data format in {json_file}")
                    return []
                
                # Process each event
                for event in raw_events:
                    if not isinstance(event, dict):
                        continue
                        
                    # Convert impact level to standard format
                    impact_level = event.get("impact", "Low")
                    # Handle both string format and emoji format
                    if impact_level == "🔴" or impact_level == "High":
                        impact_level = "High"
                    elif impact_level == "🟠" or impact_level == "Medium":
                        impact_level = "Medium"
                    else:
                        impact_level = "Low"
                    
                    # Check if event meets minimum impact level
                    if (min_impact == "High" and impact_level != "High") or \
                    (min_impact == "Medium" and impact_level == "Low"):
                        continue
                    
                    # Check if event is for the specified currency
                    if currency and event.get("currency", "").upper() != currency.upper():
                        continue
                    
                    # Add the event
                    events.append({
                        "title": event.get("event", ""),
                        "country": event.get("country", ""),
                        "currency": event.get("currency", ""),
                        "importance": impact_level,
                        "impact": IMPACT_EMOJI.get(impact_level, "🟡"),
                        "time": event.get("time", ""),
                        "actual": event.get("actual", ""),
                        "forecast": event.get("forecast", ""),
                        "previous": event.get("previous", ""),
                        "date": target_date.strftime("%Y-%m-%d")
                    })
                
                logger.info(f"Retrieved {len(events)} events from ForexFactory")
                return events
            else:
                logger.error(f"ForexFactory data file not found: {json_file}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting ForexFactory calendar: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def get_economic_calendar(self, currencies: List[str] = None, days_ahead: int = 0, min_impact: str = "Low") -> str:
        """Get formatted economic calendar for display
        
        Args:
            currencies: List of currencies to filter events by
            days_ahead: Number of days to look ahead
            min_impact: Minimum impact level to include (Low, Medium, High)
            
        Returns:
            Formatted calendar string
        """
        logger.info(f"Getting economic calendar (currencies={currencies}, days_ahead={days_ahead}, min_impact={min_impact})")
        
        try:
            # Calculate the target date
            current_time = datetime.now(self.singapore_tz)
            target_date = current_time + timedelta(days=days_ahead)
            date_str = target_date.strftime("%Y-%m-%d")
            
            # Check if we have a text file with pre-formatted output
            text_file = os.path.join(self.base_path, f"forex_factory_events_{date_str}.txt")
            if os.path.exists(text_file):
                with open(text_file, 'r') as f:
                    content = f.read()
                    # Return the content with HTML formatting for Telegram
                    return f"<pre>{content}</pre>"
            
            # If we don't have a pre-formatted file, get events and format them
            events = []
            if currencies and len(currencies) > 0:
                # Fetch events for each currency
                for currency in currencies:
                    currency_events = await self.get_calendar(days_ahead, min_impact, currency)
                    events.extend(currency_events)
            else:
                # Fetch all events
                events = await self.get_calendar(days_ahead, min_impact)
            
            if not events:
                return "No economic events found for the selected criteria."
            
            # Sort events by time
            events.sort(key=lambda x: x.get("time", ""))
            
            # Format the calendar
            date_str = target_date.strftime("%A, %B %d, %Y")
            
            # Format the data ourselves
            output = [f"ForexFactory Economic Calendar for {date_str} (GMT+8)"]
            output.append("=" * 80)
            output.append("")
            
            # Table header
            output.append("| Time     | Currency | Impact | Event                          | Actual   | Forecast  | Previous  |")
            output.append("|----------|----------|--------|--------------------------------|----------|-----------|-----------|")
            
            # Table rows
            for event in events:
                time = event.get("time", "")
                currency = f"{CURRENCY_FLAGS.get(event.get('currency', ''), '')} {event.get('currency', '')}"
                impact = event.get("impact", "")
                title = event.get("title", "")[:30]  # Truncate long titles
                actual = event.get("actual", "")
                forecast = event.get("forecast", "")
                previous = event.get("previous", "")
                
                output.append(f"| {time:<9} | {currency:<8} | {impact:<6} | {title:<30} | {actual:<8} | {forecast:<9} | {previous:<9} |")
            
            # Join with newlines and return
            formatted = "\n".join(output)
            return f"<pre>{formatted}</pre>"
            
        except Exception as e:
            logger.error(f"Error formatting economic calendar: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return "❌ Error generating economic calendar"
    
    async def format_calendar_chronologically(self, events: List[Dict], today_formatted: str = None, group_by_currency: bool = False) -> str:
        """Format calendar events chronologically
        
        This is a compatibility method to match the interface of TradingViewCalendarService
        
        Args:
            events: List of calendar events
            today_formatted: Optional formatted date string
            group_by_currency: Whether to group events by currency
            
        Returns:
            Formatted calendar string
        """
        # Simply use the get_economic_calendar method since our events are already formatted
        return await self.get_economic_calendar()
    
    async def get_instrument_calendar(self, instrument: str, days_ahead: int = 0, min_impact: str = "Low") -> str:
        """Get calendar events for a specific trading instrument
        
        Args:
            instrument: Trading instrument (e.g., EURUSD)
            days_ahead: Number of days to look ahead
            min_impact: Minimum impact level to include
            
        Returns:
            Formatted calendar string
        """
        logger.info(f"Getting calendar for instrument: {instrument}")
        
        # Extract currencies from the instrument
        currencies = []
        if len(instrument) == 6:
            # Forex pair (e.g., EURUSD)
            base = instrument[:3]
            quote = instrument[3:]
            currencies = [base, quote]
        elif instrument in ["XAUUSD", "XAGUSD"]:
            # Gold or silver (just show USD)
            currencies = ["USD"]
        elif instrument in ["US30", "US100", "US500"]:
            # US indices
            currencies = ["USD"]
        elif instrument in ["UK100"]:
            # UK indices
            currencies = ["GBP"]
        elif instrument in ["GER40", "ESP35", "FRA40"]:
            # European indices
            currencies = ["EUR"]
        else:
            # Default to major currencies
            currencies = MAJOR_CURRENCIES
        
        # Get calendar for these currencies
        return await self.get_economic_calendar(currencies, days_ahead, min_impact)

# For testing
async def main():
    service = ForexFactoryCalendarService()
    calendar = await service.get_economic_calendar()
    print(calendar)

if __name__ == "__main__":
    asyncio.run(main()) 