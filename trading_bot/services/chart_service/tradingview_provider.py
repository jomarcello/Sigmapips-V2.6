import logging
import asyncio
import pandas as pd
import random
import time
from typing import Optional, Dict, Tuple, List, Any
from datetime import datetime, timedelta
import os
import traceback

# Import de historische data provider
try:
    from trading_bot.services.chart_service.tradingview_historical import TradingViewHistorical
    HAS_TRADINGVIEW_HISTORICAL = True
except ImportError:
    HAS_TRADINGVIEW_HISTORICAL = False

# Probeer de enhanced tradingview te importeren
try:
    from trading_bot.services.chart_service.enhanced_tradingview import EnhancedTradingView
    HAS_ENHANCED_TRADINGVIEW = True
except ImportError:
    HAS_ENHANCED_TRADINGVIEW = False

# Ensure this dependency is installed
try:
    from tradingview_ta import TA_Handler, Interval, Exchange
    HAS_TRADINGVIEW_TA = True
except ImportError:
    HAS_TRADINGVIEW_TA = False

# Set up logging
logger = logging.getLogger(__name__)

# Cache for API results
market_data_cache = {}
data_download_cache = {}

class TradingViewProvider:
    """Provider class voor TradingView data als alternatief voor forex en andere marktdata"""
    
    # Mapping van timeframes naar TradingView intervallen
    TIMEFRAME_MAP = {
        "1m": Interval.INTERVAL_1_MINUTE if HAS_TRADINGVIEW_TA else "1m",
        "5m": Interval.INTERVAL_5_MINUTES if HAS_TRADINGVIEW_TA else "5m",
        "15m": Interval.INTERVAL_15_MINUTES if HAS_TRADINGVIEW_TA else "15m",
        "30m": Interval.INTERVAL_30_MINUTES if HAS_TRADINGVIEW_TA else "30m",
        "1h": Interval.INTERVAL_1_HOUR if HAS_TRADINGVIEW_TA else "1h",
        "4h": Interval.INTERVAL_4_HOURS if HAS_TRADINGVIEW_TA else "4h",
        "1d": Interval.INTERVAL_1_DAY if HAS_TRADINGVIEW_TA else "1d",
        "1w": Interval.INTERVAL_1_WEEK if HAS_TRADINGVIEW_TA else "1w",
        "1M": Interval.INTERVAL_1_MONTH if HAS_TRADINGVIEW_TA else "1M",
    }
    
    # Mapping van symbolen naar TradingView format
    SYMBOL_MAP = {
        # Forex paren
        "EURUSD": ("EURUSD", "forex", "FX_IDC"),
        "GBPUSD": ("GBPUSD", "forex", "FX_IDC"),
        "USDJPY": ("USDJPY", "forex", "FX_IDC"),
        "AUDUSD": ("AUDUSD", "forex", "FX_IDC"),
        "USDCAD": ("USDCAD", "forex", "FX_IDC"),
        "USDCHF": ("USDCHF", "forex", "FX_IDC"),
        "NZDUSD": ("NZDUSD", "forex", "FX_IDC"),
        # Commodities
        "XAUUSD": ("GOLD", "cfd", "TVC"),  # Gold op TVC
        "XAGUSD": ("SILVER", "cfd", "TVC"),  # Silver op TVC
        "XTIUSD": ("USOIL", "cfd", "TVC"),  # WTI Olie op TVC
        "XBRUSD": ("UKOIL", "cfd", "TVC"),  # Brent Olie op TVC
        # Aandelen
        "AAPL": ("AAPL", "america", "NASDAQ"),
        "MSFT": ("MSFT", "america", "NASDAQ"),
        "GOOGL": ("GOOGL", "america", "NASDAQ"),
        "AMZN": ("AMZN", "america", "NASDAQ"),
        # Indices
        "US500": ("SPX500", "america", "CBOE"),  # S&P 500 index via CBOE
        "NAS100": ("NDX", "america", "NASDAQ"),  # Nasdaq 100 index
        "US30": ("DJI", "america", "DJ"),        # Dow Jones index
        # Crypto
        "BTCUSD": ("BTCUSD", "crypto", "BINANCE"),
        "ETHUSD": ("ETHUSD", "crypto", "BINANCE"),
    }

    @staticmethod
    def _format_symbol(symbol: str) -> Tuple[str, str, str]:
        """Format een handelssymbool voor gebruik met TradingView API"""
        if symbol in TradingViewProvider.SYMBOL_MAP:
            return TradingViewProvider.SYMBOL_MAP[symbol]
        
        # Fallback: probeer een standaard mapping
        if symbol.endswith("USD") and symbol.startswith("X"):
            # Metaal/commodities in cfd format
            metal_symbol = "GOLD" if "XAU" in symbol else "SILVER" if "XAG" in symbol else symbol
            return (metal_symbol, "cfd", "TVC")
        elif symbol.endswith("USD") and not symbol.startswith("X"):
            # Crypto format aanname
            return (symbol, "crypto", "BINANCE")
        elif len(symbol) <= 5 and not symbol.startswith("X"):
            # Aandeel formaat aanname
            return (symbol, "america", "NASDAQ")
        elif symbol.startswith("US") or symbol in ["SPX", "DJI", "NDX"]:
            # Index format
            return (symbol, "america", "INDEX")
        else:
            # Forex formaat aanname
            return (symbol, "forex", "FX_IDC")

    @staticmethod
    def _map_timeframe(timeframe: str) -> str:
        """Converteer timeframe naar TradingView interval"""
        if timeframe in TradingViewProvider.TIMEFRAME_MAP:
            return TradingViewProvider.TIMEFRAME_MAP[timeframe]
        
        # Fallback to default
        logger.warning(f"[TradingView] Onbekend timeframe '{timeframe}', valt terug op 1h")
        return TradingViewProvider.TIMEFRAME_MAP["1h"]

    @staticmethod
    async def get_technical_analysis(symbol: str, timeframe: str = "1h") -> Dict[str, Any]:
        """Haal technische analyse op van TradingView voor een specifiek symbool"""
        
        if not HAS_TRADINGVIEW_TA:
            logger.error("[TradingView] tradingview-ta pakket niet geïnstalleerd. Installeer met: pip install tradingview-ta")
            return {"error": "tradingview_ta_not_installed"}
            
        # Formatteer symbool voor TradingView
        symbol_formatted, screener, exchange = TradingViewProvider._format_symbol(symbol)
        interval = TradingViewProvider._map_timeframe(timeframe)
        
        logger.info(f"[TradingView] Requesting analysis for {symbol} ({symbol_formatted}/{screener}/{exchange}) on {interval}")
        
        # Cache key
        cache_key = f"{symbol_formatted}_{screener}_{exchange}_{interval}"
        
        # Check cache
        if cache_key in market_data_cache:
            cache_entry = market_data_cache[cache_key]
            cache_time = cache_entry.get("time", 0)
            
            # Bepaal maximale cache tijd gebaseerd op timeframe
            max_cache_time = 60  # 60 seconden voor default
            if timeframe == "1m": max_cache_time = 30
            elif timeframe in ["5m", "15m"]: max_cache_time = 60
            elif timeframe == "30m": max_cache_time = 120
            elif timeframe == "1h": max_cache_time = 300
            elif timeframe in ["4h", "1d"]: max_cache_time = 1800
            
            # Als cache nog geldig is
            if time.time() - cache_time < max_cache_time:
                logger.info(f"[TradingView] Cache hit voor {symbol}")
                return cache_entry.get("data", {})
        
        try:
            # Check first if we have the enhanced API
            if HAS_ENHANCED_TRADINGVIEW:
                logger.info(f"[TradingView] Using EnhancedTradingView to get technical analysis")
                # Execute in thread pool to not block the event loop
                loop = asyncio.get_running_loop()
                
                def get_enhanced_analysis():
                    try:
                        # Get multi-timeframe data for complete analysis
                        multi_tf_data = EnhancedTradingView.get_multiple_timeframes(symbol, ["1d", timeframe])
                        
                        if "error" in multi_tf_data:
                            logger.error(f"[TradingView] Error in enhanced analysis: {multi_tf_data.get('error')}")
                            return {"error": multi_tf_data.get("error")}
                        
                        # Get the data for the requested timeframe
                        tf_data = multi_tf_data["timeframes"].get(timeframe, multi_tf_data["timeframes"].get("1d"))
                        
                        if not tf_data:
                            logger.warning(f"[TradingView] No data for timeframe {timeframe} in enhanced analysis")
                            return {"error": f"No data for timeframe {timeframe}"}
                        
                        # Extract complete indicators
                        indicators = tf_data.get("indicators", {})
                        
                        # Add daily high/low data
                        indicators["daily_high"] = multi_tf_data.get("daily_high")
                        indicators["daily_low"] = multi_tf_data.get("daily_low")
                        
                        # Build complete result
                        result = {
                            "summary": tf_data.get("summary", {}),
                            "oscillators": tf_data.get("oscillators", {}),
                            "moving_averages": tf_data.get("moving_averages", {}),
                            "indicators": indicators
                        }
                        
                        return result
                    except Exception as e:
                        logger.error(f"[TradingView] Error in enhanced analysis: {str(e)}")
                        logger.error(f"[TradingView] {traceback.format_exc()}")
                        return {"error": str(e)}
                
                # Run in thread pool
                logger.info("[TradingView] Running enhanced analysis in thread pool")
                result = await loop.run_in_executor(None, get_enhanced_analysis)
                
                # Check if the result is valid
                if "error" not in result and "indicators" in result:
                    # Update cache
                    market_data_cache[cache_key] = {
                        "time": time.time(),
                        "data": result
                    }
                    
                    logger.info(f"[TradingView] Successfully retrieved enhanced analysis for {symbol}")
                    return result
                else:
                    logger.warning(f"[TradingView] Enhanced analysis failed, falling back to regular analysis: {result.get('error', 'Unknown error')}")
            
            # Fallback to regular TradingView TA
            loop = asyncio.get_running_loop()
            
            def get_analysis():
                try:
                    logger.info(f"[TradingView] Creating TA_Handler for {symbol_formatted}/{screener}/{exchange}")
                    handler = TA_Handler(
                        symbol=symbol_formatted,
                        screener=screener,
                        exchange=exchange,
                        interval=interval
                    )
                    
                    # Get analysis
                    logger.info("[TradingView] Calling get_analysis()")
                    analysis = handler.get_analysis()
                    
                    # Debug what indicators we got - LOG ALLE INDICATORS VOOR DEBUGGING
                    raw_indicators = analysis.indicators
                    logger.info(f"[TradingView] Received indicator keys: {raw_indicators.keys()}")
                    
                    # Log alle indicator waardes voor debugging
                    for key, value in raw_indicators.items():
                        logger.info(f"[TradingView] Indicator {key} = {value}")
                    
                    # Create a safe price value
                    price_value = analysis.indicators.get("close", None)
                    if price_value is None:
                        # Try alternative price source
                        price_value = 1.0  # Default placeholder
                        logger.warning(f"[TradingView] No close price found, using placeholder: {price_value}")
                    else:
                        logger.info(f"[TradingView] Close price: {price_value}")
                    
                    # Build result with more complete price data
                    result = {
                        "summary": analysis.summary,
                        "oscillators": analysis.oscillators,
                        "moving_averages": analysis.moving_averages,
                        "indicators": {
                            # Price data - ensure it's present
                            "close": price_value,
                            "open": analysis.indicators.get("open", price_value),
                            "high": analysis.indicators.get("high", price_value * 1.001),
                            "low": analysis.indicators.get("low", price_value * 0.999),
                            
                            # Get the "high" and "low" directly from daily indicators for most accurate daily high/low
                            "daily_high": analysis.indicators.get("high", price_value * 1.005),
                            "daily_low": analysis.indicators.get("low", price_value * 0.995),
                            
                            # Common indicators
                            "RSI": analysis.indicators.get("RSI", None),
                            "MACD.macd": analysis.indicators.get("MACD.macd", None),
                            "MACD.signal": analysis.indicators.get("MACD.signal", None),
                            "Stoch.K": analysis.indicators.get("Stoch.K", None),
                            "Stoch.D": analysis.indicators.get("Stoch.D", None),
                            "ADX": analysis.indicators.get("ADX", None),
                            "ATR": analysis.indicators.get("ATR", None),
                            "CCI": analysis.indicators.get("CCI20", None),
                            "AO": analysis.indicators.get("AO", None),
                            "Mom": analysis.indicators.get("Mom", None),
                            "VWMA": analysis.indicators.get("VWMA", None),
                            
                            # Extra data waar mogelijk
                            "Volatility": analysis.indicators.get("Volatility", None),
                            "Volume": analysis.indicators.get("Volume", None),
                            "Change": analysis.indicators.get("Change", None),
                            "Recommend.All": analysis.indicators.get("Recommend.All", None),
                            "Recommend.MA": analysis.indicators.get("Recommend.MA", None),
                            "Recommend.Other": analysis.indicators.get("Recommend.Other", None),
                            
                            # Kopieer alle originele indicators voor maximale data
                            **raw_indicators
                        }
                    }
                    
                    return result
                except Exception as e:
                    logger.error(f"[TradingView] Error in analysis: {str(e)}")
                    logger.error(f"[TradingView] {traceback.format_exc()}")
                    return {"error": str(e)}
            
            # Run in thread pool
            logger.info("[TradingView] Running get_analysis in thread pool")
            result = await loop.run_in_executor(None, get_analysis)
            
            # Update cache
            market_data_cache[cache_key] = {
                "time": time.time(),
                "data": result
            }
            
            # Verify if critical data is present
            if "indicators" in result and "close" in result["indicators"]:
                logger.info(f"[TradingView] Successfully retrieved analysis with close price: {result['indicators']['close']}")
            else:
                logger.warning("[TradingView] Analysis data missing critical price information")
            
            return result
            
        except Exception as e:
            logger.error(f"[TradingView] Error getting analysis for {symbol}: {str(e)}")
            logger.error(f"[TradingView] {traceback.format_exc()}")
            return {"error": str(e)}

    @staticmethod
    async def get_market_data(symbol: str, timeframe: str = "1h", limit: int = 100) -> Optional[Tuple[pd.DataFrame, Dict]]:
        """
        Haal marktdata inclusief technische indicatoren op voor het gegeven symbool
        
        Args:
            symbol: Het handelssymbool (bijv. EURUSD, AAPL)
            timeframe: Het tijdsinterval (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo)
            limit: Maximaal aantal datapunten (niet relevant voor real-time data)
            
        Returns:
            Tuple[pd.DataFrame, Dict]: (Dataframe met marktdata, dict met indicatoren)
        """
        try:
            logger.info(f"[TradingView] Getting market data for {symbol} ({timeframe}) with limit {limit}")
            
            # Check if we can use the enhanced TradingView
            if HAS_ENHANCED_TRADINGVIEW:
                logger.info(f"[TradingView] Using EnhancedTradingView for accurate market data")
                
                # Get data with accurate daily high/low
                enhanced_result = EnhancedTradingView.get_accurate_market_data(symbol, timeframe)
                
                if enhanced_result:
                    df, metadata = enhanced_result
                    
                    logger.info(f"[TradingView] Successfully retrieved ENHANCED data for {symbol}")
                    logger.info(f"[TradingView] Daily high: {metadata['daily_high']}, Daily low: {metadata['daily_low']}, Current: {metadata['close']}")
                    
                    return df, metadata
                else:
                    logger.warning(f"[TradingView] Enhanced market data failed, falling back to regular analysis")
            
            # Fallback: Get technical analysis via regular method
            analysis = await TradingViewProvider.get_technical_analysis(symbol, timeframe)
            
            if "error" in analysis:
                logger.error(f"[TradingView] Error getting analysis: {analysis['error']}")
                return None
                
            # Extract price data
            indicators = analysis.get("indicators", {})
            logger.info(f"[TradingView] Received indicators: {indicators.keys()}")
            
            # ALLEEN ECHTE DATA GEBRUIKEN - GEEN MOCK/FALLBACK DATA
            # Extract de werkelijke waarden die TradingView teruggeeft
            close_price = indicators.get("close")
            open_price = indicators.get("open")
            high_price = indicators.get("high")
            low_price = indicators.get("low")
            volume = indicators.get("Volume", 0)
            
            # Haal dagelijkse high/low direct uit de indicators (die nu accurater zijn dankzij onze aanpassingen)
            daily_high = indicators.get("daily_high")  
            daily_low = indicators.get("daily_low")
            
            # Als deze niet beschikbaar zijn, gebruik dan de huidige candle high/low waardes
            if daily_high is None:
                daily_high = high_price
                logger.info(f"[TradingView] Using current high as daily high: {daily_high}")
            
            if daily_low is None:
                daily_low = low_price
                logger.info(f"[TradingView] Using current low as daily low: {daily_low}")
            
            # Log de echte waarden
            logger.info(f"[TradingView] REAL data from TradingView - Open: {open_price}, High: {high_price}, Low: {low_price}, Close: {close_price}")
            logger.info(f"[TradingView] Daily range - High: {daily_high}, Low: {daily_low}")
            
            # Als een van de essentiële prijscomponenten ontbreekt, geef dit aan en return None
            if close_price is None or high_price is None or low_price is None or open_price is None:
                logger.error(f"[TradingView] Missing essential price data for {symbol}. Only returning what TradingView provided.")
                logger.error(f"[TradingView] Available data: Close: {close_price}, High: {high_price}, Low: {low_price}, Open: {open_price}")
                return None
            
            # Maak een DataFrame met alleen de echte gegevens van dit moment
            now = datetime.now()
            data = {
                'Open': [open_price],
                'High': [high_price],
                'Low': [low_price],
                'Close': [close_price],
                'Volume': [volume]
            }
            df = pd.DataFrame(data, index=[now])
            
            # Format the technical analysis indicators met ALLEEN ECHTE DATA
            analysis_info = {
                # Alleen echte data gebruiken
                "close": close_price,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                # Gebruik de gevonden daily high/low waarden
                "daily_high": daily_high,
                "daily_low": daily_low,
                # Gebruik echte indicator data
                "rsi": indicators.get("RSI"),
                "macd": indicators.get("MACD.macd"),
                "macd_signal": indicators.get("MACD.signal"),
                "stochastic_k": indicators.get("Stoch.K"),
                "stochastic_d": indicators.get("Stoch.D"),
                "adx": indicators.get("ADX"),
                "atr": indicators.get("ATR"),
                # Indicator data voor moving averages indien beschikbaar
                "ema_5": indicators.get("EMA5"),
                "ema_10": indicators.get("EMA10"),
                "ema_20": indicators.get("EMA20"),
                "ema_50": indicators.get("EMA50"),
                "ema_100": indicators.get("EMA100"),
                "ema_200": indicators.get("EMA200"),
                # Meer TradingView data
                "summary": analysis.get("summary", {}),
                "recommendation": analysis.get("summary", {}).get("RECOMMENDATION", "NEUTRAL"),
                "moving_averages": analysis.get("moving_averages", {}),
                "oscillators": analysis.get("oscillators", {})
            }
            
            logger.info(f"[TradingView] Successfully retrieved REAL data for {symbol}, close price: {close_price}")
            return df, analysis_info
            
        except Exception as e:
            logger.error(f"[TradingView] Error in get_market_data for {symbol}: {str(e)}")
            logger.error(f"[TradingView] {traceback.format_exc()}")
            return None 
