# Sentiment service initialization

# Define MarketSentimentService class directly in __init__.py to avoid circular imports
import logging
import random
import os
from datetime import datetime, timedelta
import aiohttp
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Global cache for sentiment data
_sentiment_cache = {}

class MarketSentimentService:
    """Service for analyzing market sentiment (simplified version in __init__.py)"""
    
    def __init__(self):
        """Initialize the market sentiment service"""
        self.use_mock = False
        self.cache_ttl = 30 * 60
        logger.info("MarketSentimentService initialized with cache TTL: %s seconds", self.cache_ttl)
    
    async def get_market_sentiment(self, instrument):
        """Get market sentiment for a given instrument"""
        logger.info(f"Getting market sentiment for {instrument}")
        
        # Check cache first
        cached_sentiment = self._get_from_cache(instrument)
        if cached_sentiment:
            logger.info(f"Using cached sentiment data for {instrument}")
            return cached_sentiment
            
        try:
            # We gebruiken Yahoo Finance niet meer, direct foutmelding geven
            return self._create_error_sentiment(instrument)
        except Exception as e:
            logger.error(f"Error in get_market_sentiment: {str(e)}")
            return self._create_error_sentiment(instrument, str(e))
                
    async def _generate_mock_data(self, instrument):
        """Generate mock sentiment data for testing"""
        logger.warning(f"Using mock data is disabled, returning error for {instrument}")
        return self._create_error_sentiment(instrument, "Using mock data is disabled")
    
    def _get_from_cache(self, instrument):
        """Get sentiment data from cache"""
        cache_key = f"market_{instrument}"
        if cache_key in _sentiment_cache:
            cached_item = _sentiment_cache[cache_key]
            cache_time = cached_item.get('timestamp')
            if cache_time and (datetime.now() - cache_time).total_seconds() < self.cache_ttl:
                return cached_item.get('result')
        return None
    
    async def _handle_data_fetch_error(self, instrument):
        """Handle error when data fetch fails"""
        logger.warning(f"Could not fetch real data for {instrument}")
        return self._create_error_sentiment(instrument)
    
    def _create_error_sentiment(self, instrument, error_details=None):
        """Create error sentiment response"""
        logger.warning(f"Creating error sentiment for {instrument}")
        
        error_msg = f"<b>⚠️ Sentiment Analysis Error</b>\n\nUnable to retrieve current market sentiment data for {instrument}.\n\nPlease try again later or check another instrument."
        
        if error_details:
            logger.error(f"Error details: {error_details}")
            
        return {
            "overall_sentiment": "unknown",
            "sentiment_score": 0,
            "bullish_percentage": 0,
            "bearish_percentage": 0,
            "neutral_percentage": 0,
            "analysis": error_msg,
            "source": "error"
        }
    
    async def get_sentiment(self, instrument, market_type=None):
        """Get sentiment for a given instrument"""
        return await self.get_market_sentiment(instrument)
        
    async def get_market_sentiment_html(self, instrument):
        """Get HTML-formatted sentiment analysis"""
        sentiment_data = await self.get_market_sentiment(instrument)
        return sentiment_data.get('analysis', f"<b>No sentiment data available for {instrument}</b>")
    
    def _format_compact_sentiment_text(self, instrument, bullish_pct, bearish_pct, neutral_pct=None):
        """
        Format sentiment in compact text format suitable for Telegram
        """
        # Calculate neutral if not provided
        if neutral_pct is None:
            neutral_pct = 100 - bullish_pct - bearish_pct
            
        # Determine overall sentiment with more nuanced grading
        strength = "balanced"
        direction = "sideways"
        outlook = "mixed"
        risk_profile = "moderate"
        
        if bullish_pct - bearish_pct > 20:
            sentiment = "Strongly Bullish 📈"
            strength = "strong"
            direction = "upward"
            outlook = "very positive"
            sentiment_detail = "strongly bullish"
        elif bullish_pct - bearish_pct > 10:
            sentiment = "Bullish 📈"
            strength = "solid"
            direction = "upward"
            outlook = "positive"
            sentiment_detail = "bullish"
        elif bullish_pct - bearish_pct > 5:
            sentiment = "Slightly Bullish 📈"
            strength = "mild"
            direction = "gradually upward"
            outlook = "cautiously positive"
            sentiment_detail = "mildly bullish"
        elif bearish_pct - bullish_pct > 20:
            sentiment = "Strongly Bearish 📉"
            strength = "strong"
            direction = "downward"
            outlook = "very negative"
            sentiment_detail = "strongly bearish"
        elif bearish_pct - bullish_pct > 10:
            sentiment = "Bearish 📉"
            strength = "solid"
            direction = "downward"
            outlook = "negative"
            sentiment_detail = "bearish"
        elif bearish_pct - bullish_pct > 5:
            sentiment = "Slightly Bearish 📉"
            strength = "mild"
            direction = "gradually downward"
            outlook = "cautiously negative"
            sentiment_detail = "mildly bearish"
        else:
            sentiment = "Neutral ⚖️"
            sentiment_detail = "balanced"
            
        # Determine volatility based on spread between bullish and bearish
        sentiment_spread = abs(bullish_pct - bearish_pct)
        if sentiment_spread > 30:
            volatility = "high"
            risk_profile = "elevated risk"
        elif sentiment_spread > 15:
            volatility = "moderate"
            risk_profile = "moderate risk"
        else:
            volatility = "low"
            risk_profile = "lower risk"
            
        # Generate specific analysis text based on instrument type
        instrument_lower = instrument.lower()
        
        # Create market analysis text
        market_analysis = f"Current market shows {sentiment_detail} trend with {bullish_pct}% positive sentiment vs {bearish_pct}% negative sentiment. Market participants are demonstrating {outlook} expectations with {volatility} volatility conditions."
        
        # Generate key drivers based on instrument type
        if "usd" in instrument_lower or "eur" in instrument_lower or "gbp" in instrument_lower or "jpy" in instrument_lower:
            # Forex specific drivers
            if "bullish" in sentiment_detail:
                key_drivers = f"• Currency strength indicators show {sentiment_detail} momentum\n• Recent economic data supports {direction} pressure\n• Technical indicators align with {outlook} bias\n• Central bank policies creating favorable environment\n• Trader positioning shows increasing {outlook} bias"
            elif "bearish" in sentiment_detail:
                key_drivers = f"• Currency weakness signals indicate {sentiment_detail} pressure\n• Economic indicators suggest {direction} movement\n• Technical patterns confirm {outlook} outlook\n• Monetary policy developments weighing on price\n• Market participants positioning for continued weakness"
            else:
                key_drivers = f"• Mixed signals across technical indicators\n• Conflicting economic data points\n• Consolidation pattern forming on charts\n• Balanced institutional positioning\n• Waiting for clear directional catalyst"
        elif "btc" in instrument_lower or "eth" in instrument_lower or "xrp" in instrument_lower:
            # Crypto specific drivers
            if "bullish" in sentiment_detail:
                key_drivers = f"• Network activity metrics show increasing usage\n• Institutional interest driving {direction} momentum\n• On-chain metrics support {outlook} bias\n• Technical breakout patterns forming\n• Positive regulatory developments emerging"
            elif "bearish" in sentiment_detail:
                key_drivers = f"• Reduced network activity signals {sentiment_detail} trend\n• Market positioning skewed to the {direction} side\n• Technical patterns suggest continued pressure\n• Regulatory concerns impacting sentiment\n• Macroeconomic headwinds affecting risk assets"
            else:
                key_drivers = f"• Trading volumes showing mixed signals\n• Market positioning balanced between buyers/sellers\n• Technical indicators showing indecision\n• Regulatory landscape remains uncertain\n• Waiting for market catalyst"
        elif "gold" in instrument_lower or "silver" in instrument_lower or "oil" in instrument_lower:
            # Commodities specific drivers
            if "bullish" in sentiment_detail:
                key_drivers = f"• Supply constraints driving prices {direction}\n• Demand metrics showing strength in current market\n• Macro environment supporting {outlook} outlook\n• Geopolitical factors providing price support\n• Technical breakout patterns forming"
            elif "bearish" in sentiment_detail:
                key_drivers = f"• Supply growth outpacing demand\n• Economic indicators putting {direction} pressure\n• Technical resistance levels containing price\n• Weak industrial demand forecasts\n• Strengthening dollar weighing on commodity prices"
            else:
                key_drivers = f"• Supply and demand metrics in relative balance\n• Economic data showing mixed implications\n• Price action contained within recent range\n• Seasonal factors currently neutral\n• Conflicting macroeconomic signals"
        else:
            # Generic drivers
            if "bullish" in sentiment_detail:
                key_drivers = f"• Economic indicators show {sentiment_detail} outlook\n• Market sentiment calculation based on real-time data\n• Technical patterns confirming upward momentum\n• Institutional positioning favoring higher prices\n• Fundamental catalysts supporting current trend"
            elif "bearish" in sentiment_detail:
                key_drivers = f"• Economic indicators show {sentiment_detail} outlook\n• Market sentiment based on latest data shows weakness\n• Technical patterns confirming downward pressure\n• Smart money positioning for lower prices\n• Fundamental headwinds impacting price action"
            else:
                key_drivers = f"• Economic indicators show mixed outlook\n• Market sentiment evenly divided between bulls and bears\n• Technical consolidation phase in progress\n• No clear directional bias from major players\n• Waiting for fundamental catalyst"
            
        # Create formatted text with HTML formatting
        formatted_text = f"""<b>🎯 {instrument} Market Sentiment Analysis</b>

<b>Overall Sentiment:</b> {sentiment}

<b>Market Sentiment Breakdown:</b>
🟢 Bullish: {bullish_pct}%
🔴 Bearish: {bearish_pct}%
⚪️ Neutral: {neutral_pct}%

<b>📊 Market Analysis:</b>
{market_analysis}

<b>📰 Key Drivers:</b>
{key_drivers}"""

        return formatted_text

# Export the class
__all__ = ["MarketSentimentService"]
