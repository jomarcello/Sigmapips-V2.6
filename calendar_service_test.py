import asyncio
import logging
import json
import aiohttp
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

# Configureer logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Definieer de major currencies
MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"]

# Emoji's voor valuta vlaggen
CURRENCY_FLAGS = {
    "USD": "🇺🇸",
    "EUR": "🇪🇺",
    "GBP": "🇬🇧",
    "JPY": "🇯🇵",
    "CHF": "🇨🇭",
    "AUD": "🇦🇺",
    "NZD": "🇳🇿",
    "CAD": "🇨🇦"
}

# Emoji's voor impact levels
IMPACT_EMOJI = {
    "High": "🔴",
    "Medium": "🟠",
    "Low": "🟢"
}

class TodayCalendarService:
    """Calendar service die events van vandaag toont voor major currencies"""
    
    def __init__(self, tz_offset=8):  # Malaysia time (UTC+8)
        self.base_url = "https://economic-calendar.tradingview.com/events"
        self.session = None
        
        # Configureer tijdzone offset (Malaysia = UTC+8)
        self.tz_offset = tz_offset
        self.timezone_name = f"UTC+{tz_offset}" if tz_offset >= 0 else f"UTC{tz_offset}"
        self.tz = timezone(timedelta(hours=tz_offset))
        
        # Gebruik lokale tijd voor weergave
        self.today = datetime.now(self.tz)
        self.today_str = self.today.strftime("%Y-%m-%d")
        self.today_formatted = self.today.strftime("%A, %d %B %Y")  # Bijv. "Monday, 12 May 2025"
        logger.info(f"TodayCalendarService initialized for {self.today_formatted} ({self.timezone_name})")
        
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
        """Format date for TradingView API (UTC)"""
        # Zorg ervoor dat de datum in UTC is voor de API
        utc_date = date.astimezone(timezone.utc)
        utc_date = utc_date.replace(microsecond=0)
        return utc_date.isoformat().replace('+00:00', '.000Z')
        
    async def get_today_calendar(self, min_impact: str = "Low", currency: str = None) -> List[Dict[str, Any]]:
        """
        Fetch calendar events from TradingView for today only
        
        Args:
            min_impact: Minimum impact level to include (Low, Medium, High)
            currency: Optional currency to filter events by (must be a major currency)
            
        Returns:
            List of today's calendar events for major currencies
        """
        try:
            # Valideer currency parameter als deze is opgegeven
            if currency and currency not in MAJOR_CURRENCIES:
                logger.warning(f"Currency {currency} is not a major currency, using all major currencies instead")
                currency = None
            
            logger.info(f"Starting calendar fetch for today ({self.today_formatted}), min_impact={min_impact}, currency={currency}")
            await self._ensure_session()
            
            # Calculate date range - alleen voor vandaag (in lokale tijd)
            start_date = self.today.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = self.today.replace(hour=23, minute=59, second=59, microsecond=0)
            
            logger.info(f"Date range (local): {start_date.isoformat()} to {end_date.isoformat()}")
            
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
                'limit': 1000
            }
            
            logger.info(f"API date range (UTC): from={params['from']} to={params['to']}")
            
            # Filter by specific currency or use all major currencies
            if currency:
                params['countries'] = currency_to_country.get(currency)
                logger.info(f"Filtering by currency: {currency} (country code: {params['countries']})")
            else:
                # Gebruik alle major currencies
                country_codes = [currency_to_country[curr] for curr in MAJOR_CURRENCIES]
                params['countries'] = ','.join(country_codes)
                logger.info(f"Using all major currencies: {MAJOR_CURRENCIES}")
            
            # Headers voor betere API compatibiliteit
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
            
            # Direct API call to TradingView
            logger.info(f"Making API request to: {self.base_url}")
            
            # Use a longer timeout to prevent hanging
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with self.session.get(self.base_url, params=params, headers=headers, timeout=timeout) as response:
                logger.info(f"Got response with status: {response.status}")
                
                if response.status != 200:
                    logger.error(f"Error response from TradingView (status {response.status})")
                    return []
                    
                # Verwerk de response
                response_text = await response.text()
                
                # Controleer of de API een geldige JSON-respons geeft
                if not response_text or not (response_text.strip().startswith('[') or response_text.strip().startswith('{')):
                    logger.error("API returned invalid or empty response")
                    return []
                
                # Parse JSON response
                try:
                    data = json.loads(response_text)
                    
                    # Check if the response has the correct structure
                    if isinstance(data, dict) and 'status' in data and data['status'] == 'ok' and 'result' in data:
                        events_data = data['result']
                        logger.info(f"Found {len(events_data)} events in API response")
                        
                        # Process events
                        processed_events = self._process_events(events_data, min_impact, currency)
                        logger.info(f"Processed {len(processed_events)} events for today")
                        
                        return processed_events
                    else:
                        logger.warning(f"Unexpected response format: {type(data)}")
                        return []
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse response as JSON: {e}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error in get_today_calendar: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
        finally:
            # Ensure we close the session
            await self._close_session()
            
    def _process_events(self, events_data: List[Dict], min_impact: str = "Low", currency: str = None) -> List[Dict[str, Any]]:
        """Process raw events from API response, filtering for major currencies only"""
        processed_events = []
        
        # Map impact levels
        impact_map = {
            -1: "Low",
            0: "Medium", 
            1: "Medium",
            2: "High",
            3: "High"
        }
        
        # Map impact levels to numeric values for comparison
        impact_levels = {
            "Low": 1,
            "Medium": 2,
            "High": 3
        }
        min_impact_value = impact_levels.get(min_impact, 1)
        
        # Map country codes to currency codes
        country_to_currency = {
            'US': 'USD',
            'EU': 'EUR',
            'GB': 'GBP',
            'JP': 'JPY',
            'CH': 'CHF',
            'AU': 'AUD',
            'NZ': 'NZD',
            'CA': 'CAD'
        }
        
        # Process each event
        for event in events_data:
            try:
                # Get country code
                country_code = event.get('country')
                if not country_code:
                    continue
                
                # Map country code to currency code
                event_currency = country_to_currency.get(country_code)
                
                # Skip if not a major currency
                if not event_currency or event_currency not in MAJOR_CURRENCIES:
                    continue
                
                # Filter by currency if specified
                if currency and event_currency != currency:
                    continue
                
                # Get event time
                event_time = event.get('date', '')
                if not event_time:
                    continue
                
                # Parse event time (API geeft UTC terug)
                try:
                    # Parse UTC time from API
                    event_datetime_utc = datetime.fromisoformat(event_time.replace('.000Z', '+00:00'))
                    
                    # Convert to local timezone for display
                    event_datetime_local = event_datetime_utc.astimezone(self.tz)
                    event_time_str = event_datetime_local.strftime('%H:%M')
                    
                    # Store both for sorting and display
                    event_datetime = event_datetime_local
                    
                    # Controleer of het event van vandaag is (in lokale tijd)
                    event_date = event_datetime_local.date()
                    today_date = self.today.date()
                    if event_date != today_date:
                        logger.warning(f"Event date {event_date} does not match today's date {today_date}, skipping")
                        continue
                    
                except Exception as e:
                    logger.warning(f"Failed to parse event time '{event_time}': {e}")
                    event_time_str = "00:00"
                    event_datetime = datetime.now(self.tz).replace(hour=0, minute=0, second=0, microsecond=0)
                
                # Get impact level
                raw_impact = event.get('importance', -1)
                impact = impact_map.get(raw_impact, "Low")
                
                # Filter by impact level
                impact_value = impact_levels.get(impact, 0)
                if impact_value < min_impact_value:
                    continue
                
                # Create processed event
                processed_event = {
                    "country": event_currency,
                    "flag": CURRENCY_FLAGS.get(event_currency, "🌐"),
                    "time": event_time_str,
                    "datetime": event_datetime,  # Bewaar voor sortering
                    "event": event.get('title', 'Unknown Event'),
                    "impact": impact,
                    "impact_emoji": IMPACT_EMOJI.get(impact, "⚪"),
                    "forecast": event.get('forecast'),
                    "previous": event.get('previous'),
                    "actual": event.get('actual')
                }
                
                # Add highlighted flag if this is the requested currency
                if currency:
                    processed_event["highlighted"] = (event_currency == currency)
                
                processed_events.append(processed_event)
                
            except Exception as e:
                logger.warning(f"Error processing event: {e}")
                continue
        
        # Sort events by time
        processed_events.sort(key=lambda x: x["datetime"])
        
        return processed_events

    def format_calendar_for_display(self, events: List[Dict], group_by_currency: bool = False) -> str:
        """Format calendar events for display"""
        if not events:
            return f"📅 Economic Calendar for {self.today_formatted}\n\nNo economic events found for today."
        
        # Format de kalender
        output = [f"📅 Economic Calendar for {self.today_formatted}\n"]
        output.append("Impact: 🔴 High   🟠 Medium   🟢 Low\n")
        
        if group_by_currency:
            # Groepeer events per valuta
            events_by_currency = {}
            for event in events:
                currency = event.get('country')
                if currency not in events_by_currency:
                    events_by_currency[currency] = []
                events_by_currency[currency].append(event)
            
            # Sorteer valuta's volgens MAJOR_CURRENCIES volgorde
            for currency in MAJOR_CURRENCIES:
                if currency in events_by_currency:
                    currency_events = events_by_currency[currency]
                    flag = CURRENCY_FLAGS.get(currency, "🌐")
                    
                    # Voeg valuta header toe
                    output.append(f"{flag} {currency}")
                    
                    # Sorteer events op tijd
                    currency_events.sort(key=lambda x: x["datetime"])
                    
                    # Voeg events toe
                    for event in currency_events:
                        time = event.get('time')
                        impact_emoji = event.get('impact_emoji')
                        title = event.get('event')
                        
                        # Voeg forecast en previous toe indien beschikbaar
                        forecast = event.get('forecast')
                        previous = event.get('previous')
                        
                        extra_info = []
                        if forecast is not None:
                            extra_info.append(f"F: {forecast}")
                        if previous is not None:
                            extra_info.append(f"P: {previous}")
                        
                        extra_str = f" ({', '.join(extra_info)})" if extra_info else ""
                        
                        output.append(f"  {time} - {impact_emoji} {title}{extra_str}")
                    
                    # Voeg lege regel toe tussen valuta's
                    output.append("")
        else:
            # Events zijn al gesorteerd op tijd
            for event in events:
                time = event.get('time')
                impact_emoji = event.get('impact_emoji')
                title = event.get('event')
                flag = event.get('flag')
                currency = event.get('country')
                
                # Voeg forecast en previous toe indien beschikbaar
                forecast = event.get('forecast')
                previous = event.get('previous')
                
                extra_info = []
                if forecast is not None:
                    extra_info.append(f"F: {forecast}")
                if previous is not None:
                    extra_info.append(f"P: {previous}")
                
                extra_str = f" ({', '.join(extra_info)})" if extra_info else ""
                
                output.append(f"{time} - {flag} {currency} - {impact_emoji} {title}{extra_str}")
        
        return "\n".join(output)

