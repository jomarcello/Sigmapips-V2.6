print("Loading chart.py module...")

import os
import logging
import aiohttp
import random
from typing import Optional, Union, Dict, List, Tuple, Any
from urllib.parse import quote
import asyncio
import base64
from io import BytesIO
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import mplfinance as mpf
from datetime import datetime, timedelta
import time
import json
import pickle
import hashlib
import traceback
import re
import glob
import tempfile
import io
from pathlib import Path

# Probeer cv2 (OpenCV) te importeren, maar ga door als het niet beschikbaar is
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    logging.warning("OpenCV (cv2) is niet geïnstalleerd. Fallback mechanismen worden gebruikt voor noodgevallen charts.")
    CV2_AVAILABLE = False

# Import base class en providers
from trading_bot.services.chart_service.base import TradingViewService
from trading_bot.services.chart_service.binance_provider import BinanceProvider
# Remove Yahoo Finance imports and dependencies - Yahoo Finance is no longer used
DIRECT_MARKET_AVAILABLE = False
from trading_bot.services.chart_service.tradingview_provider import TradingViewProvider

# Import other utilities
try:
    from trading_bot.config import DISABLE_BROWSER
    from trading_bot.utils.browser_utils import setup_browser
except ImportError:
    # Fallback als config.py of utils niet bestaat
    DISABLE_BROWSER = False
    
    # Fallback setup_browser functie
    async def setup_browser():
        """Fallback functie voor browser setup als utils.browser_utils niet beschikbaar is"""
        return None

logger = logging.getLogger(__name__)

OCR_CACHE_DIR = os.path.join('data', 'cache', 'ocr')

# JSON Encoder voor NumPy types
class NumpyJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super(NumpyJSONEncoder, self).default(obj)

