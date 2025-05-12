#!/usr/bin/env python3
"""
Economic Calendar Script for Telegram
Displays economic events for major currencies in UTC+8 timezone
"""

import os
import asyncio
import logging
import json
import aiohttp
from datetime import datetime, timedelta
import pytz
import argparse
import telegram
from telegram.constants import ParseMode
import sys
import html

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Set timezone to UTC+8
UTC_PLUS_8 = pytz.timezone('Asia/Singapore')  # Singapore is UTC+8

# Define major currencies
MAJOR_CURRENCIES = ["US", "EU", "GB", "JP", "CN"]

# Impact emoji mapping
IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
    "Medium-Low": "🟡",
    "Low": "🟢"
}

async def get_tradingview_calendar_events(days_ahead=0):
    """Fetch economic calendar events directly from TradingView
    
    Args:
        days_ahead: Number of days ahead to fetch events (0=today, 1=tomorrow, etc.)
    """
    try:
        # TradingView calendar API endpoint
        base_url = "https://economic-calendar.tradingview.com/events"
        
        # Calculate date range (today or specific day ahead)
        current_time = datetime.now(UTC_PLUS_8)
        
        # If we want events for today, start from now
        # If we want events for a future day, start from 00:00 that day
        if days_ahead == 0:
            from_date = current_time
        else:
            from_date = datetime(
                current_time.year, current_time.month, current_time.day, 
                tzinfo=UTC_PLUS_8
            ) + timedelta(days=days_ahead)
        
        # End date is always the end of the selected day
        to_date = datetime(
            from_date.year, from_date.month, from_date.day, 23, 59, 59,
            tzinfo=UTC_PLUS_8
        ) + timedelta(days=0)
        
        logger.info(f"Fetching economic calendar events for: {from_date.strftime('%Y-%m-%d')}")
        
        # Format date for TradingView API
        def format_date(date):
            # Convert to UTC for API
            utc_date = date.astimezone(pytz.UTC)
            utc_date = utc_date.replace(microsecond=0)
            return utc_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        # Parameters for API request
        params = {
            'from': format_date(from_date),
            'to': format_date(to_date)
        }
        
        logger.debug(f"API request parameters: {params}")
        
        # Headers for better API compatibility
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/economic-calendar/"
        }
        
        # Make API request
        logger.info("Fetching economic calendar data from TradingView...")
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params, headers=headers) as response:
                logger.info(f"API response status: {response.status}")
                
                if response.status == 200:
                    response_text = await response.text()
                    
                    # Check if the response is valid JSON
                    if response_text.strip().startswith('[') or response_text.strip().startswith('{'):
                        logger.info("✅ Successfully fetched data from TradingView API")
                        
                        # Parse the JSON response
                        data = json.loads(response_text)
                        
                        # Process the events
                        events = process_events(data, current_time)
                        return events
                    else:
                        logger.error("API returned 200 but not valid JSON")
                        logger.debug(f"First 200 characters of response: {response_text[:200]}")
                        return []
                else:
                    logger.error(f"API request failed with status {response.status}")
                    return []
    
    except Exception as e:
        logger.error(f"Error fetching calendar data: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def process_events(data, current_time):
    """Process the raw API response into formatted events"""
    events = []
    
    # Check if data is a string (error message)
    if isinstance(data, str):
        logger.error(f"API returned a string instead of JSON data: {data[:100]}...")
        return []
    
    # Check if we have the correct structure
    if isinstance(data, dict) and 'status' in data and data['status'] == 'ok' and 'result' in data:
        logger.info("✅ Correct API structure found with 'result' field")
        items = data['result']
        logger.info(f"Number of items in 'result': {len(items)}")
    else:
        logger.warning("Unexpected API structure, trying to process directly")
        if isinstance(data, list):
            items = data
            logger.info(f"Data is a list with {len(items)} items")
        else:
            logger.warning(f"Data type: {type(data)}")
            logger.warning(f"Data keys (if dict): {data.keys() if isinstance(data, dict) else 'Not applicable'}")
            items = []
    
    # Current time in UTC+8
    current_time_utc8 = current_time
    logger.info(f"Current time (UTC+8): {current_time_utc8.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Process each event
    for i, item in enumerate(items):
        # Skip if item is not a dictionary
        if not isinstance(item, dict):
            logger.warning(f"Item {i} is not a dictionary, but {type(item)}")
            continue
        
        # Show the first item for debugging
        if i == 0 and os.environ.get("DEBUG"):
            logger.debug(f"First item example:")
            logger.debug(json.dumps(item, indent=2)[:500])
        
        # Extract event details
        try:
            event_time_str = item.get('date', '')
            if not event_time_str:
                logger.warning(f"Item {i} has no 'date' field")
                continue
                
            event_country = item.get('country', '')
            event_title = item.get('title', '')
            
            # Parse the event time to UTC+8
            try:
                event_time_utc = datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
                event_time_utc8 = event_time_utc.astimezone(UTC_PLUS_8)
                
                # Skip events that have already passed
                if event_time_utc8 < current_time_utc8:
                    continue
                
                # Determine impact level based on available data
                impact = "Low"
                if 'importance' in item:
                    event_importance = item.get('importance', 0)
                    if event_importance >= 3:
                        impact = "High"
                    elif event_importance >= 2:
                        impact = "Medium"
                    elif event_importance >= 1:
                        impact = "Medium-Low"
                
                # Format time and date
                time_str = event_time_utc8.strftime("%H:%M")
                date_str = event_time_utc8.strftime("%Y-%m-%d")
                
                # Create formatted event
                formatted_event = {
                    "date": date_str,
                    "time": time_str,
                    "country": event_country,
                    "event": event_title,
                    "impact": impact,
                    "forecast": item.get('forecast', ''),
                    "previous": item.get('previous', ''),
                    "actual": item.get('actual', '')
                }
                
                events.append(formatted_event)
            except Exception as e:
                logger.error(f"Error processing event time: {str(e)}")
                continue
        except Exception as e:
            logger.error(f"Error processing event: {str(e)}")
            continue
    
    # Sort events by date and time
    events.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))
    
    return events

