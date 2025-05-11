import asyncio
import logging
from calendar_service import TodayCalendarService, MAJOR_CURRENCIES, CURRENCY_FLAGS, IMPACT_EMOJI

# Configureer logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def demo_calendar_service():
    """Demonstreer de calendar service met events in chronologische volgorde op tijd"""
    
    # Initialiseer de service met Maleisische tijd (UTC+8)
    calendar_service = TodayCalendarService(tz_offset=8)
    
    # Haal alle events op voor vandaag
    print("\n\n=== ECONOMIC CALENDAR: ALL EVENTS (CHRONOLOGICAL ORDER) ===")
    print("Note: Events marked with [Est] are estimated events when API data is unavailable")
    all_events = await calendar_service.get_today_calendar()
    print(f"Total events found: {len(all_events)}")
    
    # Check if any fallback events were generated
    fallback_events = [e for e in all_events if e.get('is_fallback', False)]
    if fallback_events:
        print(f"Note: {len(fallback_events)} fallback events were generated due to API limitations")
    
    # Toon alle events in chronologische volgorde
    chrono_calendar = calendar_service.format_calendar_for_display(all_events, group_by_currency=False)
    print(chrono_calendar)
    
    # Toon alleen USD events in chronologische volgorde
    print("\n\n=== USD EVENTS ONLY (CHRONOLOGICAL ORDER) ===")
    usd_events = await calendar_service.get_today_calendar(currency="USD")
    print(f"USD events found: {len(usd_events)}")
    
    usd_calendar = calendar_service.format_calendar_for_display(usd_events, group_by_currency=False)
    print(usd_calendar)
    
    # Toon alleen high impact events in chronologische volgorde
    print("\n\n=== HIGH IMPACT EVENTS ONLY (CHRONOLOGICAL ORDER) ===")
    high_impact_events = await calendar_service.get_today_calendar(min_impact="High")
    print(f"High impact events found: {len(high_impact_events)}")
    
    if high_impact_events:
        high_impact_calendar = calendar_service.format_calendar_for_display(high_impact_events, group_by_currency=False)
        print(high_impact_calendar)
    else:
        print("No high impact events found for today")
        
        # Als alternatief, toon medium impact events
        print("\n=== MEDIUM IMPACT EVENTS (CHRONOLOGICAL ORDER) ===")
        medium_impact_events = await calendar_service.get_today_calendar(min_impact="Medium")
        print(f"Medium impact events found: {len(medium_impact_events)}")
        
        if medium_impact_events:
            medium_impact_calendar = calendar_service.format_calendar_for_display(medium_impact_events, group_by_currency=False)
            print(medium_impact_calendar)
    
    # Toon medium/high impact USD events in chronologische volgorde
    print("\n\n=== MEDIUM/HIGH IMPACT USD EVENTS (CHRONOLOGICAL ORDER) ===")
    usd_medium_events = await calendar_service.get_today_calendar(min_impact="Medium", currency="USD")
    print(f"Medium/High impact USD events found: {len(usd_medium_events)}")
    
    if usd_medium_events:
        usd_medium_calendar = calendar_service.format_calendar_for_display(usd_medium_events, group_by_currency=False)
        print(usd_medium_calendar)
    else:
        print("No medium/high impact USD events found for today")
    
    return {
        "all_events": len(all_events),
        "fallback_events": len(fallback_events) if fallback_events else 0,
        "usd_events": len(usd_events),
        "high_impact_events": len(high_impact_events),
        "medium_impact_usd_events": len(usd_medium_events)
    }

if __name__ == "__main__":
    print("\n===== ECONOMIC CALENDAR - CHRONOLOGICAL ORDER =====")
    print("All events are displayed in chronological order by time")
    print("Time zone: Malaysia (UTC+8)")
    print("=================================================")
    
    results = asyncio.run(demo_calendar_service())
    
    print("\n=== SUMMARY ===")
    print(f"Total events: {results['all_events']}")
    if results['fallback_events'] > 0:
        print(f"Fallback events: {results['fallback_events']} (when API data unavailable)")
    print(f"USD events: {results['usd_events']}")
    print(f"High impact events: {results['high_impact_events']}")
    print(f"Medium/High impact USD events: {results['medium_impact_usd_events']}")
    print("\n=================================================") 