import asyncio
import logging
import json
import aiohttp
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import random
import base64

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

# Fallback event templates per currency
FALLBACK_EVENTS = {
    "USD": [
        {"title": "Fed Chair Speech", "importance": 2},
        {"title": "FOMC Meeting Minutes", "importance": 2},
        {"title": "Nonfarm Payrolls", "importance": 3},
        {"title": "CPI m/m", "importance": 2},
        {"title": "Retail Sales m/m", "importance": 1},
        {"title": "Unemployment Rate", "importance": 2}
    ],
    "EUR": [
        {"title": "ECB Press Conference", "importance": 2},
        {"title": "German Manufacturing PMI", "importance": 1},
        {"title": "CPI y/y", "importance": 2},
        {"title": "Eurozone GDP q/q", "importance": 2}
    ],
    "GBP": [
        {"title": "BOE Monetary Policy Report", "importance": 2},
        {"title": "Manufacturing PMI", "importance": 1},
        {"title": "GDP m/m", "importance": 2}
    ],
    "JPY": [
        {"title": "BOJ Policy Statement", "importance": 2},
        {"title": "Tokyo Core CPI y/y", "importance": 1},
        {"title": "Monetary Policy Meeting Minutes", "importance": 1}
    ],
    "CHF": [
        {"title": "SNB Monetary Policy Assessment", "importance": 2},
        {"title": "PPI m/m", "importance": 0}
    ],
    "AUD": [
        {"title": "RBA Rate Statement", "importance": 2},
        {"title": "Employment Change", "importance": 1},
        {"title": "CPI q/q", "importance": 2}
    ],
    "NZD": [
        {"title": "RBNZ Rate Statement", "importance": 2},
        {"title": "GDP q/q", "importance": 1}
    ],
    "CAD": [
        {"title": "BOC Rate Statement", "importance": 2},
        {"title": "Employment Change", "importance": 1},
        {"title": "CPI m/m", "importance": 1}
    ]
}

