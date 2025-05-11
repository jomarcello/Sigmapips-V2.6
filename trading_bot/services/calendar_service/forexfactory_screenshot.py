import os
import logging
import time
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from playwright.async_api import async_playwright, Browser, Page, TimeoutError

# Configure logging
logger = logging.getLogger(__name__)

class ForexFactoryScreenshotService:
    """Service for retrieving forex calendar data from ForexFactory using screenshots."""
    
    def __init__(self):
        """Initialize the service."""
        self.browser = None
        self.base_url = "https://www.forexfactory.com/calendar"
        self.is_initialized = False
        
        # Keep track of last successful screenshot
        self.last_screenshot = None
        self.last_screenshot_time = None
        
        # Cache for calendar data
        self.calendar_cache = {}
        self.cache_expiry = 3600  # 1 hour in seconds
    
    async def initialize(self) -> bool:
        """Initialize the browser if not already initialized."""
        if self.is_initialized:
            return True
            
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.is_initialized = True
            logger.info("ForexFactory screenshot service initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize ForexFactory screenshot service: {str(e)}")
            return False
    
    async def close(self):
        """Close the browser."""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.is_initialized = False
            logger.info("ForexFactory screenshot service closed")
    
    async def take_screenshot(self, days_ahead: int = 0) -> Optional[bytes]:
        """Take a screenshot of the ForexFactory calendar."""
        if not self.is_initialized:
            success = await self.initialize()
            if not success:
                logger.error("Could not initialize browser for screenshot")
                return None
        
        try:
            # Create new page
            page = await self.browser.new_page()
            
            # Navigate to ForexFactory calendar
            await page.goto(self.base_url, wait_until="networkidle")
            
            # If we need to navigate to a future date
            if days_ahead > 0:
                # Click on next day button the required number of times
                for _ in range(days_ahead):
                    await page.click('a.calendar__pagination--next')
                    await page.wait_for_timeout(1000)  # Wait for page to update
            
            # Wait for calendar to load
            await page.wait_for_selector('.calendar__table', timeout=10000)
            
            # Take screenshot
            screenshot = await page.screenshot()
            
            # Close page
            await page.close()
            
            # Update last screenshot timestamp
            self.last_screenshot = screenshot
            self.last_screenshot_time = datetime.now()
            
            return screenshot
        except Exception as e:
            logger.error(f"Error taking ForexFactory calendar screenshot: {str(e)}")
            return None
    
    async def get_calendar_events(self, days_ahead: int = 0, currency: str = None) -> List[Dict[str, Any]]:
        """Get calendar events.
        
        This is a stub implementation that returns mock data, as OCR would be needed
        to actually extract events from the screenshot.
        """
        try:
            # Check if we have cached data
            cache_key = f"{days_ahead}_{currency}"
            current_time = datetime.now()
            
            if cache_key in self.calendar_cache:
                cache_time, cache_data = self.calendar_cache[cache_key]
                # If cache is still valid
                if (current_time - cache_time).total_seconds() < self.cache_expiry:
                    logger.info(f"Using cached calendar data for {cache_key}")
                    return cache_data
            
            # Take screenshot (this part would be where OCR would happen in a real implementation)
            await self.take_screenshot(days_ahead)
            
            # Generate mock event data
            # In a real implementation, this would extract data from the screenshot using OCR
            events = self._generate_mock_events(currency)
            
            # Cache the result
            self.calendar_cache[cache_key] = (current_time, events)
            
            return events
        except Exception as e:
            logger.error(f"Error getting calendar events: {str(e)}")
            return []
    
    def _generate_mock_events(self, currency: str = None) -> List[Dict[str, Any]]:
        """Generate mock calendar events for testing."""
        # Get current hour for dynamic events
        current_hour = datetime.now().hour
        
        # Common economic events
        all_events = {
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
                {"time": f"{(current_hour + 3) % 24:02d}:00", "event": "RBNZ Interest Rate Decision", "impact": "High"},
                {"time": f"{(current_hour + 5) % 24:02d}:45", "event": "GDP", "impact": "Medium"}
            ],
            "CAD": [
                {"time": f"{(current_hour + 2) % 24:02d}:30", "event": "BOC Interest Rate Decision", "impact": "High"},
                {"time": f"{(current_hour + 4) % 24:02d}:15", "event": "CPI", "impact": "Medium"}
            ]
        }
        
        # Filter by currency if provided
        if currency and currency in all_events:
            return all_events[currency]
        elif currency:
            return []  # Return empty list if currency doesn't have any events
        
        # Return all events if no currency filter
        result = []
        for curr, events in all_events.items():
            for event in events:
                event_with_currency = event.copy()
                event_with_currency["currency"] = curr
                result.append(event_with_currency)
        
        return result 