def format_events_for_display(events, only_major=True):
    """Format events for display in console or Telegram
    
    Args:
        events: List of events
        only_major: Only show events for major currencies
        
    Returns:
        Tuple of (console_output, telegram_output)
    """
    if not events:
        return "No economic events found.", "No economic events found."
    
    # Filter for major currencies if desired
    if only_major:
        filtered_events = [e for e in events if e.get('country') in MAJOR_CURRENCIES]
    else:
        filtered_events = events
    
    if not filtered_events:
        return "No economic events found for the selected currencies.", "No economic events found for the selected currencies."
    
    # Current time in UTC+8
    current_time_utc8 = datetime.now(UTC_PLUS_8)
    
    # Group events by date
    events_by_date = {}
    for event in filtered_events:
        date_str = event.get('date', '')
        if date_str not in events_by_date:
            events_by_date[date_str] = []
        events_by_date[date_str].append(event)
    
    # Console output
    console_lines = []
    
    # Title
    if only_major:
        console_lines.append(f"\n📅 ECONOMIC EVENTS FOR MAJOR CURRENCIES")
    else:
        console_lines.append(f"\n📅 ALL ECONOMIC EVENTS")
    console_lines.append(f"Timezone: UTC+8 (current time: {current_time_utc8.strftime('%H:%M')})")
    
    # Telegram output
    telegram_lines = []
    
    # Title for Telegram
    if only_major:
        telegram_lines.append(f"📅 <b>ECONOMIC EVENTS FOR MAJOR CURRENCIES</b>")
    else:
        telegram_lines.append(f"📅 <b>ALL ECONOMIC EVENTS</b>")
    telegram_lines.append(f"Timezone: UTC+8 (current time: {current_time_utc8.strftime('%H:%M')})")
    
    # Show events by date
    for date_str in sorted(events_by_date.keys()):
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        
        # Console date header
        console_lines.append(f"\n📆 {date_obj.strftime('%A, %d %B %Y')}")
        console_lines.append("=" * 100)
        console_lines.append(f"{'TIME':<6} | {'CTRY':<4} | {'IMPACT':<8} | {'EVENT':<50} | {'PREV':<8} | {'FCST':<8}")
        console_lines.append("-" * 100)
        
        # Telegram date header
        telegram_lines.append(f"\n📆 <b>{date_obj.strftime('%A, %d %B %Y')}</b>")
        
        # Filter events by impact level and sort by time
        high_impact_events = [e for e in events_by_date[date_str] if e.get('impact') == "High"]
        medium_impact_events = [e for e in events_by_date[date_str] if e.get('impact') == "Medium"]
        medium_low_impact_events = [e for e in events_by_date[date_str] if e.get('impact') == "Medium-Low"]
        low_impact_events = [e for e in events_by_date[date_str] if e.get('impact') == "Low"]
        
        # Combine events in order of impact
        sorted_events = high_impact_events + medium_impact_events + medium_low_impact_events + low_impact_events
        
        # Sort events by time within each impact category
        sorted_events.sort(key=lambda x: x.get("time", ""))
        
        for event in sorted_events:
            time = event.get('time', '')
            country = event.get('country', '')
            impact = event.get('impact', '')
            name = event.get('event', '')
            previous = str(event.get('previous', '')) if event.get('previous') is not None else '-'
            forecast = str(event.get('forecast', '')) if event.get('forecast') is not None else '-'
            
            # Impact emoji
            emoji = IMPACT_EMOJI.get(impact, "🟢")
            
            # Format event line for console
            console_event_line = f"{time:<6} | {country:<4} | {emoji} {impact:<6} | {name:<50} | {previous:<8} | {forecast:<8}"
            console_lines.append(console_event_line)
            
            # Format event line for Telegram (HTML)
            impact_text = f"{emoji} {impact}"
            if impact == "High":
                impact_text = f"<b>{emoji} {impact}</b>"
            
            telegram_event_line = (
                f"<code>{time}</code> | <code>{country}</code> | "
                f"{impact_text} | {html.escape(name)} | "
                f"Prev: <code>{previous}</code> | Fcst: <code>{forecast}</code>"
            )
            telegram_lines.append(telegram_event_line)
    
    return "\n".join(console_lines), "\n".join(telegram_lines)