async def test_today_calendar():
    """Test de calendar service voor vandaag"""
    
    logger.info("Initializing calendar service for today...")
    calendar_service = TodayCalendarService(tz_offset=8)  # Malaysia Time (UTC+8)
    
    # Haal events op voor vandaag
    logger.info("Fetching calendar data for today...")
    events = await calendar_service.get_today_calendar()
    logger.info(f"Retrieved: {len(events)} events for today")
    
    # Groepeer events per valuta
    events_by_currency = {}
    for event in events:
        currency = event.get('country')
        if currency not in events_by_currency:
            events_by_currency[currency] = []
        events_by_currency[currency].append(event)
    
    # Toon aantal events per valuta
    for currency, curr_events in events_by_currency.items():
        logger.info(f"Currency {currency}: {len(curr_events)} events")
    
    # Format de kalender voor weergave (chronologisch)
    formatted_calendar_chrono = calendar_service.format_calendar_for_display(events, group_by_currency=False)
    
    # Format de kalender voor weergave (gegroepeerd per valuta)
    formatted_calendar_grouped = calendar_service.format_calendar_for_display(events, group_by_currency=True)
    
    return {
        "today": calendar_service.today_formatted,
        "timezone": calendar_service.timezone_name,
        "all_events": len(events),
        "events_by_currency": {curr: len(evts) for curr, evts in events_by_currency.items()},
        "formatted_calendar_chrono": formatted_calendar_chrono,
        "formatted_calendar_grouped": formatted_calendar_grouped
    }

if __name__ == "__main__":
    logger.info("Starting calendar test for today...")
    results = asyncio.run(test_today_calendar())
    
    print("\n=== ECONOMIC CALENDAR ===")
    print(f"Date: {results['today']}")
    print(f"Total events: {results['all_events']}")
    
    print("\nEvents by currency:")
    for currency, count in results['events_by_currency'].items():
        flag = CURRENCY_FLAGS.get(currency, "🌐")
        print(f"  {flag} {currency}: {count} events")
    
    print("\n--- TIME ORDER ---\n")
    print(results['formatted_calendar_chrono'])
    
    print("\n--- BY CURRENCY ---\n")
    print(results['formatted_calendar_grouped'])
    print("\n-------------------------------") 