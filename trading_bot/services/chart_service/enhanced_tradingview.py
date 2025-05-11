import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List

# TradingView TA bibliotheek
from tradingview_ta import TA_Handler, Interval, Exchange

# Set up logging
logger = logging.getLogger(__name__)

class EnhancedTradingView:
    """
    Enhanced TradingView API wrapper voor het ophalen van accurate dagelijkse high/low waarden
    en andere technische analyse data van TradingView.
    """
    
    # Mapping van timeframes naar TradingView intervallen
    TIMEFRAME_MAP = {
        "1m": Interval.INTERVAL_1_MINUTE,
        "5m": Interval.INTERVAL_5_MINUTES,
        "15m": Interval.INTERVAL_15_MINUTES,
        "30m": Interval.INTERVAL_30_MINUTES,
        "1h": Interval.INTERVAL_1_HOUR,
        "4h": Interval.INTERVAL_4_HOURS,
        "1d": Interval.INTERVAL_1_DAY,
        "1w": Interval.INTERVAL_1_WEEK,
        "1M": Interval.INTERVAL_1_MONTH,
    }
    
    # Mapping van symbolen naar TradingView format voor screener en exchange
    SYMBOL_MAP = {
        # Forex paren
        "EURUSD": ("forex", "FX_IDC"),
        "GBPUSD": ("forex", "FX_IDC"),
        "USDJPY": ("forex", "FX_IDC"),
        "AUDUSD": ("forex", "FX_IDC"),
        "USDCAD": ("forex", "FX_IDC"),
        "USDCHF": ("forex", "FX_IDC"),
        "NZDUSD": ("forex", "FX_IDC"),
        # Commodities
        "XAUUSD": ("cfd", "TVC", "GOLD"),  # Gold op TVC
        "XAGUSD": ("cfd", "TVC", "SILVER"),  # Silver op TVC
        "XTIUSD": ("cfd", "TVC", "USOIL"),  # WTI Olie op TVC
        "XBRUSD": ("cfd", "TVC", "UKOIL"),  # Brent Olie op TVC
        # Aandelen
        "AAPL": ("america", "NASDAQ"),
        "MSFT": ("america", "NASDAQ"),
        "GOOGL": ("america", "NASDAQ"),
        "AMZN": ("america", "NASDAQ"),
        # Indices - note: technische analyse voor indices is niet ondersteund door TradingView
        "US500": ("america", "CBOE", "SPX500"),  # S&P 500 index via CBOE
        "NAS100": ("america", "NASDAQ", "NDX"),  # Nasdaq 100 index
        "US30": ("america", "DJ", "DJI"),        # Dow Jones index
        # Crypto
        "BTCUSD": ("crypto", "BINANCE"),
        "ETHUSD": ("crypto", "BINANCE"),
    }

    @staticmethod
    def _format_symbol(symbol: str) -> Tuple[str, str, str]:
        """Format een handelssymbool voor gebruik met TradingView API"""
        if symbol in EnhancedTradingView.SYMBOL_MAP:
            mapping = EnhancedTradingView.SYMBOL_MAP[symbol]
            if len(mapping) == 3:
                # Speciale gevallen met alternatieve symbool namen
                screener, exchange, alt_symbol = mapping
                return screener, exchange, alt_symbol
            else:
                # Normale gevallen zonder symbool wijziging
                screener, exchange = mapping
                return screener, exchange, symbol
        
        # Fallback: probeer een standaard mapping
        if symbol.endswith("USD") and symbol.startswith("X"):
            # Metaal/commodities in cfd format
            metal_symbol = "GOLD" if "XAU" in symbol else "SILVER" if "XAG" in symbol else symbol
            return "cfd", "TVC", metal_symbol
        elif symbol.endswith("USD") and not symbol.startswith("X"):
            # Crypto format aanname
            return "crypto", "BINANCE", symbol
        elif len(symbol) <= 5 and not symbol.startswith("X"):
            # Aandeel formaat aanname
            return "america", "NASDAQ", symbol
        else:
            # Forex formaat aanname
            return "forex", "FX_IDC", symbol

    @staticmethod
    def _map_timeframe(timeframe: str) -> str:
        """Converteer timeframe naar TradingView interval"""
        if timeframe in EnhancedTradingView.TIMEFRAME_MAP:
            return EnhancedTradingView.TIMEFRAME_MAP[timeframe]
        
        # Fallback to default
        logger.warning(f"[EnhancedTradingView] Onbekend timeframe '{timeframe}', valt terug op 1h")
        return EnhancedTradingView.TIMEFRAME_MAP["1h"]

    @staticmethod
    def get_multiple_timeframes(symbol: str, timeframes: List[str] = ["1d", "1h", "15m"]) -> Dict[str, Any]:
        """
        Haal data op van meerdere timeframes om een complete set van technische indicatoren te krijgen
        inclusief de echte dagelijkse high/low waarden
        
        Args:
            symbol: Het handelssymbool (bijv. EURUSD, AAPL)
            timeframes: Lijst van timeframes om op te halen
            
        Returns:
            Dict: Geaggregeerde data met indicators van verschillende timeframes
        """
        results = {}
        daily_data = None
        
        try:
            # Formatteer symbool voor TradingView
            screener, exchange, tv_symbol = EnhancedTradingView._format_symbol(symbol)
            
            logger.info(f"[EnhancedTradingView] Getting data for {symbol} ({tv_symbol}) on multiple timeframes")
            
            # First get daily data for true high/low
            if "1d" in timeframes:
                timeframes.remove("1d")
                timeframes = ["1d"] + timeframes  # Ensure 1d is first
            else:
                timeframes = ["1d"] + timeframes  # Add 1d if not present
            
            # Get data for each timeframe
            for tf in timeframes:
                interval = EnhancedTradingView._map_timeframe(tf)
                
                try:
                    handler = TA_Handler(
                        symbol=tv_symbol,
                        screener=screener,
                        exchange=exchange,
                        interval=interval
                    )
                    
                    analysis = handler.get_analysis()
                    
                    if tf == "1d":
                        # Save daily data separately
                        daily_data = analysis
                        
                    # Store the results
                    results[tf] = {
                        "summary": analysis.summary,
                        "oscillators": analysis.oscillators,
                        "moving_averages": analysis.moving_averages,
                        "indicators": analysis.indicators,
                    }
                    
                    logger.info(f"[EnhancedTradingView] Successfully retrieved {tf} data for {symbol}")
                    
                except Exception as e:
                    logger.error(f"[EnhancedTradingView] Error getting {tf} data for {symbol}: {str(e)}")
            
            # Process the data to get true high/low values
            if daily_data:
                daily_indicators = daily_data.indicators
                
                # Extract the true daily high/low values
                true_daily_high = daily_indicators.get("high", None)
                true_daily_low = daily_indicators.get("low", None)
                current_price = daily_indicators.get("close", None)
                
                # Store the final result with all timeframes data
                return {
                    "symbol": symbol,
                    "daily_high": true_daily_high,
                    "daily_low": true_daily_low,
                    "current_price": current_price,
                    "timeframes": results,
                    "recommendation": daily_data.summary.get("RECOMMENDATION", "NEUTRAL")
                }
            else:
                logger.error(f"[EnhancedTradingView] Could not get daily data for {symbol}")
                return {
                    "symbol": symbol,
                    "error": "Could not get daily data"
                }
                
        except Exception as e:
            logger.error(f"[EnhancedTradingView] Error in get_multiple_timeframes for {symbol}: {str(e)}")
            import traceback
            logger.error(f"[EnhancedTradingView] {traceback.format_exc()}")
            return {
                "symbol": symbol,
                "error": str(e)
            }
    
    @staticmethod
    def get_accurate_market_data(symbol: str, timeframe: str = "1h") -> Optional[Tuple[pd.DataFrame, Dict[str, Any]]]:
        """
        Haal accurate marktdata op met dag high/low waardes uit de dagelijkse candle.
        
        Args:
            symbol: Het handelssymbool (bijv. EURUSD, AAPL)
            timeframe: Het tijdsinterval voor primaire data (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo)
            
        Returns:
            Tuple[pd.DataFrame, Dict]: (DataFrame met marktdata, dict met indicators en correcte daily high/low waardes)
        """
        try:
            # Haal data op van meerdere timeframes voor een complete set van indicators
            multi_tf_data = EnhancedTradingView.get_multiple_timeframes(symbol, ["1d", timeframe])
            
            if "error" in multi_tf_data:
                logger.error(f"[EnhancedTradingView] Error getting data: {multi_tf_data['error']}")
                return None
            
            # Extract data from primary timeframe
            tf_data = multi_tf_data["timeframes"].get(timeframe, multi_tf_data["timeframes"].get("1d"))
            
            if not tf_data:
                logger.error(f"[EnhancedTradingView] No data for timeframe {timeframe}")
                return None
            
            # Get indicators from the primary timeframe
            indicators = tf_data["indicators"]
            
            # Create DataFrame with OHLC data
            now = datetime.now()
            df = pd.DataFrame({
                'Open': [indicators.get("open", multi_tf_data["current_price"])],
                'High': [indicators.get("high", multi_tf_data["current_price"] * 1.001)],
                'Low': [indicators.get("low", multi_tf_data["current_price"] * 0.999)],
                'Close': [indicators.get("close", multi_tf_data["current_price"])],
                'Volume': [indicators.get("volume", 0)]
            }, index=[now])
            
            # Daily high and low from the 1d timeframe
            daily_high = multi_tf_data["daily_high"]
            daily_low = multi_tf_data["daily_low"]
            
            # Verify the values are realistic
            if daily_high is None or daily_low is None:
                logger.warning(f"[EnhancedTradingView] Missing daily high/low for {symbol}")
                daily_high = indicators.get("high", multi_tf_data["current_price"] * 1.01)
                daily_low = indicators.get("low", multi_tf_data["current_price"] * 0.99)
            
            # Log the values we're using
            current_price = multi_tf_data["current_price"]
            logger.info(f"[EnhancedTradingView] REAL TV data: Current={current_price}, Daily High={daily_high}, Daily Low={daily_low}")
            
            # Build metadata with technical indicators
            metadata = {
                "close": current_price,
                "open": indicators.get("open", current_price),
                "high": indicators.get("high", current_price),
                "low": indicators.get("low", current_price),
                "daily_high": daily_high,
                "daily_low": daily_low,
                # Technical indicators from requested timeframe
                "rsi": indicators.get("RSI", None),
                "macd": indicators.get("MACD.macd", None),
                "macd_signal": indicators.get("MACD.signal", None),
                "stochastic_k": indicators.get("Stoch.K", None),
                "stochastic_d": indicators.get("Stoch.D", None),
                "adx": indicators.get("ADX", None),
                "cci": indicators.get("CCI20", None),
                "atr": indicators.get("ATR", None),
                # Moving averages
                "sma_20": indicators.get("SMA20", None),
                "sma_50": indicators.get("SMA50", None),
                "sma_200": indicators.get("SMA200", None),
                "ema_20": indicators.get("EMA20", None),
                "ema_50": indicators.get("EMA50", None),
                "ema_200": indicators.get("EMA200", None),
                # Overall recommendation
                "recommendation": multi_tf_data["recommendation"]
            }
            
            return df, metadata
            
        except Exception as e:
            logger.error(f"[EnhancedTradingView] Error in get_accurate_market_data for {symbol}: {str(e)}")
            import traceback
            logger.error(f"[EnhancedTradingView] {traceback.format_exc()}")
            return None 
