"""
Browser utility functions for the trading bot
"""

import logging

logger = logging.getLogger(__name__)

async def setup_browser():
    """
    Setup a playwright browser instance
    
    Returns:
        Browser: Playwright browser instance, or None if playwright is not available
    """
    try:
        # Try to import playwright
        from playwright.async_api import async_playwright
        
        logger.info("Setting up browser with playwright")
        playwright = await async_playwright().start()
        
        # Launch browser with minimal settings
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-extensions", "--disable-dev-shm-usage"]
        )
        
        return browser
    except ImportError:
        logger.warning("Playwright not available, browser features will be disabled")
        return None
    except Exception as e:
        logger.error(f"Error setting up browser: {str(e)}")
        return None 