async def send_to_telegram(message, bot_token, chat_id):
    """Send a message to Telegram
    
    Args:
        message: Message text (HTML formatted)
        bot_token: Telegram bot token
        chat_id: Telegram chat ID
    """
    try:
        bot = telegram.Bot(token=bot_token)
        # Split message if it's too long (Telegram has a 4096 character limit)
        if len(message) <= 4000:
            await bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)
        else:
            # Split the message by dates
            parts = message.split("\n📆")
            
            # Send the header (first part)
            header = parts[0]
            await bot.send_message(chat_id=chat_id, text=header, parse_mode=ParseMode.HTML)
            
            # Send each date section separately
            for i in range(1, len(parts)):
                part_text = "📆" + parts[i]
                if len(part_text) > 4000:
                    # If a single date section is still too long, split it further
                    chunks = [part_text[i:i+4000] for i in range(0, len(part_text), 4000)]
                    for chunk in chunks:
                        await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=ParseMode.HTML)
                else:
                    await bot.send_message(chat_id=chat_id, text=part_text, parse_mode=ParseMode.HTML)
        
        logger.info(f"Successfully sent message to Telegram chat {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending message to Telegram: {str(e)}")
        return False

async def main():
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Display economic calendar events')
    parser.add_argument('--days', type=int, default=0, help='Number of days ahead (0=today, 1=tomorrow, etc.)')
    parser.add_argument('--all-currencies', action='store_true', help='Show events for all currencies (default: only major currencies)')
    parser.add_argument('--telegram', action='store_true', help='Send output to Telegram')
    parser.add_argument('--bot-token', type=str, help='Telegram bot token')
    parser.add_argument('--chat-id', type=str, help='Telegram chat ID')
    parser.add_argument('--debug', action='store_true', help='Show debug information')
    args = parser.parse_args()
    
    if args.debug:
        os.environ["DEBUG"] = "1"
        logger.setLevel(logging.DEBUG)
    
    # Check if Telegram arguments are provided when --telegram is used
    if args.telegram and (not args.bot_token or not args.chat_id):
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
        if not bot_token or not chat_id:
            logger.error("Telegram bot token and chat ID must be provided either as arguments or environment variables")
            parser.print_help()
            sys.exit(1)
    else:
        bot_token = args.bot_token
        chat_id = args.chat_id
    
    logger.info(f"Fetching economic events for {args.days} days ahead...")
    events = await get_tradingview_calendar_events(days_ahead=args.days)
    
    only_major = not args.all_currencies
    
    if only_major:
        major_events = [e for e in events if e.get('country') in MAJOR_CURRENCIES]
        logger.info(f"Found {len(major_events)} upcoming events for major currencies")
    else:
        logger.info(f"Found {len(events)} upcoming events")
    
    # Format events for display
    console_output, telegram_output = format_events_for_display(events, only_major=only_major)
    
    # Print to console
    print(console_output)
    
    # Send to Telegram if requested
    if args.telegram:
        logger.info("Sending to Telegram...")
        success = await send_to_telegram(telegram_output, bot_token, chat_id)
        if success:
            logger.info("Successfully sent to Telegram")
        else:
            logger.error("Failed to send to Telegram")

if __name__ == "__main__":
    asyncio.run(main()) 