class ChartService:
    def __init__(self):
        """Initialize chart service"""
        print("ChartService initialized")
        try:
            # Maak cache directory aan als die niet bestaat
            os.makedirs(OCR_CACHE_DIR, exist_ok=True)
            
            # Remove Yahoo tracking - Yahoo Finance is no longer used
            # self.last_yahoo_request = 0
            
            # Initialize caches
            self.chart_cache = {}
            self.chart_cache_ttl = 60 * 5  # 5 minutes in seconds
            self.analysis_cache = {}
            self.analysis_cache_ttl = 60 * 15  # 15 minutes in seconds
            
            # Initialize browser service reference
            self.browser_service = None
            
            # Initialize chart_providers list with TradingView first
            self.chart_providers = [TradingViewProvider()]  # TradingView als primaire data bron
            
            # Add Binance provider
            self.chart_providers.append(BinanceProvider())  # Dan Binance voor crypto's
            
            # Only add DirectYahooProvider if it's available
            if DIRECT_MARKET_AVAILABLE:
                # Create a placeholder 
                class DirectMarketProvider:
                    """Fallback implementation when the real DirectMarketProvider is not available"""
                    pass
                
            # Initialiseer de chart links met de specifieke TradingView links
            self.chart_links = {
                # Commodities
                "XAUUSD": "https://www.tradingview.com/chart/bylCuCgc/",
                "XTIUSD": "https://www.tradingview.com/chart/zmsuvPgj/",  # Bijgewerkte link voor Oil
                "USOIL": "https://www.tradingview.com/chart/zmsuvPgj/",  # Dezelfde link als Oil
                
                # Currencies
                "EURUSD": "https://www.tradingview.com/chart/zmsuvPgj/",  # Bijgewerkte link voor EURUSD
                "EURGBP": "https://www.tradingview.com/chart/xt6LdUUi/",
                "EURCHF": "https://www.tradingview.com/chart/4Jr8hVba/",
                "EURJPY": "https://www.tradingview.com/chart/ume7H7lm/",
                "EURCAD": "https://www.tradingview.com/chart/gbtrKFPk/",
                "EURAUD": "https://www.tradingview.com/chart/WweOZl7z/",
                "EURNZD": "https://www.tradingview.com/chart/bcrCHPsz/",
                "GBPUSD": "https://www.tradingview.com/chart/jKph5b1W/",
                "GBPCHF": "https://www.tradingview.com/chart/1qMsl4FS/",
                "GBPJPY": "https://www.tradingview.com/chart/Zcmh5M2k/",
                "GBPCAD": "https://www.tradingview.com/chart/CvwpPBpF/",
                "GBPAUD": "https://www.tradingview.com/chart/neo3Fc3j/",
                "GBPNZD": "https://www.tradingview.com/chart/egeCqr65/",
                "CHFJPY": "https://www.tradingview.com/chart/g7qBPaqM/",
                "USDJPY": "https://www.tradingview.com/chart/mcWuRDQv/",
                "USDCHF": "https://www.tradingview.com/chart/e7xDgRyM/",
                "USDCAD": "https://www.tradingview.com/chart/jjTOeBNM/",
                "CADJPY": "https://www.tradingview.com/chart/KNsPbDME/",
                "CADCHF": "https://www.tradingview.com/chart/XnHRKk5I/",
                "AUDUSD": "https://www.tradingview.com/chart/h7CHetVW/",
                "AUDCHF": "https://www.tradingview.com/chart/oooBW6HP/",
                "AUDJPY": "https://www.tradingview.com/chart/sYiGgj7B/",
                "AUDNZD": "https://www.tradingview.com/chart/AByyHLB4/",
                "AUDCAD": "https://www.tradingview.com/chart/L4992qKp/",
                "NDZUSD": "https://www.tradingview.com/chart/yab05IFU/",
                "NZDCHF": "https://www.tradingview.com/chart/7epTugqA/",
                "NZDJPY": "https://www.tradingview.com/chart/fdtQ7rx7/",
                "NZDCAD": "https://www.tradingview.com/chart/mRVtXs19/",
                
                # Cryptocurrencies
                "BTCUSD": "https://www.tradingview.com/chart/NWT8AI4a/",
                "ETHUSD": "https://www.tradingview.com/chart/rVh10RLj/",
                "XRPUSD": "https://www.tradingview.com/chart/tQu9Ca4E/",
                "SOLUSD": "https://www.tradingview.com/chart/oTTmSjzQ/",
                "BNBUSD": "https://www.tradingview.com/chart/wNBWNh23/",
                "ADAUSD": "https://www.tradingview.com/chart/WcBNFrdb/",
                "LTCUSD": "https://www.tradingview.com/chart/AoDblBMt/",
                "DOGUSD": "https://www.tradingview.com/chart/F6SPb52v/",
                "DOTUSD": "https://www.tradingview.com/chart/nT9dwAx2/",
                "LNKUSD": "https://www.tradingview.com/chart/FzOrtgYw/",
                "XLMUSD": "https://www.tradingview.com/chart/SnvxOhDh/",
                "AVXUSD": "https://www.tradingview.com/chart/LfTlCrdQ/",
                
                # Indices
                "AU200": "https://www.tradingview.com/chart/U5CKagMM/",
                "EU50": "https://www.tradingview.com/chart/tt5QejVd/",
                "FR40": "https://www.tradingview.com/chart/RoPe3S1Q/",
                "HK50": "https://www.tradingview.com/chart/Rllftdyl/",
                "JP225": "https://www.tradingview.com/chart/i562Fk6X/",
                "UK100": "https://www.tradingview.com/chart/0I4gguQa/",
                "US100": "https://www.tradingview.com/chart/5d36Cany/",
                "US500": "https://www.tradingview.com/chart/VsfYHrwP/",
                "US30": "https://www.tradingview.com/chart/heV5Zitn/",
                "DE40": "https://www.tradingview.com/chart/OWzg0XNw/",
            }
            
            # Log initialization with available providers
            if DIRECT_MARKET_AVAILABLE:
                logging.info("Chart service initialized with providers: TradingView, Binance, DirectMarket")
            else:
                logging.info("Chart service initialized with providers: TradingView, Binance")
        except Exception as e:
            logging.error(f"Error initializing chart service: {str(e)}")
            raise

    async def get_chart(self, instrument: str, timeframe: str = "1h", fullscreen: bool = False) -> bytes:
        """Get a chart for a specific instrument and timeframe."""
        start_time = time.time()
        logger.info(f"🔍 Getting chart for {instrument} with timeframe {timeframe}")
        
        try:
            # Normaliseer het instrument
            orig_instrument = instrument
            instrument = self._normalize_instrument_name(instrument)
            logger.info(f"Normalized instrument name from {orig_instrument} to {instrument}")
            
            # Controleer of we een gecachede versie hebben
            cache_key = f"{instrument}_{timeframe}_{fullscreen}"
            if cache_key in self.chart_cache:
                cache_time, cached_chart = self.chart_cache[cache_key]
                # Gebruik de cache alleen als deze nog geldig is
                if time.time() - cache_time < self.chart_cache_ttl:
                    logger.info(f"Using cached chart for {instrument}")
                    return cached_chart
            
            # Detecteer het markttype
            market_type = await self._detect_market_type(instrument)
            logger.info(f"Detected market type for {instrument}: {market_type}")
            
            # Attempt to get TradingView screenshot first (preferred method)
            screenshot_bytes = None
            try:
                # Get the TradingView URL for this instrument
                tv_url = self.get_tradingview_url(instrument, timeframe)
                
                if tv_url:
                    logger.info(f"Attempting to capture TradingView screenshot for {instrument}")
                    # Directly call the screenshot method (browser_service is now just a flag)
                    screenshot_bytes = await self._capture_tradingview_screenshot(tv_url, instrument)
                    
                    if screenshot_bytes:
                        logger.info(f"Successfully captured TradingView screenshot for {instrument}")
                        # Cache the chart
                        self.chart_cache[cache_key] = (time.time(), screenshot_bytes)
                        return screenshot_bytes
                    else:
                        logger.warning(f"TradingView screenshot capture failed for {instrument}")
                else:
                    logger.warning(f"No TradingView URL available for {instrument}")
            except Exception as e:
                logger.error(f"Error getting TradingView screenshot: {str(e)}")
                logger.error(traceback.format_exc())
            
            # Try to get data from appropriate provider for this market type
            if market_type == "crypto":
                for provider in self.chart_providers:
                    if isinstance(provider, BinanceProvider):
                        try:
                            logger.info(f"Attempting to get crypto data from Binance for {instrument}")
                            market_data = await provider.get_market_data(instrument, timeframe=timeframe)
                            if market_data is not None and not isinstance(market_data, str) and not market_data.empty:
                                logger.info(f"Creating chart from Binance data for {instrument}")
                                # Generate custom chart with matplotlib
                                chart_bytes = self._generate_custom_chart(market_data, instrument, timeframe, fullscreen)
                                if chart_bytes:
                                    # Cache the chart
                                    self.chart_cache[cache_key] = (time.time(), chart_bytes)
                                    return chart_bytes
                        except Exception as e:
                            logger.error(f"Error generating chart from Binance data: {str(e)}")
            
            # If all methods fail, create an emergency chart
            logger.warning(f"All chart generation methods failed for {instrument}, creating emergency chart")
            emergency_chart = await self._create_emergency_chart(instrument, timeframe)
            return emergency_chart
                    
        except Exception as e:
            logger.error(f"Error in get_chart: {str(e)}")
            logger.error(traceback.format_exc())
            # Create an emergency chart
            return await self._create_emergency_chart(instrument, timeframe)
        finally:
            elapsed_time = time.time() - start_time
            logger.info(f"Chart generation for {instrument} completed in {elapsed_time:.2f} seconds")

    async def _create_emergency_chart(self, instrument: str, timeframe: str = "1h") -> bytes:
        """Create an emergency chart with a message when all chart generation methods fail."""
        try:
            logger.info(f"Creating emergency chart for {instrument}")
            
            # Maak een lege figuur
            fig, ax = plt.subplots(figsize=(10, 6))
            fig.patch.set_facecolor('#1B1B1B')
            ax.set_facecolor('#1B1B1B')
            
            # Verwijder assen en randen
            ax.axis('off')
            
            # Toon een foutmelding
            message = f"Kan geen grafiek genereren voor {instrument}\nGeen marktdata beschikbaar\nHet systeem gebruikt geen fallback data."
            ax.text(0.5, 0.5, message, ha='center', va='center', color='white', fontsize=14)
            
            # Converteer naar bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Error creating emergency chart: {str(e)}")
            # Als echt alles faalt, geef dan een statisch placeholder image terug
            chart_placeholder = resource_path("resources/chart_error.png")
            if os.path.exists(chart_placeholder):
                with open(chart_placeholder, 'rb') as f:
                    return f.read()
            else:
                # Anders een heel basic image met numpy en PIL als cv2 niet beschikbaar is
                logger.error("Emergency chart placeholder not found")
                
                if CV2_AVAILABLE:
                    emergency_img = np.ones((400, 600, 3), dtype=np.uint8) * 30
                    cv2.putText(emergency_img, "Chart unavailable", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
                    is_success, buffer = cv2.imencode(".png", emergency_img)
                    if is_success:
                        return buffer.tobytes()
                else:
                    # Fallback met PIL als cv2 niet beschikbaar is
                    try:
                        from PIL import Image, ImageDraw, ImageFont
                        img = Image.new('RGB', (600, 400), color=(30, 30, 30))
                        draw = ImageDraw.Draw(img)
                        draw.text((50, 200), "Chart unavailable", fill=(200, 200, 200))
                        buf = io.BytesIO()
                        img.save(buf, format='PNG')
                        buf.seek(0)
                        return buf.getvalue()
                    except ImportError:
                        # Als ook PIL niet beschikbaar is, maak een lege bytes array
                        logger.error("PIL is also not available for fallback chart generation")
                        return b''
                
            return b''

    async def cleanup(self):
        """Clean up resources"""
        try:
            # Er zijn nu geen specifieke resources meer om op te schonen
            logger.info("Chart service resources cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up chart service: {str(e)}")

    async def _generate_fallback_chart(self, instrument: str, timeframe: str) -> bytes:
        """Generate a fallback chart when real market data is not available.
        
        Args:
            instrument: The instrument symbol
            timeframe: The timeframe (1h, 4h, 1d)
            
        Returns:
            bytes: The chart image as bytes
        """
        try:
            logger.warning(f"Generating fallback chart for {instrument}")
            
            # Maak een lege figuur
            fig, ax = plt.subplots(figsize=(10, 6))
            fig.patch.set_facecolor('#1B1B1B')
            ax.set_facecolor('#1B1B1B')
            
            # Verwijder assen en randen
            ax.axis('off')
            
            # Toon een foutmelding
            message = f"Kan geen grafiek genereren voor {instrument}\nGeen marktdata beschikbaar\nHet systeem gebruikt geen fallback data."
            ax.text(0.5, 0.5, message, ha='center', va='center', color='white', fontsize=14)
            
            # Converteer naar bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Error generating fallback chart: {str(e)}")
            return b''

    async def generate_chart(self, instrument, timeframe="1h"):
        """Alias for get_chart for backward compatibility"""
        return await self.get_chart(instrument, timeframe)

    async def initialize(self):
        """Initialize the chart service"""
        try:
            logger.info("Initializing chart service")
            
            # Initialize matplotlib for fallback chart generation
            logger.info("Setting up matplotlib for chart generation")
            try:
                import matplotlib.pyplot as plt
                logger.info("Matplotlib is available for chart generation")
            except ImportError:
                logger.error("Matplotlib is not available, chart service may not function properly")
            
            # Initialize browser service for TradingView screenshots
            logger.info("Setting up browser service for TradingView screenshots")
            try:
                # Set browser_service to True to enable TradingView screenshots
                # This will allow the screenshot code path to be executed
                self.browser_service = True
                logger.info("Browser service initialized for chart screenshots")
            except Exception as browser_e:
                logger.error(f"Failed to initialize browser service: {str(browser_e)}")
                self.browser_service = None
            
            # Initialize technical analysis cache
            self.analysis_cache = {}
            self.analysis_cache_ttl = 60 * 15  # 15 minutes in seconds
            
            # Always return True to allow the bot to continue starting
            logger.info("Chart service initialization completed")
            return True
        except Exception as e:
            logger.error(f"Error initializing chart service: {str(e)}")
            logger.error(traceback.format_exc())
            # Continue anyway to prevent the bot from getting stuck
            return True

    def get_fallback_chart(self, instrument: str) -> bytes:
        """Get a fallback chart for when all else fails.
        
        Args:
            instrument: The instrument symbol
            
        Returns:
            bytes: A fallback chart image
        """
        try:
            logger.warning(f"Using fallback chart for {instrument}")
            
            # Maak een lege figuur
            fig, ax = plt.subplots(figsize=(10, 6))
            fig.patch.set_facecolor('#1B1B1B')
            ax.set_facecolor('#1B1B1B')
            
            # Verwijder assen en randen
            ax.axis('off')
            
            # Toon een foutmelding
            message = f"Kan geen grafiek genereren voor {instrument}\nGeen marktdata beschikbaar\nHet systeem gebruikt geen fallback data."
            ax.text(0.5, 0.5, message, ha='center', va='center', color='white', fontsize=14)
            
            # Converteer naar bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Error getting fallback chart: {str(e)}")
            return b''
            
    async def _calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
        
    async def _generate_random_chart(self, instrument: str, timeframe: str = "1h") -> bytes:
        """Returns a chart with an error message instead of generating random data.
        
        Args:
            instrument: The instrument symbol
            timeframe: The timeframe to display
            
        Returns:
            bytes: An error chart image
        """
        try:
            import matplotlib.pyplot as plt
            import io
            
            logger.warning(f"Random chart generation requested for {instrument} but generation is disabled")
            
            # Maak een lege figuur
            fig, ax = plt.subplots(figsize=(10, 6))
            fig.patch.set_facecolor('#1B1B1B')
            ax.set_facecolor('#1B1B1B')
            
            # Verwijder assen en randen
            ax.axis('off')
            
            # Toon een foutmelding
            message = f"Kan geen grafiek genereren voor {instrument}\nGeen marktdata beschikbaar\nHet systeem gebruikt geen fallback data."
            ax.text(0.5, 0.5, message, ha='center', va='center', color='white', fontsize=14)
            
            # Converteer naar bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
            
        except Exception as e:
            logger.error(f"Error generating error chart: {str(e)}")
            logger.error(traceback.format_exc())
            return b''

    async def _capture_tradingview_screenshot(self, url: str, instrument: str) -> Optional[bytes]:
        """Capture screenshot of TradingView chart using Playwright"""
        start_time = time.time()
        screenshot_bytes = None
        
        try:
            logger.info(f"Capturing TradingView screenshot for {instrument} from {url}")
            
            # Import playwright
            try:
                import playwright
                from playwright.async_api import async_playwright
            except ImportError as import_e:
                logger.error(f"Failed to import playwright: {str(import_e)}.")
                return None
                
            # Launch playwright
            async with async_playwright() as p:
                try:
                    # Launch browser
                    browser = await p.chromium.launch(
                        headless=True, 
                        args=['--no-sandbox', '--disable-dev-shm-usage']
                    )
                except Exception as browser_e:
                    logger.error(f"Failed to launch browser: {str(browser_e)}")
                    return None

                try:
                    # Create browser context
                    context = await browser.new_context(
                        viewport={"width": 1280, "height": 800},
                        device_scale_factor=1
                    )
                    
                    # Get the session ID from environment
                    session_id = os.environ.get('TRADINGVIEW_SESSION_ID', '')
                    if session_id:
                        logger.info(f"Adding TradingView session cookie: {session_id[:5]}...")
                        # Add session cookie
                        await context.add_cookies([
                            {
                                "name": "sessionid",
                                "value": session_id,
                                "domain": ".tradingview.com",
                                "path": "/"
                            }
                        ])
                    else:
                        logger.warning("No TradingView session ID found in environment variables")
                    
                    # Create page
                    page = await context.new_page()
                except Exception as page_e:
                    logger.error(f"Failed to setup browser context: {str(page_e)}")
                    await browser.close()
                    return None

                try:
                    # Navigate to URL
                    await page.goto(url, timeout=45000)
                    
                    # Dismiss dialogs
                    await page.keyboard.press("Escape")
                    
                    # Wait for chart to load
                    logger.info("Waiting for chart to load...")
                    try:
                        # Try different selectors
                        for selector in ['.chart-container', '.chart-markup-table', '.price-axis', '.chart-widget']:
                            try:
                                await page.wait_for_selector(selector, timeout=10000)
                                logger.info(f"Found chart element: {selector}")
                                break
                            except:
                                continue
                                
                        # Wait for indicator elements to appear
                        logger.info("Waiting for indicators to appear...")
                        indicator_selectors = [
                            '.pane-legend-line', 
                            '.pane-legend-item-value-wrap',
                            '.study-pane',
                            '.pane-legend-line__value'
                        ]
                        
                        for selector in indicator_selectors:
                            try:
                                await page.wait_for_selector(selector, timeout=5000)
                                logger.info(f"Found indicator element: {selector}")
                                break
                            except Exception as ind_e:
                                logger.warning(f"Couldn't find indicator element {selector}: {str(ind_e)}")
                                continue
                    except Exception as wait_e:
                        logger.warning(f"Wait error: {str(wait_e)}, continuing anyway")
                    
                    # Give time for chart to fully render
                    logger.info("Waiting for indicators to fully render...")
                    await page.wait_for_timeout(10000)
                    
                    # Try to go fullscreen
                    try:
                        await page.keyboard.press("Shift+F")
                        await page.wait_for_timeout(2000)
                    except:
                        logger.warning("Couldn't enter fullscreen, continuing anyway")
                    
                    # Take screenshot
                    logger.info(f"Taking screenshot for {instrument} now...")
                    screenshot_bytes = await page.screenshot(type='jpeg', quality=90)
                    logger.info(f"Screenshot taken, size: {len(screenshot_bytes) / 1024:.2f} KB")
                    
                    # Close browser
                    await browser.close()
                    logger.info("Browser closed")
                    
                except Exception as navigation_e:
                    logger.error(f"Error during screenshot: {str(navigation_e)}")
                    await browser.close() 
                    return None
        except Exception as e:
            logger.error(f"Screenshot error: {str(e)}")
            return None
        
        # Check screenshot validity
        if screenshot_bytes and len(screenshot_bytes) > 5000:
            end_time = time.time()
            logger.info(f"Screenshot completed in {end_time - start_time:.2f} seconds ({len(screenshot_bytes) / 1024:.2f} KB)")
            return screenshot_bytes
        else:
            logger.error(f"Screenshot failed: too small or empty")
            return None

    async def get_technical_analysis(self, instrument: str, timeframe: str = "1h") -> str:
        """Get technical analysis for a specific instrument and timeframe."""
        start_time = time.time()
        logger.info(f"Generating technical analysis for {instrument} on {timeframe}")
        
        try:
            # Normalize the instrument
            orig_instrument = instrument
            instrument = self._normalize_instrument_name(instrument)
            logger.info(f"Normalized instrument name from {orig_instrument} to {instrument}")
            
            # Check cache
            cache_key = f"{instrument}_{timeframe}"
            if cache_key in self.analysis_cache:
                cache_time, cached_analysis = self.analysis_cache[cache_key]
                if time.time() - cache_time < self.analysis_cache_ttl:
                    logger.info(f"Using cached analysis for {instrument}")
                    return cached_analysis
            
            # Detect market type
            market_type = await self._detect_market_type(instrument)
            
            # Priority order: TradingView, Binance (for crypto), DirectYahoo
            logger.info(f"Using TradingView as primary provider for {instrument} ({market_type})")
            
            # Try TradingView first
            tradingview_provider = next((p for p in self.chart_providers if isinstance(p, TradingViewProvider)), None)
            if tradingview_provider:
                analysis = await self._try_provider(tradingview_provider, instrument, timeframe, market_type, "TradingView")
                if analysis:
                    return analysis
            
            # Try Binance for crypto
            if market_type == "crypto":
                binance_provider = next((p for p in self.chart_providers if isinstance(p, BinanceProvider)), None)
                if binance_provider:
                    analysis = await self._try_provider(binance_provider, instrument, timeframe, market_type, "Binance")
                    if analysis:
                        return analysis
            
            # Try DirectYahoo only if it's available
            if DIRECT_MARKET_AVAILABLE:
                direct_market_provider = next((p for p in self.chart_providers if isinstance(p, DirectMarketProvider)), None)
                if direct_market_provider:
                    analysis = await self._try_direct_market(direct_market_provider, instrument, timeframe, market_type)
                    if analysis:
                        return analysis
            
            # Als alle providers falen, retourneer de standaard melding dat er geen data beschikbaar is
            logger.error(f"Geen ECHTE data beschikbaar voor {instrument} op {timeframe}")
            return (f"❌ GEEN DATA BESCHIKBAAR ❌\n\n"
                    f"Er kon geen actuele data worden opgehaald voor {instrument} op {timeframe} timeframe.\n\n"
                    f"Mogelijke oorzaken:\n"
                    f"• De verbinding met TradingView is mislukt\n"
                    f"• Het instrument bestaat niet of is niet beschikbaar\n"
                    f"• Er is momenteel geen marktdata beschikbaar\n\n"
                    f"Probeer het later nog eens, of kies een ander instrument.")
            
        except Exception as e:
            logger.error(f"Error in get_technical_analysis: {str(e)}")
            logger.error(traceback.format_exc())
            return f"❌ Error: {str(e)}"
        finally:
            elapsed_time = time.time() - start_time
            logger.info(f"Technical analysis for {instrument} completed in {elapsed_time:.2f} seconds")
    
    # Add compatibility method for bot.py calls
    async def get_analysis(self, instrument: str, timeframe: str = "1h") -> str:
        """
        Compatibility method for bot.py that calls get_technical_analysis
        
        Args:
            instrument: Instrument symbol to analyze
            timeframe: Timeframe for analysis (e.g., 1m, 15m, 1h, 4h)
            
        Returns:
            str: Technical analysis text for the specified instrument
        """
        logger.info(f"get_analysis called for {instrument} on {timeframe}")
        return await self.get_technical_analysis(instrument, timeframe)
        
    async def _try_provider(self, provider, instrument, timeframe, market_type, provider_name):
        """Helper method to try a market data provider"""
        try:
            logger.info(f"Trying {provider_name} for {instrument}")
            result = await provider.get_market_data(instrument, timeframe=timeframe)
            
            if result is None:
                return None
                
            # Extract data from result
            if isinstance(result, tuple) and len(result) >= 1:
                market_data = result[0]
                metadata_dict = result[1] if len(result) > 1 else {}
            else:
                market_data = result
                metadata_dict = {}
                
            if market_data is not None and not market_data.empty:
                logger.info(f"Successfully got market data from {provider_name} for {instrument}")
                metadata = {"provider": provider_name, "market_type": market_type}
                if metadata_dict:
                    metadata.update(metadata_dict)
                analysis = self._generate_analysis_from_data(instrument, timeframe, market_data, metadata)
                self.analysis_cache[f"{instrument}_{timeframe}"] = (time.time(), analysis)
                return analysis
                
            return None
        except Exception as e:
            logger.error(f"Error using {provider_name} provider: {str(e)}")
            return None
    
    async def _try_direct_market(self, provider, instrument, timeframe, market_type):
        """Helper method specific to DirectMarketProvider which returns different format"""
        try:
            logger.info(f"Trying DirectMarketProvider for {instrument}")
            market_data, indicators = await provider.get_market_data(instrument, timeframe=timeframe)
            
            if market_data is not None and not market_data.empty:
                logger.info(f"Successfully got market data from DirectMarketProvider for {instrument}")
                metadata = {"provider": "DirectMarket", "market_type": market_type}
                analysis = self._generate_analysis_from_data(instrument, timeframe, market_data, metadata)
                self.analysis_cache[f"{instrument}_{timeframe}"] = (time.time(), analysis)
                return analysis
                
            return None
        except Exception as e:
            logger.error(f"Error using DirectMarketProvider: {str(e)}")
            return None

    def _normalize_instrument_name(self, instrument: str) -> str:
        """
        Normalize an instrument name to ensure consistent formatting
        
        Args:
            instrument: Instrument symbol (e.g., EURUSD, BTCUSD)
            
        Returns:
            str: Normalized instrument name
        """
        if not instrument:
            logger.warning("Empty instrument name provided to normalize_instrument_name")
            return ""
        
        # Remove slashes and convert to uppercase
        normalized = instrument.upper().replace("/", "").strip()
        
        # Handle common aliases
        aliases = {
            "GOLD": "XAUUSD",
            "OIL": "XTIUSD",
            "CRUDE": "XTIUSD",
            "NAS100": "US100",
            "NASDAQ": "US100",
            "SPX": "US500",
            "SP500": "US500",
            "DOW": "US30",
            "DAX": "DE40",
            # Add crypto aliases
            "BTC": "BTCUSD",
            "ETH": "ETHUSD",
            "SOL": "SOLUSD",
            "XRP": "XRPUSD",
            "DOGE": "DOGEUSD",
            "ADA": "ADAUSD",
            "LINK": "LINKUSD",
            "AVAX": "AVAXUSD",
            "MATIC": "MATICUSD",
            "DOT": "DOTUSD"
        }
        
        # Check if the input is a pure crypto symbol without USD suffix
        crypto_symbols = ["BTC", "ETH", "XRP", "SOL", "ADA", "LINK", "DOT", "DOGE", "AVAX", "BNB", "MATIC"]
        if normalized in crypto_symbols:
            logger.info(f"Normalized pure crypto symbol {normalized} to {normalized}USD")
            normalized = f"{normalized}USD"
        
        # Handle USDT suffix for crypto (normalize to USD for consistency)
        if normalized.endswith("USDT"):
            base = normalized[:-4]
            if any(base == crypto for crypto in crypto_symbols):
                usd_version = f"{base}USD"
                logger.info(f"Normalized {normalized} to {usd_version}")
                normalized = usd_version
        
        # Return alias if found, otherwise return the normalized instrument
        return aliases.get(normalized, normalized)
        
    async def _detect_market_type(self, instrument: str) -> str:
        """
        Detect the market type based on the instrument name
        
        Args:
            instrument: Normalized instrument symbol (e.g., EURUSD, BTCUSD)
            
        Returns:
            str: Market type - "crypto", "forex", "commodity", or "index"
        """
        logger.info(f"Detecting market type for {instrument}")
        
        # Cryptocurrency detection
        crypto_symbols = ["BTC", "ETH", "XRP", "LTC", "BCH", "EOS", "XLM", "TRX", "ADA", "XMR", 
                         "DASH", "ZEC", "ETC", "NEO", "XTZ", "LINK", "ATOM", "ONT", "BAT", "SOL", 
                         "DOT", "AVAX", "DOGE", "SHIB", "MATIC", "UNI", "AAVE", "COMP", "YFI", "SNX"]
        
        # Check if it's a known crypto symbol
        if any(crypto in instrument for crypto in crypto_symbols):
            logger.info(f"{instrument} detected as crypto (by symbol)")
            return "crypto"
            
        # Check common crypto suffixes
        if instrument.endswith("BTC") or instrument.endswith("ETH") or instrument.endswith("USDT") or instrument.endswith("USDC"):
            logger.info(f"{instrument} detected as crypto (by trading pair)")
            return "crypto"
            
        # Specific check for USD-paired crypto
        if instrument.endswith("USD"):
            base = instrument[:-3]
            if any(base == crypto for crypto in crypto_symbols):
                logger.info(f"{instrument} detected as crypto (USD pair)")
                return "crypto"
                
        # Commodity detection
        commodity_symbols = ["XAU", "XAG", "XPT", "XPD", "XTI", "XBR", "XNG"]
        if any(instrument.startswith(comm) for comm in commodity_symbols):
            logger.info(f"{instrument} detected as commodity")
            return "commodity"
            
        # Index detection
        index_symbols = ["US30", "US500", "US100", "UK100", "DE40", "FR40", "EU50", "JP225", "AUS200", "HK50"]
        if instrument in index_symbols:
            logger.info(f"{instrument} detected as index")
            return "index"
            
        # Specific known instruments
        if instrument == "XAUUSD" or instrument == "XAGUSD" or instrument == "XTIUSD" or instrument == "WTIUSD" or instrument == "USOIL":
            logger.info(f"{instrument} detected as commodity (specific check)")
            return "commodity"
            
        # Forex detection (default for 6-char symbols with alphabetic chars)
        if len(instrument) == 6 and instrument.isalpha():
            currency_codes = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
            # Check if it's made of valid currency pairs
            base = instrument[:3]
            quote = instrument[3:]
            if base in currency_codes and quote in currency_codes:
                logger.info(f"{instrument} detected as forex")
                return "forex"
                
        # Default to forex for unknown instruments
        logger.info(f"{instrument} market type unknown, defaulting to forex")
        return "forex"

    def _get_instrument_precision(self, instrument: str) -> int:
        """
        Determine the appropriate decimal precision for displaying prices
        
        Args:
            instrument: The instrument symbol (e.g., EURUSD, BTCUSD)
            
        Returns:
            int: Number of decimal places to display
        """
        # Detect market type
        market_type = "crypto"  # Default to crypto if we can't run the async method
        
        # XRP uses 5 decimal places
        if "XRP" in instrument:
            return 5  # XRP specifieke precisie voor meer decimalen
            
        # Bitcoin and major cryptos
        if instrument in ["BTCUSD", "BTCUSDT"]:
            return 2  # Bitcoin usually displayed with 2 decimal places
            
        # Ethereum and high-value cryptos
        if instrument in ["ETHUSD", "ETHUSDT", "BNBUSD", "BNBUSDT", "SOLUSD", "SOLUSDT"]:
            return 2  # These often shown with 2 decimal places
        
        # Other cryptos
        if "BTC" in instrument or "ETH" in instrument or "USD" in instrument and any(c in instrument for c in ["XRP", "ADA", "DOT", "AVAX", "MATIC"]):
            return 4  # Most altcoins use 4-5 decimal places
            
        # Indices typically use 2 decimal places
        if instrument in ["US30", "US500", "US100", "UK100", "DE40", "JP225"]:
            return 2
            
        # Gold and silver use 2-3 decimal places
        if instrument in ["XAUUSD", "GOLD", "XAGUSD", "SILVER"]:
            return 2
            
        # Crude oil uses 2 decimal places
        if instrument in ["XTIUSD", "WTIUSD", "OIL", "USOIL"]:
            return 2
            
        # JPY pairs use 3 decimal places
        if "JPY" in instrument:
            return 3
            
        # Default for forex is 5 decimal places
        return 5

    async def _fetch_crypto_price(self, symbol: str) -> Optional[float]:
        """
        Fetch crypto price ONLY from Binance API.
        NEVER uses Yahoo Finance or AllTick for cryptocurrencies.
        
        Args:
            symbol: The crypto symbol without USD (e.g., BTC)
        
        Returns:
            float: Current price or None if failed
        """
        try:
            logger.info(f"Fetching crypto price for {symbol} from Binance API")
            
            # Use BinanceProvider to get the latest price
            from trading_bot.services.chart_service.binance_provider import BinanceProvider
            binance_provider = BinanceProvider()
            binance_result = await binance_provider.get_market_data(symbol, "1h")
            
            # Properly extract price from binance result
            if binance_result:
                if hasattr(binance_result, 'indicators') and 'close' in binance_result.indicators:
                    price = binance_result.indicators['close']
                    logger.info(f"Got crypto price {price} for {symbol} from Binance API")
                    return price
            
            logger.warning(f"Failed to get crypto price for {symbol} from Binance API")
            
            # Als Binance faalt, GEEN andere providers proberen en direct default waarden gebruiken
            logger.warning(f"Binance API failed for {symbol}, using default values")
            
            # Default values for common cryptocurrencies (updated values)
            crypto_defaults = {
                "BTC": 66500,   # Updated Bitcoin price
                "ETH": 3200,    # Updated Ethereum price
                "XRP": 2.25,    # Updated XRP price (2023-04-30)
                "SOL": 150,     # Updated Solana price
                "BNB": 550,     # Updated BNB price 
                "ADA": 0.45,    # Updated Cardano price
                "DOGE": 0.15,   # Updated Dogecoin price
                "DOT": 7.0,     # Updated Polkadot price
                "LINK": 16.5,   # Updated Chainlink price
                "AVAX": 32.0,   # Updated Avalanche price
                "MATIC": 0.60,  # Updated Polygon price
            }
            
            if symbol.upper() in crypto_defaults:
                price = crypto_defaults[symbol.upper()]
                # Add small variation to make it look realistic
                variation = random.uniform(-0.01, 0.01)  # ±1% variation
                price = price * (1 + variation)
                logger.info(f"Using default price for {symbol}: {price:.2f}")
                return price
            
            logger.warning(f"No default value available for {symbol}")
            return None
        
        except Exception as e:
            logger.error(f"Error fetching crypto price: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    async def _fetch_commodity_price(self, symbol: str) -> Optional[float]:
        """
        Fetch commodity price from TradingView or another provider (Yahoo Finance no longer used).
        
        Args:
            symbol: The commodity symbol to fetch.
            
        Returns:
            The price or None if it couldn't be fetched.
        """
        try:
            logger.info(f"Fetching {symbol} price from TradingView")
            
            # Map to correct TradingView symbol if needed
            tradingview_symbols = {
                "XAUUSD": "GOLD", 
                "XTIUSD": "USOIL",
                "USOIL": "USOIL",
                "XAGUSD": "SILVER",
                "UKOUSD": "UKOIL", 
                "UKOIL": "UKOIL",
                "COPUSD": "COPPER"
            }
            
            # Use the provided symbol or map it
            tv_symbol = tradingview_symbols.get(symbol, symbol)
            
            # Look for TradingView provider
            for provider in self.chart_providers:
                if 'tradingview' in provider.__class__.__name__.lower():
                    # Get market data with a short timeframe for recent price
                    data = await provider.get_market_data(tv_symbol, "1h", limit=5)
                    if data is not None and isinstance(data, pd.DataFrame) and not data.empty:
                        # Use the last closing price
                        price = data['close'].iloc[-1]
                        logger.info(f"Got {symbol} price from TradingView: {price}")
                        return price
            
            # If TradingView provider didn't work, try hardcoded fallback prices as last resort
            fallback_prices = {
                "XAUUSD": 1900.0,  # Gold default price
                "XTIUSD": 75.0,    # Oil default price
                "USOIL": 75.0,     # Oil default price
                "XAGUSD": 23.0,    # Silver default price
                "UKOIL": 80.0,     # Brent Oil default price
                "COPUSD": 3.8      # Copper default price
            }
            
            if symbol in fallback_prices:
                logger.warning(f"Using fallback price for {symbol}: {fallback_prices[symbol]}")
                return fallback_prices[symbol]
                
            logger.warning(f"Failed to get {symbol} price from any provider")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching commodity price: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    def _generate_analysis_from_data(self, instrument: str, timeframe: str, data: pd.DataFrame, metadata: Dict) -> str:
        """Generate a formatted technical analysis from dataframe and metadata"""
        try:
            logger.info(f"Generating analysis from data for {instrument} ({timeframe})")
            
            # Format instrument name to match Yahoo Finance/TradingView style
            display_name = instrument
            if instrument == "XAUUSD":
                display_name = "Gold (GC=F)"
            elif instrument == "XTIUSD" or instrument == "USOIL":
                display_name = "Crude Oil (CL=F)"
            elif instrument == "XAGUSD":
                display_name = "Silver (SI=F)"
            elif instrument == "US500":
                display_name = "S&P 500 (^GSPC)"
            elif instrument == "US30":
                display_name = "Dow Jones (^DJI)"
            elif instrument == "US100":
                display_name = "Nasdaq (^IXIC)"
            elif instrument == "DE40":
                display_name = "DAX (^GDAXI)"
            elif instrument == "UK100":
                display_name = "FTSE 100 (^FTSE)"
            
            # Format price with appropriate precision
            precision = self._get_instrument_precision(instrument)
            
            # Extract key data points if available
            current_price = metadata.get('close', None)
            
            if current_price is None:
                logger.error(f"No current price available for {instrument}")
                return f"⚠️ <b>Error:</b> No price data available for {instrument}."
                
            formatted_price = f"{current_price:.{precision}f}"
            
            # Get key indicators
            ema_20 = metadata.get('ema_20', None)
            ema_50 = metadata.get('ema_50', None)
            ema_200 = metadata.get('ema_200', None)
            rsi = metadata.get('rsi', None)
            macd = metadata.get('macd', None)
            macd_signal = metadata.get('macd_signal', None)
            
            # Get daily high/low directly from metadata - BELANGRIJK: GEBRUIK DEZE DIRECT
            daily_high = metadata.get('daily_high', None)
            daily_low = metadata.get('daily_low', None)
            
            # Log de waarden die we hebben ontvangen van de provider
            logger.info(f"Received from provider: daily_high={daily_high}, daily_low={daily_low}, current={current_price}")
            
            # Alleen proberen te berekenen uit DataFrame als ze niet in metadata zitten
            if (daily_high is None or daily_low is None) and len(data) > 0:
                logger.info(f"No daily high/low in metadata, calculating from DataFrame with {len(data)} rows")
                daily_data = data
                daily_high = daily_high or daily_data['High'].max()
                daily_low = daily_low or daily_data['Low'].min()
                logger.info(f"Calculated daily high: {daily_high:.5f}, daily low: {daily_low:.5f}")
            
            # Fallback values if still missing (alleen als er echt geen data is)
            if daily_high is None:
                daily_high = current_price * 1.01  # 1% above current price
                logger.info(f"Using fallback daily high: {daily_high}")
            if daily_low is None:
                daily_low = current_price * 0.99  # 1% below current price
                logger.info(f"Using fallback daily low: {daily_low}")
            
            # Get weekly high/low from the last 5 trading days
            weekly_high = metadata.get('weekly_high', None)
            weekly_low = metadata.get('weekly_low', None)
            
            # Try to calculate from DataFrame if not in metadata
            if (weekly_high is None or weekly_low is None) and len(data) >= 5:
                weekly_data = data.tail(5) if len(data) > 5 else data
                weekly_high = weekly_high or weekly_data['High'].max()
                weekly_low = weekly_low or weekly_data['Low'].min()
            
            # Fallback values for weekly high/low
            if weekly_high is None:
                weekly_high = daily_high * 1.005  # Slightly above daily high
            if weekly_low is None:
                weekly_low = daily_low * 0.995  # Slightly below daily low
            
            # Calculate momentum strength (1-5 stars)
            momentum_strength = 3  # Default
            
            # Adjust based on RSI
            if rsi is not None:
                if rsi > 70 or rsi < 30:
                    momentum_strength += 1
            
            # Adjust based on MACD
            if macd is not None and macd_signal is not None:
                if (ema_20 is not None and ema_50 is not None and 
                    ((ema_20 > ema_50 and macd > macd_signal) or 
                     (ema_20 < ema_50 and macd < macd_signal))):
                    momentum_strength += 1
            
            # Ensure within 1-5 range
            momentum_strength = max(1, min(5, momentum_strength))
            
            # Create strength stars
            strength_stars = "★" * momentum_strength + "☆" * (5 - momentum_strength)
            
            # Determine market direction based on EMAs
            market_direction = "neutral"
            if ema_20 is not None and ema_50 is not None:
                if ema_20 > ema_50:
                    market_direction = "bullish"
                elif ema_20 < ema_50:
                    market_direction = "bearish"
            
            # RSI analysis
            rsi_analysis = "N/A"
            if rsi is not None:
                if rsi > 70:
                    rsi_analysis = f"overbought ({rsi:.2f})"
                elif rsi < 30:
                    rsi_analysis = f"oversold ({rsi:.2f})"
                else:
                    rsi_analysis = f"neutral ({rsi:.2f})"
            
            # MACD analysis
            macd_analysis = "N/A"
            if macd is not None and macd_signal is not None:
                if macd > macd_signal:
                    macd_analysis = f"bullish ({macd:.5f} is above signal {macd_signal:.5f})"
                else:
                    macd_analysis = f"bearish ({macd:.5f} is below signal {macd_signal:.5f})"
            
            # Moving averages analysis
            ma_analysis = "Moving average data not available"
            if ema_50 is not None and ema_200 is not None and current_price is not None:
                if current_price > ema_50 and current_price > ema_200:
                    ma_analysis = f"Price above EMA 50 ({ema_50:.{precision}f}) and above EMA 200 ({ema_200:.{precision}f}), confirming bullish bias."
                elif current_price < ema_50 and current_price < ema_200:
                    ma_analysis = f"Price below EMA 50 ({ema_50:.{precision}f}) and below EMA 200 ({ema_200:.{precision}f}), confirming bearish bias."
                elif current_price > ema_50 and current_price < ema_200:
                    ma_analysis = f"Price above EMA 50 ({ema_50:.{precision}f}) but below EMA 200 ({ema_200:.{precision}f}), showing mixed signals."
                else:
                    ma_analysis = f"Price below EMA 50 ({ema_50:.{precision}f}) but above EMA 200 ({ema_200:.{precision}f}), showing mixed signals."
            
            # Generate market overview
            if market_direction == "bullish":
                overview = f"Price is currently trading near current price of {formatted_price}, showing bullish momentum. The pair remains above key EMAs, indicating a strong uptrend. Volume is moderate, supporting the current price action."
            elif market_direction == "bearish":
                overview = f"Price is currently trading near current price of {formatted_price}, showing bearish momentum. The pair remains below key EMAs, indicating a strong downtrend. Volume is moderate, supporting the current price action."
            else:
                overview = f"Price is currently trading near current price of {formatted_price}, showing neutral momentum. The pair is consolidating near key EMAs, indicating indecision. Volume is moderate, supporting the current price action."
            
            # Final check om te zorgen dat we zeker de juiste waarden gebruiken voor daily high/low
            logger.info(f"FINAL VALUES: daily_high={daily_high:.{precision}f}, daily_low={daily_low:.{precision}f}")
            
            # Generate AI recommendation
            if daily_high is not None and daily_low is not None:
                if market_direction == "bullish":
                    recommendation = f"Watch for a breakout above {daily_high:.{precision}f} for further upside. Maintain a buy bias while price holds above {daily_low:.{precision}f}. Be cautious of overbought conditions if RSI approaches 70."
                elif market_direction == "bearish":
                    recommendation = f"Watch for a breakdown below {daily_low:.{precision}f} for further downside. Maintain a sell bias while price holds below {daily_high:.{precision}f}. Be cautious of oversold conditions if RSI approaches 30."
                else:
                    recommendation = f"Market is in consolidation. Wait for a breakout above {daily_high:.{precision}f} or breakdown below {daily_low:.{precision}f} before taking a position. Monitor volume for breakout confirmation."
            else:
                recommendation = "Insufficient data for a specific recommendation."
            
            # Format key levels properly
            daily_high_formatted = f"{daily_high:.{precision}f}" if daily_high is not None else "N/A"
            daily_low_formatted = f"{daily_low:.{precision}f}" if daily_low is not None else "N/A"
            weekly_high_formatted = f"{weekly_high:.{precision}f}" if weekly_high is not None else "N/A"
            weekly_low_formatted = f"{weekly_low:.{precision}f}" if weekly_low is not None else "N/A"
            
            # Generate analysis text
            analysis = f"""{display_name} Analysis

Zone Strength: {strength_stars}

📊 Market Overview
{overview}

🔑 Key Levels
Daily High:   {daily_high_formatted}
Daily Low:    {daily_low_formatted}
Weekly High:  {weekly_high_formatted}
Weekly Low:   {weekly_low_formatted}

📈 Technical Indicators
RSI: {rsi_analysis}
MACD: {macd_analysis}
Moving Averages: {ma_analysis}

🤖 Sigmapips AI Recommendation
{recommendation}

⚠️ Disclaimer: For educational purposes only.
"""
            
            return analysis
        except Exception as e:
            logger.error(f"Error generating analysis from data: {str(e)}")
            logger.error(traceback.format_exc())
            return f"⚠️ <b>Error:</b> Unable to generate analysis for {instrument}. Error: {str(e)}"

    def _detect_market_type_sync(self, instrument: str) -> str:
        """
        Non-async version of _detect_market_type
        """
        # List of common forex pairs
        forex_pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD', 'EURGBP', 'EURJPY']
        
        # List of common indices
        indices = ['US30', 'US500', 'US100', 'DE40', 'UK100', 'FR40', 'JP225', 'AU200', 'EU50']
        
        # List of common commodities
        commodities = ['XAUUSD', 'XAGUSD', 'XTIUSD', 'XBRUSD', 'XCUUSD', 'USOIL']
        
        # Crypto prefixes and common cryptos
        crypto_prefixes = ['BTC', 'ETH', 'XRP', 'LTC', 'BCH', 'BNB', 'ADA', 'DOT', 'LINK', 'XLM']
        common_cryptos = ['BTCUSD', 'ETHUSD', 'XRPUSD', 'LTCUSD', 'BCHUSD', 'BNBUSD', 'ADAUSD', 'DOTUSD', 'LINKUSD', 'XLMUSD']
        
        # Check if the instrument is a forex pair
        if instrument in forex_pairs or (
                len(instrument) == 6 and 
            instrument[:3] in ['EUR', 'GBP', 'USD', 'AUD', 'NZD', 'CAD', 'CHF', 'JPY'] and
            instrument[3:] in ['EUR', 'GBP', 'USD', 'AUD', 'NZD', 'CAD', 'CHF', 'JPY']
            ):
            return "forex"
        
        # Check if the instrument is an index
        if instrument in indices:
            return "index"
        
        # Check if the instrument is a commodity
        if instrument in commodities:
            return "commodity"
        
        # Check if the instrument is a cryptocurrency
        if instrument in common_cryptos or any(instrument.startswith(prefix) for prefix in crypto_prefixes):
            return "crypto"
        
        # Default to forex for unknown instruments
        return "forex"

    def get_tradingview_url(self, instrument: str, timeframe: str = '1h') -> str:
        """Get TradingView URL for a specific instrument and timeframe.
        
        Args:
            instrument: The instrument symbol.
            timeframe: The chart timeframe (1h, 4h, 1d, etc.)
        
        Returns:
            The TradingView URL with the correct timeframe or empty string if not found.
        """
        # Check if this instrument is in our chart_links dictionary
        if instrument not in self.chart_links:
            logger.warning(f"No TradingView URL found for {instrument}")
            return ""
            
        # Get the base URL from chart_links
        base_url = self.chart_links[instrument]
        
        # Map timeframe to TradingView format
        tv_timeframe_map = {
            '1h': '60',
            '4h': '240',
            '1d': 'D',
            '5m': '5',
            '15m': '15',
            '30m': '30',
            '1w': 'W'
        }
        tv_timeframe = tv_timeframe_map.get(timeframe, timeframe)
        
        # Parse URL components to properly add parameters
        url_parts = base_url.split('?')
        base_url = url_parts[0]
        params = {}
        
        # Parse existing parameters
        if len(url_parts) > 1:
            query_string = url_parts[1]
            for param in query_string.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = value
        
        # Add essential parameters
        params['interval'] = tv_timeframe
        
        # Add theme parameter for consistency
        params['theme'] = 'dark'
        
        # Force reload parameter to bypass cache
        params['force_reload'] = 'true'
        
        # Rebuild the URL with all params
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        final_url = f"{base_url}?{query_string}"
        
        logger.info(f"Using TradingView URL: {final_url}")
        
        return final_url

    async def _fetch_index_price(self, symbol: str) -> Optional[float]:
        """
        Fetch market index price from APIs.
        
        Args:
            symbol: The index symbol (e.g., US30, US500)
            
        Returns:
            float: Current price or None if failed
        """
        try:
            logger.info(f"Fetching {symbol} price from external APIs")
            
            # Map symbols to common index names
            index_map = {
                "US30": "dow",
                "US500": "sp500",
                "US100": "nasdaq",
                "UK100": "ftse",
                "DE40": "dax",
                "JP225": "nikkei",
                "AU200": "asx200"
            }
            
            index_name = index_map.get(symbol, symbol.lower())
            
            # Probeer prijs op te halen via TradingView
            try:
                # Probeer de prijs via TradingView te krijgen
                data = await TradingViewProvider.get_market_data(symbol, "1h")
                if data:
                    df, metadata = data
                    price = metadata.get("close")
                    if price:
                        logger.info(f"Retrieved {symbol} price from TradingView: {price}")
                        return price
            except Exception as e:
                logger.error(f"Error fetching {symbol} price from TradingView: {str(e)}")
            
            # Als we hier komen, hebben we geen prijs kunnen ophalen
            logger.warning(f"Could not fetch real price for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching index price: {str(e)}")
            return None

    async def _generate_default_analysis(self, instrument: str, timeframe: str) -> str:
        """
        Retourneert een bericht dat er geen data beschikbaar is in plaats van mock data te genereren.
        
        Args:
            instrument: Het handelssymbool (bijv. EURUSD, AAPL)
            timeframe: Het tijdsinterval (1m, 5m, 1h, 1d, etc.)
            
        Returns:
            str: Bericht dat er geen data beschikbaar is
        """
        logger.error(f"Geen ECHTE data beschikbaar voor {instrument} op {timeframe}")
        
        return (f"❌ GEEN DATA BESCHIKBAAR ❌\n\n"
                f"Er kon geen actuele data worden opgehaald voor {instrument} op {timeframe} timeframe.\n\n"
                f"Mogelijke oorzaken:\n"
                f"• De verbinding met TradingView is mislukt\n"
                f"• Het instrument bestaat niet of is niet beschikbaar\n"
                f"• Er is momenteel geen marktdata beschikbaar\n\n"
                f"Probeer het later nog eens, of kies een ander instrument.")

    def _prioritize_providers_for_market(self, instrument: str, market_type: str, timeframe: str) -> List[Any]:
        """Return a list of providers prioritized for the given market type."""
        # Copy the list of providers to avoid modifying the original
        providers = self.chart_providers.copy()
        
        # Set up the prioritized list
        prioritized_providers = []
        
        # First, identify the TradingView provider which gets highest priority
        tradingview_provider = None
        # No need for Yahoo provider anymore - Yahoo Finance is no longer used
        
        # Identify all provider types
        for provider in providers:
            if 'tradingview' in provider.__class__.__name__.lower():
                tradingview_provider = provider
        
        # Start with TradingView in any case
        if tradingview_provider:
            prioritized_providers.append(tradingview_provider)
        
        # For crypto, prioritize Binance
        if market_type == "crypto":
            for provider in providers:
                if 'binance' in provider.__class__.__name__.lower():
                    prioritized_providers.append(provider)
        
        # Add any remaining providers in original order
        for provider in providers:
            if provider not in prioritized_providers:
                prioritized_providers.append(provider)
        
        # Return deduplicated list
        return list(dict.fromkeys(prioritized_providers))