class TodayCalendarService:
    """Calendar service die events van vandaag toont voor major currencies"""
    
    def __init__(self, tz_offset=8, scraping_ant_key=None):  # Malaysia time (UTC+8)
        self.base_url = "https://economic-calendar.tradingview.com/events"
        self.scraping_ant_url = "https://api.scrapingant.com/v2/general"
        self.scraping_ant_key = scraping_ant_key
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
        if scraping_ant_key:
            logger.info(f"ScrapingAnt proxy enabled with key: {scraping_ant_key[:5]}...{scraping_ant_key[-3:]}")
        
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
            
            # Use a longer timeout to prevent hanging
            timeout = aiohttp.ClientTimeout(total=30)
            
            # Determine if we should use ScrapingAnt or direct API
            if self.scraping_ant_key:
                # Use ScrapingAnt proxy
                response_text = await self._fetch_with_scraping_ant(params)
            else:
                # Direct API call to TradingView
                logger.info(f"Making direct API request to: {self.base_url}")
                async with self.session.get(self.base_url, params=params, headers=headers, timeout=timeout) as response:
                    logger.info(f"Got response with status: {response.status}")
                    
                    if response.status != 200:
                        logger.error(f"Error response from TradingView (status {response.status})")
                        return self._generate_fallback_events(min_impact, currency)
                        
                    # Verwerk de response
                    response_text = await response.text()
            
            # Controleer of de API een geldige JSON-respons geeft
            if not response_text or not (response_text.strip().startswith('[') or response_text.strip().startswith('{')):
                logger.error("API returned invalid or empty response")
                return self._generate_fallback_events(min_impact, currency)
            
            # Parse JSON response
            try:
                data = json.loads(response_text)
                
                # Check for different response formats
                events_data = []
                
                # Format 1: Direct array of events
                if isinstance(data, list):
                    events_data = data
                    logger.info(f"Found {len(events_data)} events in API response (array format)")
                
                # Format 2: Object with 'result' containing events
                elif isinstance(data, dict) and 'result' in data:
                    events_data = data['result']
                    logger.info(f"Found {len(events_data)} events in API response (result object format)")
                
                # Format 3: Object with 'data' containing events
                elif isinstance(data, dict) and 'data' in data:
                    events_data = data['data']
                    logger.info(f"Found {len(events_data)} events in API response (data object format)")
                
                # Format 4: ScrapingAnt format with 'content' containing JSON string
                elif isinstance(data, dict) and 'content' in data and isinstance(data.get('content'), str):
                    try:
                        content_data = json.loads(data['content'])
                        if isinstance(content_data, list):
                            events_data = content_data
                            logger.info(f"Found {len(events_data)} events in ScrapingAnt content (array format)")
                        elif isinstance(content_data, dict) and 'result' in content_data:
                            events_data = content_data['result']
                            logger.info(f"Found {len(events_data)} events in ScrapingAnt content (result object format)")
                        elif isinstance(content_data, dict) and 'data' in content_data:
                            events_data = content_data['data']
                            logger.info(f"Found {len(events_data)} events in ScrapingAnt content (data object format)")
                    except json.JSONDecodeError:
                        logger.error("Failed to parse ScrapingAnt content as JSON")
                        return self._generate_fallback_events(min_impact, currency)
                
                else:
                    logger.warning(f"Unexpected response format: {type(data)}")
                    logger.warning("API returned valid response but no calendar events were found")
                    return self._generate_fallback_events(min_impact, currency)
                
                # Process events
                processed_events = self._process_events(events_data, min_impact, currency)
                logger.info(f"Processed {len(processed_events)} events for today")
                
                # If no events were found, generate fallback events
                if not processed_events:
                    logger.warning("No events found after processing, generating fallback events")
                    return self._generate_fallback_events(min_impact, currency)
                
                return processed_events
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse response as JSON: {e}")
                return self._generate_fallback_events(min_impact, currency)
                
        except Exception as e:
            logger.error(f"Error in get_today_calendar: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self._generate_fallback_events(min_impact, currency)
        finally:
            # Ensure we close the session
            await self._close_session()
    
    async def _fetch_with_scraping_ant(self, params: Dict) -> Optional[str]:
        """Fetch data using ScrapingAnt proxy"""
        try:
            # Build TradingView URL with parameters
            url = self.base_url
            query_params = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{query_params}"
            
            logger.info(f"Making ScrapingAnt request for URL: {full_url}")
            
            # Prepare ScrapingAnt request
            scraping_params = {
                "url": full_url,
                "browser": True,
                "return_page_source": True,
                "proxy_type": "residential",
                "wait_for_selector": "body"
            }
            
            headers = {
                "x-api-key": self.scraping_ant_key,
                "Content-Type": "application/json"
            }
            
            # Make request to ScrapingAnt
            async with self.session.post(
                self.scraping_ant_url, 
                json=scraping_params, 
                headers=headers
            ) as response:
                logger.info(f"ScrapingAnt response status: {response.status}")
                
                if response.status != 200:
                    logger.error(f"ScrapingAnt error: {response.status}")
                    return None
                
                # Get response JSON
                response_json = await response.json()
                
                # Check if we have content
                if "content" not in response_json:
                    logger.error("No content in ScrapingAnt response")
                    return None
                
                return response_json["content"]
                
        except Exception as e:
            logger.error(f"Error in ScrapingAnt request: {e}")
            return None
    
    def _generate_fallback_events(self, min_impact: str = "Low", currency: str = None) -> List[Dict[str, Any]]:
        """Generate fallback events when API fails"""
        logger.info("Generating fallback economic events")
        
        # Map impact levels to numeric values for comparison
        impact_levels = {
            "Low": 1,
            "Medium": 2,
            "High": 3
        }
        min_impact_value = impact_levels.get(min_impact, 1)
        
        # Impact map for fallback events
        impact_map = {
            -1: "Low",
            0: "Low",
            1: "Medium",
            2: "Medium",
            3: "High"
        }
        
        # Generate events for today
        processed_events = []
        
        # Determine which currencies to include
        currencies_to_include = [currency] if currency else MAJOR_CURRENCIES
        
        # Current hour in local timezone
        current_hour = self.today.hour
        
        # Generate 1-2 events per currency
        for curr in currencies_to_include:
            # Skip if no fallback events for this currency
            if curr not in FALLBACK_EVENTS:
                continue
                
            # Get fallback events for this currency
            currency_events = FALLBACK_EVENTS[curr]
            
            # Filter by impact level
            filtered_events = [e for e in currency_events 
                              if impact_levels.get(impact_map.get(e.get('importance', -1), "Low"), 0) >= min_impact_value]
            
            if not filtered_events:
                continue
                
            # Select 1-2 events
            num_events = min(len(filtered_events), random.randint(1, 2))
            selected_events = random.sample(filtered_events, num_events)
            
            # Spread events throughout the day
            for i, event in enumerate(selected_events):
                # Generate a time in the future if current hour is morning
                # Otherwise generate throughout the day
                if current_hour < 12:
                    hour = random.randint(current_hour + 1, 23)
                else:
                    hour = random.randint(0, 23)
                    
                minute = random.choice([0, 15, 30, 45])
                event_time = self.today.replace(hour=hour, minute=minute)
                
                # Get impact level
                raw_impact = event.get('importance', -1)
                impact = impact_map.get(raw_impact, "Low")
                
                # Create processed event
                processed_event = {
                    "country": curr,
                    "flag": CURRENCY_FLAGS.get(curr, "🌐"),
                    "time": event_time.strftime('%H:%M'),
                    "datetime": event_time,
                    "event": event.get('title', 'Economic Event'),
                    "impact": impact,
                    "impact_emoji": IMPACT_EMOJI.get(impact, "⚪"),
                    "forecast": None,
                    "previous": None,
                    "actual": None,
                    "is_fallback": True  # Mark as fallback event
                }
                
                processed_events.append(processed_event)
        
        # Sort events by time
        processed_events.sort(key=lambda x: x["datetime"])
        
        logger.info(f"Generated {len(processed_events)} fallback events")
        return processed_events
            
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
                        
                        # Add fallback indicator if applicable
                        is_fallback = event.get('is_fallback', False)
                        fallback_str = " [Est]" if is_fallback else ""
                        
                        output.append(f"  {time} - {impact_emoji} {title}{extra_str}{fallback_str}")
                    
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
                
                # Add fallback indicator if applicable
                is_fallback = event.get('is_fallback', False)
                fallback_str = " [Est]" if is_fallback else ""
                
                output.append(f"{time} - {flag} {currency} - {impact_emoji} {title}{extra_str}{fallback_str}")
        
        return "\n".join(output)

async def test_today_calendar(scraping_ant_key=None):
    """Test de calendar service voor vandaag"""
    
    logger.info("Initializing calendar service for today...")
    calendar_service = TodayCalendarService(tz_offset=8, scraping_ant_key=scraping_ant_key)  # Malaysia Time (UTC+8)
    
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
    # Check if ScrapingAnt key is provided in environment
    import os
    scraping_ant_key = os.environ.get("SCRAPING_ANT_KEY")
    
    logger.info("Starting calendar test for today...")
    if scraping_ant_key:
        logger.info(f"Using ScrapingAnt with key: {scraping_ant_key[:5]}...{scraping_ant_key[-3:]}")
    else:
        logger.info("No ScrapingAnt key found, using direct API access")
        
    results = asyncio.run(test_today_calendar(scraping_ant_key))
    
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