import os
import logging
import asyncio
import json
import base64
import subprocess
import time
from typing import Optional, Dict, List, Any, Union
from io import BytesIO
from datetime import datetime
from trading_bot.services.chart_service.tradingview import TradingViewService

logger = logging.getLogger(__name__)

class TradingViewNodeService(TradingViewService):
    def __init__(self, session_id=None):
        """Initialize the TradingView Node.js service"""
        super().__init__()
        self.session_id = session_id or os.getenv("TRADINGVIEW_SESSION_ID", "z90l85p2anlgdwfppsrdnnfantz48z1o")
        self.username = os.getenv("TRADINGVIEW_USERNAME", "")
        self.password = os.getenv("TRADINGVIEW_PASSWORD", "")
        self.is_initialized = False
        self.is_logged_in = False
        self.base_url = "https://www.tradingview.com"
        self.chart_url = "https://www.tradingview.com/chart"
        
        # Get the project root directory and set the correct script path
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.script_path = os.path.join(project_root, "tradingview_screenshot.js")
        
        # Caching van playfound playwright check
        self.playwright_installed = None
        self.playwright_browsers_installed = None
        
        # Chart links voor verschillende symbolen
        self.chart_links = {
            "EURUSD": "https://www.tradingview.com/chart/?symbol=EURUSD",
            "GBPUSD": "https://www.tradingview.com/chart/?symbol=GBPUSD",
            "BTCUSD": "https://www.tradingview.com/chart/?symbol=BTCUSD",
            "ETHUSD": "https://www.tradingview.com/chart/?symbol=ETHUSD"
        }
        
        # Screenshot cache removed
        
        logger.info(f"TradingView Node.js service initialized")
    
    async def initialize(self):
        """Initialize the Node.js service"""
        try:
            logger.info("Initializing TradingView Node.js service")
            
            # Controleer of Node.js is geïnstalleerd (alleen indien nodig)
            try:
                node_version = subprocess.check_output(["node", "--version"]).decode().strip()
                logger.info(f"Node.js version: {node_version}")
            except Exception as node_error:
                logger.error(f"Error checking Node.js version: {str(node_error)}")
                return False
            
            # Check if the screenshot.js file exists in different potential locations
            potential_paths = [
                self.script_path,  # Original path
                os.path.join(os.getcwd(), "tradingview_screenshot.js"),  # Project root
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "tradingview_screenshot.js")  # Root directory
            ]
            
            script_found = False
            for path in potential_paths:
                if os.path.exists(path):
                    self.script_path = path
                    script_found = True
                    logger.info(f"screenshot.js found at {self.script_path}")
                    break
            
            if not script_found:
                logger.error(f"screenshot.js not found in any of the potential paths")
                return False
            
            # Playwright check verbeteren
            if self.playwright_installed is None:
                try:
                    # Test if Playwright is installed
                    subprocess.run(["node", "-e", "require('playwright')"], 
                                  check=True, 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  timeout=3)
                    logger.info("Playwright is available")
                    
                    # Check if browsers are installed
                    try:
                        # Korte test of de browser bestaat
                        browser_check = subprocess.run(
                            ["node", "-e", "const { chromium } = require('playwright'); (async () => { try { const browser = await chromium.launch(); await browser.close(); console.log('true'); } catch(e) { console.log('false'); } })()"],
                            check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            timeout=5
                        )
                        browsers_installed = "true" in browser_check.stdout.decode()
                        
                        # Als browsers niet beschikbaar zijn, installeer ze
                        if not browsers_installed:
                            logger.info("Playwright browsers installeren...")
                            subprocess.run(
                                ["npx", "playwright", "install", "chromium"],
                                check=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                timeout=120  # Tijdslimiet van 2 minuten voor installatie
                            )
                            logger.info("Playwright browsers geïnstalleerd")
                        
                        self.playwright_installed = True
                        self.playwright_browsers_installed = True
                    except Exception as browser_error:
                        logger.error(f"Browser check/install fout: {str(browser_error)}")
                        self.playwright_installed = True
                        self.playwright_browsers_installed = False
                except Exception:
                    logger.warning("Playwright niet beschikbaar")
                    self.playwright_installed = False
            
            # Set initialized flag
            self.is_initialized = True
            logger.info("TradingView Node.js service initialized")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing TradingView Node.js service: {str(e)}")
            return False
    
    async def take_screenshot(self, symbol, timeframe=None, fullscreen=False):
        """Take a screenshot of a chart"""
        try:
            logger.info(f"Taking screenshot for {symbol} on {timeframe} timeframe (fullscreen: {fullscreen})")
            
            # Normaliseer het symbool (verwijder / en converteer naar hoofdletters)
            normalized_symbol = symbol.replace("/", "").upper()
            
            # Bouw de chart URL
            chart_url = self.chart_links.get(normalized_symbol)
            if not chart_url:
                logger.warning(f"No chart URL found for {symbol}, using default URL")
                # Gebruik een lichtere versie van de chart
                chart_url = f"https://www.tradingview.com/chart/xknpxpcr/?symbol={normalized_symbol}"
                if timeframe:
                    tv_interval = self.interval_map.get(timeframe, "D")
                    chart_url += f"&interval={tv_interval}"
            
            # Controleer of de URL geldig is
            if not chart_url:
                logger.error(f"Invalid chart URL for {symbol}")
                return None
            
            # Gebruik de take_screenshot_of_url methode om de screenshot te maken
            logger.info(f"Taking screenshot of URL: {chart_url}")
            screenshot_bytes = await self.take_screenshot_of_url(chart_url, fullscreen=fullscreen)
            
            if screenshot_bytes:
                logger.info(f"Screenshot taken successfully for {symbol}")
                return screenshot_bytes
            else:
                logger.error(f"Failed to take screenshot for {symbol}")
                return None
            
        except Exception as e:
            logger.error(f"Error taking screenshot: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def batch_capture_charts(self, symbols=None, timeframes=None):
        """Capture multiple charts"""
        if not self.is_initialized:
            logger.warning("TradingView Node.js service not initialized")
            return None
        
        if not symbols:
            symbols = ["EURUSD", "GBPUSD", "BTCUSD", "ETHUSD"]
        
        if not timeframes:
            timeframes = ["1h", "4h", "1d"]
        
        results = {}
        
        try:
            for symbol in symbols:
                results[symbol] = {}
                
                for timeframe in timeframes:
                    try:
                        # Take screenshot
                        screenshot = await self.take_screenshot(symbol, timeframe)
                        results[symbol][timeframe] = screenshot
                    except Exception as e:
                        logger.error(f"Error capturing {symbol} at {timeframe}: {str(e)}")
                        results[symbol][timeframe] = None
            
            return results
            
        except Exception as e:
            logger.error(f"Error in batch capture: {str(e)}")
            return None
    
    async def cleanup(self):
        """Clean up resources"""
        # Geen resources om op te ruimen
        logger.info("TradingView Node.js service cleaned up")
    
    async def take_screenshot_of_url(self, url: str, fullscreen: bool = False) -> Optional[bytes]:
        """Take a screenshot of a URL using Node.js"""
        start_time = time.time()
        logger.info(f"[START] Take screenshot of URL: {url} (fullscreen: {fullscreen})")
        
        try:
            # Genereer een unieke bestandsnaam voor de screenshot
            timestamp = int(time.time())
            screenshot_id = f"{timestamp}_{hash(url) % 10000}"
            screenshot_path = os.path.join(os.path.dirname(self.script_path), f"screenshot_{screenshot_id}.png")
            
            # Zorg ervoor dat de URL geen aanhalingstekens bevat
            url = url.strip('"\'')
            
            # Voeg session ID en timeouts toe aan het commando
            cmd = f"node {self.script_path} \"{url}\" \"{screenshot_path}\" \"{self.session_id}\""
            
            # Voeg fullscreen parameter toe als dat nodig is
            if fullscreen or "fullscreen=true" in url:
                cmd += " fullscreen"
                
            # Voeg extra wachttijd toe aan het commando
            cmd += " 45000"  # 45 seconden wachttijd max voor paginalading
            
            # Verwijder eventuele puntkomma's uit het commando
            cmd = cmd.replace(";", "")
            
            logger.info(f"[EXEC] Executing Node.js command: {cmd}")
            
            # Gebruik asyncio.create_subprocess_shell met een langere timeout
            try:
                process_start = time.time()
                logger.info(f"[PROC] Starting Node.js process")
                
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Wacht op het proces met een langere timeout (45 seconden max)
                try:
                    logger.info(f"[PROC] Waiting for Node.js process to complete (timeout: 45s)")
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=45.0)
                    
                    process_end = time.time()
                    process_time = process_end - process_start
                    logger.info(f"[PROC] Node.js process completed in {process_time:.2f} seconds")
                    
                    # Log the standard output if not empty
                    if stdout:
                        stdout_output = stdout.decode().strip()
                        if stdout_output:
                            logger.info(f"[PROC] Node.js stdout: {stdout_output}")
                    
                except asyncio.TimeoutError:
                    logger.error(f"[PROC] TIMEOUT waiting for Node.js script (45s), terminating process")
                    try:
                        process.kill()
                        logger.info(f"[PROC] Process killed successfully")
                    except Exception as kill_error:
                        logger.error(f"[PROC] Error killing process: {str(kill_error)}")
                    return None
                
                # Log errors if any
                if stderr:
                    stderr_output = stderr.decode().strip()
                    if stderr_output:
                        logger.error(f"[PROC] Node.js stderr: {stderr_output}")
                
                # Controleer of het bestand bestaat met extra logging
                file_check_start = time.time()
                if os.path.exists(screenshot_path):
                    file_size = os.path.getsize(screenshot_path)
                    logger.info(f"[FILE] Screenshot file found: {screenshot_path} (size: {file_size} bytes)")
                    
                    # Controleer of het bestand een minimale grootte heeft
                    if file_size < 5000:  # Minder dan 5KB is waarschijnlijk geen echte screenshot
                        logger.warning(f"[FILE] Screenshot file is suspiciously small: {file_size} bytes")
                    
                    # Lees het bestand
                    with open(screenshot_path, 'rb') as f:
                        screenshot_data = f.read()
                        logger.info(f"[FILE] Screenshot file read successfully: {len(screenshot_data)} bytes")
                    
                    # Verwijder het bestand
                    try:
                        os.remove(screenshot_path)
                        logger.info(f"[FILE] Screenshot file removed successfully")
                    except Exception as e:
                        logger.warning(f"[FILE] Failed to remove temporary screenshot file: {str(e)}")
                    
                    # Log de totale tijd
                    total_time = time.time() - start_time
                    logger.info(f"[DONE] Screenshot capture completed in {total_time:.2f} seconds with success")
                    
                    # Return the screenshot data
                    return screenshot_data
                else:
                    logger.error(f"[FILE] Screenshot file not found: {screenshot_path}")
                    
                    # Controleer of er andere screenshot bestanden zijn in dezelfde map
                    try:
                        directory = os.path.dirname(screenshot_path)
                        files = [f for f in os.listdir(directory) if f.startswith("screenshot_")]
                        if files:
                            logger.info(f"[FILE] Found other screenshot files in directory: {files}")
                    except Exception as e:
                        logger.error(f"[FILE] Error checking directory for other screenshot files: {str(e)}")
                    
                    return None
                    
            except Exception as process_error:
                logger.error(f"[PROC] Error running Node.js process: {str(process_error)}")
                logger.error(f"[PROC] Traceback: {traceback.format_exc()}")
                return None
                
        except Exception as e:
            logger.error(f"[ERROR] Error taking screenshot: {str(e)}")
            logger.error(f"[ERROR] Traceback: {traceback.format_exc()}")
            return None
