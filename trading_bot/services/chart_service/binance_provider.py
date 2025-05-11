import logging
import traceback
import asyncio
import os
import aiohttp
import hmac
import hashlib
import time
import random
from typing import Optional, Dict, Any, List
from collections import namedtuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

class BinanceProvider:
    """Provider class for Binance API integration for cryptocurrency data"""
    
    # Base URLs for Binance API with failover options
    BASE_ENDPOINTS = [
        "https://api.binance.com",
        "https://api-gcp.binance.com", 
        "https://api1.binance.com",
        "https://api2.binance.com",
        "https://api3.binance.com",
        "https://api4.binance.com"
    ]
    
    # Officially documented endpoint for public market data (less restricted)
    SPOT_DATA_API_URL = "https://data-api.binance.vision"
    
    # Current active endpoint (start with the primary one)
    _active_endpoint_index = 0
    
    # Track API usage
    _last_api_call = 0
    _api_call_count = 0
    _max_calls_per_minute = 20  # Binance rate limits
    
    # API credentials (loaded from environment variables)
    API_KEY = os.environ.get("BINANCE_API_KEY", "")
    API_SECRET = os.environ.get("BINANCE_API_SECRET", "")
    
    @classmethod
    def get_base_url(cls):
        """Get current active base URL with optional failover"""
        return cls.BASE_ENDPOINTS[cls._active_endpoint_index]
    
    @classmethod
    def switch_endpoint(cls):
        """Switch to next endpoint for failover"""
        cls._active_endpoint_index = (cls._active_endpoint_index + 1) % len(cls.BASE_ENDPOINTS)
        new_endpoint = cls.get_base_url()
        logger.info(f"Switching to Binance endpoint: {new_endpoint}")
        return new_endpoint
    
    @staticmethod
    async def get_market_data(instrument: str, timeframe: str = "1h") -> Optional[Dict[str, Any]]:
        """
        Get market data from Binance Data API (data.binance.com) for technical analysis.
        This endpoint is less likely to be geo-restricted for market data.
        
        Args:
            instrument: Trading instrument (e.g., BTCUSD, ETHUSDT)
            timeframe: Timeframe for analysis (1h, 4h, 1d)
            
        Returns:
            Optional[Dict]: Technical analysis data or None if failed
        """
        # Use the dedicated SPOT data endpoint URL defined at class level
        data_endpoint_url = BinanceProvider.SPOT_DATA_API_URL 
        
        # Log original instrument before formatting
        logger.info(f"[Binance Data API] Getting market data for instrument: {instrument}")
        
        try:
            # Implement basic rate limiting (still useful)
            current_time = time.time()
            minute_passed = current_time - BinanceProvider._last_api_call >= 60
            
            if minute_passed:
                BinanceProvider._api_call_count = 0
                BinanceProvider._last_api_call = current_time
            elif BinanceProvider._api_call_count >= BinanceProvider._max_calls_per_minute:
                logger.warning(f"Binance API rate limit reached ({BinanceProvider._api_call_count} calls). Waiting...")
                await asyncio.sleep(5 + random.random() * 2)
            
            BinanceProvider._api_call_count += 1
            
            # Format symbol for Binance API
            formatted_symbol = BinanceProvider._format_symbol(instrument)
            logger.info(f"[Binance Data API] Formatted symbol: {instrument} -> {formatted_symbol}")
            
            logger.info(f"Fetching {formatted_symbol} data from Binance Vision Data API: {data_endpoint_url}. API call #{BinanceProvider._api_call_count} this minute.")
            
            # Map timeframe to Binance interval
            binance_interval = {
                "1m": "1m", 
                "5m": "5m", 
                "15m": "15m", 
                "30m": "30m",
                "1h": "1h", 
                "2h": "2h", 
                "4h": "4h", 
                "1d": "1d",
                "1w": "1w",
                "1M": "1M"
            }.get(timeframe, "1h")
            
            limit = 120 # Always get enough data for indicators
                
            endpoint = "/api/v3/klines"
            params = {
                "symbol": formatted_symbol,
                "interval": binance_interval,
                "limit": limit
            }
            
            # Get candlestick data using the specific data endpoint
            async with aiohttp.ClientSession() as session:
                headers = {} # Data endpoint typically doesn't need API key for public klines
                
                request_url = f"{data_endpoint_url}{endpoint}"
                logger.info(f"[Binance Data API Request] URL: {request_url}")
                logger.info(f"[Binance Data API Request] PARAMS: {params}")
                logger.info(f"[Binance Data API Request] HEADERS: {headers}")
                
                try:
                    async with session.get(request_url, params=params, headers=headers, timeout=20) as response: # Increased timeout slightly
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"[Binance Data API Response Error] STATUS: {response.status}")
                            logger.error(f"[Binance Data API Response Error] HEADERS: {response.headers}")
                            logger.error(f"[Binance Data API Response Error] BODY: {error_text}")
                            # If data endpoint fails, return None - no fallback needed for this specific strategy
                            return None
                        
                        klines = await response.json()
                        if not klines or not isinstance(klines, list):
                            logger.error(f"[Binance Data API] Returned invalid kline data: {klines}")
                            return None
                        
                        logger.info(f"[Binance Data API] Successfully retrieved {len(klines)} klines for {formatted_symbol}")
                        
                except aiohttp.ClientConnectorError as e:
                    logger.error(f"[Binance Data API Connection Error] Failed to connect to {request_url}: {str(e)}")
                    return None # Fail directly if connection error to data endpoint
                except asyncio.TimeoutError:
                    logger.error(f"[Binance Data API Connection Error] Timeout connecting to {request_url}")
                    return None # Fail directly if timeout to data endpoint
            
            # Convert klines to dataframe
            df = BinanceProvider._klines_to_dataframe(klines)
            
            # Calculate technical indicators
            df = BinanceProvider._calculate_indicators(df)
            
            # Get the latest data point
            latest = df.iloc[-1]
            
            # Create analysis result object
            MarketData = namedtuple('MarketData', ['instrument', 'indicators'])
            
            # Extract indicators for return
            indicators = {
                "close": float(latest["close"]),
                "open": float(latest["open"]),
                "high": float(latest["high"]),
                "low": float(latest["low"]),
                "volume": float(latest["volume"]),
                "EMA20": float(latest["EMA20"]),
                "EMA50": float(latest["EMA50"]),
                "EMA200": float(latest["EMA200"]),
                "RSI": float(latest["RSI"]),
                "MACD.macd": float(latest["MACD"]),
                "MACD.signal": float(latest["MACD_signal"]),
                "MACD.hist": float(latest["MACD_hist"]),
            }
            
            standardized_indicators = BinanceProvider._standardize_indicator_names(indicators)
            
            week_data = df.tail(168 if binance_interval == "1h" else 42 if binance_interval == "4h" else 7 if binance_interval == "1d" else df.shape[0])
            standardized_indicators["weekly_high"] = float(week_data["high"].max())
            standardized_indicators["weekly_low"] = float(week_data["low"].min())
                
            result = MarketData(instrument=instrument, indicators=standardized_indicators)
            return result
            
        except Exception as e:
            logger.error(f"Error getting market data from Binance Data API: {str(e)}")
            logger.error(traceback.format_exc())
            return None # General exception handling
    
    @staticmethod
    async def get_ticker_price(symbol: str) -> Optional[float]:
        """Get current ticker price for a symbol"""
        retries = 0
        max_retries = 3
        
        while retries < max_retries:
            try:
                formatted_symbol = BinanceProvider._format_symbol(symbol)
                base_url = BinanceProvider.get_base_url()
                
                # For ticker price, we can use the data API endpoint for better performance
                endpoint_url = BinanceProvider.DATA_API_ENDPOINT if retries == 0 else base_url
                endpoint = "/api/v3/ticker/price"
                params = {"symbol": formatted_symbol}
                
                async with aiohttp.ClientSession() as session:
                    headers = {}
                    if BinanceProvider.API_KEY:
                        headers["X-MBX-APIKEY"] = BinanceProvider.API_KEY
                        
                    async with session.get(f"{endpoint_url}{endpoint}", params=params, headers=headers) as response:
                        if response.status != 200:
                            # Try another endpoint if data API fails
                            if retries < max_retries - 1:
                                if retries == 0:  # If data API failed, switch to base endpoints
                                    endpoint_url = BinanceProvider.get_base_url()
                                else:
                                    BinanceProvider.switch_endpoint()
                                retries += 1
                                continue
                            return None
                        
                        data = await response.json()
                        if "price" in data:
                            return float(data["price"])
                        
                        logger.error(f"Invalid response from Binance ticker API: {data}")
                        return None
            except Exception as e:
                logger.error(f"Error getting ticker price from Binance: {str(e)}")
                
                # Try another endpoint
                if retries < max_retries - 1:
                    if retries == 0:  # If data API failed, switch to base endpoints
                        endpoint_url = BinanceProvider.get_base_url()
                    else:
                        BinanceProvider.switch_endpoint()
                    retries += 1
                else:
                    return None
    
    @staticmethod
    async def get_account_info() -> Optional[Dict]:
        """Get account information (requires API key and secret)"""
        # Check if API keys are set
        api_key = BinanceProvider.API_KEY
        api_secret = BinanceProvider.API_SECRET
        
        if not api_key or not api_secret:
            logger.warning("Binance API key and secret are required for account info")
            return None
        
        # Log that we have API credentials
        logger.info(f"Using Binance API key: {api_key[:5]}...{api_key[-5:]}")
        
        retries = 0
        max_retries = 3
        
        while retries < max_retries:    
            try:
                timestamp = int(time.time() * 1000)
                params = {
                    "timestamp": timestamp,
                    "recvWindow": 5000  # Specify the receiving window
                }
                
                # Generate signature
                query_string = urlencode(params)
                signature = hmac.new(
                    api_secret.encode('utf-8'),
                    query_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                endpoint = "/api/v3/account"
                base_url = BinanceProvider.get_base_url()
                
                # Log important details for debugging 
                logger.info(f"Using base URL: {base_url}")
                
                async with aiohttp.ClientSession() as session:
                    headers = {"X-MBX-APIKEY": api_key}
                    
                    url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
                    logger.info(f"Full URL (signature truncated): {url[:100]}...")
                    
                    async with session.get(url, headers=headers) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Binance API error: {response.status}, Response: {error_text}")
                            
                            # Try another endpoint
                            if retries < max_retries - 1:
                                BinanceProvider.switch_endpoint()
                                retries += 1
                                continue
                            return None
                        
                        data = await response.json()
                        if "code" in data and "msg" in data:
                            logger.error(f"Binance API error: {data['msg']} (Code: {data['code']})")
                            return None
                            
                        # Log success
                        logger.info("Successfully retrieved account information from Binance API")
                        return data
            except Exception as e:
                logger.error(f"Error getting account info from Binance: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Try another endpoint
                if retries < max_retries - 1:
                    BinanceProvider.switch_endpoint()
                    retries += 1
                else:
                    return None
    
    @staticmethod
    def _klines_to_dataframe(klines: List) -> pd.DataFrame:
        """Convert Binance klines to pandas DataFrame"""
        # Binance kline format: 
        # [Open time, Open, High, Low, Close, Volume, Close time, Quote asset volume, 
        # Number of trades, Taker buy base asset volume, Taker buy quote asset volume, Ignore]
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 
            'close_time', 'quote_volume', 'trades', 'taker_base_volume', 
            'taker_quote_volume', 'ignore'
        ])
        
        # Convert types
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['open'] = pd.to_numeric(df['open'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])
        
        # Set timestamp as index
        df.set_index('timestamp', inplace=True)
        
        return df
    
    @staticmethod
    def _calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators"""
        # Calculate EMAs
        df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()  # Add EMA20
        df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Calculate MACD
        df['EMA12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['EMA26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA12'] - df['EMA26']
        df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_hist'] = df['MACD'] - df['MACD_signal']
        
        # Clean NaN values
        df.fillna(0, inplace=True)
        
        return df
    
    @staticmethod
    def _format_symbol(instrument: str) -> str:
        """Format instrument symbol for Binance API"""
        logger.info(f"[Binance] Formatting symbol: {instrument}")
        
        # Ensure uppercase and remove slashes
        instrument = instrument.upper().replace("/", "")
        
        # Make sure crypto symbols end with USDT for Binance
        if instrument.endswith("USD") and not instrument.endswith("USDT"):
            instrument = instrument.replace("USD", "USDT")
            logger.info(f"[Binance] Converted USD to USDT: {instrument}")
        
        # Handle common crypto symbols without USD suffix (e.g., BTC -> BTCUSDT)
        common_crypto_symbols = ["BTC", "ETH", "XRP", "DOT", "ADA", "SOL", "DOGE", "AVAX", "MATIC"]
        if instrument in common_crypto_symbols:
            instrument = f"{instrument}USDT"
            logger.info(f"[Binance] Added USDT suffix to common crypto: {instrument}")
        
        logger.info(f"[Binance] Final formatted symbol: {instrument}")
        return instrument
    
    @staticmethod
    async def create_order(symbol: str, side: str, order_type: str, quantity: float, price: float = None, 
                           time_in_force: str = "GTC") -> Optional[Dict]:
        """
        Create and execute an order on Binance

        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            side: Order side (BUY or SELL)
            order_type: Order type (LIMIT, MARKET, STOP_LOSS, etc.)
            quantity: Order quantity
            price: Order price (required for LIMIT orders)
            time_in_force: Time in force (GTC, IOC, FOK)

        Returns:
            Optional[Dict]: Order response or None if failed
        """
        # Check if API keys are set
        api_key = BinanceProvider.API_KEY
        api_secret = BinanceProvider.API_SECRET
        
        if not api_key or not api_secret:
            logger.warning("Binance API key and secret are required for creating orders")
            return None
        
        # Format symbol
        formatted_symbol = BinanceProvider._format_symbol(symbol)
        
        # Prepare parameters
        params = {
            "symbol": formatted_symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000  # Specify the receiving window
        }
        
        # Add price if it's a limit order
        if order_type.upper() == "LIMIT" and price is not None:
            params["price"] = price
            params["timeInForce"] = time_in_force
        
        retries = 0
        max_retries = 3
        
        while retries < max_retries:
            try:
                # Generate signature
                query_string = urlencode(params)
                signature = hmac.new(
                    api_secret.encode('utf-8'),
                    query_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                # Prepare endpoint
                endpoint = "/api/v3/order"
                base_url = BinanceProvider.get_base_url()
                
                logger.info(f"Creating {side.upper()} {order_type.upper()} order for {formatted_symbol}")
                
                # Execute order
                async with aiohttp.ClientSession() as session:
                    headers = {"X-MBX-APIKEY": api_key}
                    
                    url = f"{base_url}{endpoint}"
                    full_params = f"{query_string}&signature={signature}"
                    
                    logger.info(f"Sending order to {url} (params truncated): {full_params[:50]}...")
                    
                    async with session.post(url, data=full_params, headers=headers) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Binance API error: {response.status}, Response: {error_text}")
                            
                            # Try another endpoint
                            if retries < max_retries - 1:
                                BinanceProvider.switch_endpoint()
                                retries += 1
                                continue
                            return None
                        
                        data = await response.json()
                        if "code" in data and "msg" in data:
                            logger.error(f"Binance API error: {data['msg']} (Code: {data['code']})")
                            return None
                        
                        logger.info(f"Successfully created order: {data.get('orderId', 'Unknown')} for {formatted_symbol}")
                        return data
                        
            except Exception as e:
                logger.error(f"Error creating order on Binance: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Try another endpoint
                if retries < max_retries - 1:
                    BinanceProvider.switch_endpoint()
                    retries += 1
                else:
                    return None 

    @staticmethod
    def _standardize_indicator_names(indicators: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardize indicator names for compatibility with chart service.
        Adds lowercase versions with underscores for all indicators.
        
        Args:
            indicators: Dictionary with original indicator names
            
        Returns:
            Dict: Dictionary with both original and standardized names
        """
        result = indicators.copy()  # Keep original names
        
        # Add standardized versions (lowercase with underscores)
        mapping = {
            "EMA20": "ema_20",
            "EMA50": "ema_50", 
            "EMA200": "ema_200",
            "RSI": "rsi",
            "MACD.macd": "macd",
            "MACD.signal": "macd_signal",
            "MACD.hist": "macd_hist"
        }
        
        # Add all standardized versions
        for orig_key, std_key in mapping.items():
            if orig_key in indicators:
                result[std_key] = indicators[orig_key]
        
        return result 
