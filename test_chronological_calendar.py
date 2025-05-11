#!/usr/bin/env python3
"""
Test script for chronological economic calendar formatter.
This script demonstrates how to use the chronological formatter with the existing TradingViewCalendarService.
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def test_chronological_calendar():
    """Test the chronological calendar formatter with TradingViewCalendarService"""
    
    try:
        # Import the TradingViewCalendarService
        from trading_bot.services.calendar_service.tradingview_calendar import TradingViewCalendarService
        
        # Import our chronological formatter
        from trading_bot.services.calendar_service.chronological_formatter import (
            format_calendar_events_chronologically,
            format_calendar_events_by_currency,
            format_tradingview_calendar
        )
        
        logger.info("Successfully imported required modules")
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        print(f"ERROR: Failed to import required modules: {e}")
        return
    
    # Check if ScrapingAnt key is available
    scraping_ant_key = os.environ.get("SCRAPINGANT_API_KEY")
    if not scraping_ant_key:
        logger.warning("No ScrapingAnt API key found. Set SCRAPINGANT_API_KEY environment variable for better results.")
        print("WARNING: No ScrapingAnt API key found. Set SCRAPINGANT_API_KEY environment variable for better results.")
    else:
        masked_key = f"{scraping_ant_key[:5]}...{scraping_ant_key[-3:]}" if len(scraping_ant_key) > 8 else "[masked]"
        logger.info(f"Using ScrapingAnt with API key: {masked_key}")
        # Ensure ScrapingAnt is enabled
        os.environ["USE_SCRAPINGANT"] = "true"
    
    try:
        # Initialize TradingViewCalendarService
        calendar_service = TradingViewCalendarService()
        logger.info("Initialized TradingViewCalendarService")
        
        # Get today's date formatted
        today_formatted = datetime.now().strftime("%A, %d %B %Y")
        logger.info(f"Today's date: {today_formatted}")
        
        # Retrieve calendar events for today
        print("\nRetrieving calendar events for today...")
        events = await calendar_service.get_calendar(days_ahead=0, min_impact="Low")
        logger.info(f"Retrieved {len(events)} calendar events")
        print(f"Retrieved {len(events)} calendar events")
        
        # Format events chronologically
        print("\n=== ECONOMIC CALENDAR (CHRONOLOGICAL ORDER) ===")
        chronological_calendar = await calendar_service.format_calendar_chronologically(
            events, today_formatted, group_by_currency=False
        )
        print(chronological_calendar)
        
        # Format events by currency
        print("\n=== ECONOMIC CALENDAR (GROUPED BY CURRENCY) ===")
        currency_grouped_calendar = await calendar_service.format_calendar_chronologically(
            events, today_formatted, group_by_currency=True
        )
        print(currency_grouped_calendar)
        
        # Get USD events only
        print("\n\nRetrieving USD events only...")
        usd_events = await calendar_service.get_calendar(days_ahead=0, min_impact="Low", currency="USD")
        logger.info(f"Retrieved {len(usd_events)} USD events")
        print(f"Retrieved {len(usd_events)} USD events")
        
        # Format USD events chronologically
        print("\n=== USD EVENTS ONLY (CHRONOLOGICAL ORDER) ===")
        usd_calendar = await calendar_service.format_calendar_chronologically(
            usd_events, today_formatted, group_by_currency=False
        )
        print(usd_calendar)
        
        # Get high impact events only
        print("\n\nRetrieving high impact events only...")
        high_impact_events = await calendar_service.get_calendar(days_ahead=0, min_impact="High")
        logger.info(f"Retrieved {len(high_impact_events)} high impact events")
        print(f"Retrieved {len(high_impact_events)} high impact events")
        
        # Format high impact events chronologically
        print("\n=== HIGH IMPACT EVENTS ONLY (CHRONOLOGICAL ORDER) ===")
        if high_impact_events:
            high_impact_calendar = await calendar_service.format_calendar_chronologically(
                high_impact_events, today_formatted, group_by_currency=False
            )
            print(high_impact_calendar)
        else:
            print("No high impact events found for today")
        
        return {
            "all_events": len(events),
            "usd_events": len(usd_events),
            "high_impact_events": len(high_impact_events)
        }
        
    except Exception as e:
        logger.error(f"Error testing chronological calendar: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"ERROR: {e}")
        return None

if __name__ == "__main__":
    print("\n===== ECONOMIC CALENDAR - CHRONOLOGICAL FORMATTER TEST =====")
    print("Testing the chronological formatter with TradingViewCalendarService")
    print("=============================================================")
    
    results = asyncio.run(test_chronological_calendar())
    
    if results:
        print("\n=== SUMMARY ===")
        print(f"Total events: {results['all_events']}")
        print(f"USD events: {results['usd_events']}")
        print(f"High impact events: {results['high_impact_events']}")
        print("\n=================================================")
    else:
        print("\n=== TEST FAILED ===")
        print("Check the logs for details")
        print("======================") 