# Sentiment service initialization
import logging
import os
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Import the full implementation from sentiment.py
try:
    from .sentiment import MarketSentimentService
    logger.info("Imported full MarketSentimentService implementation from sentiment.py")
except ImportError as e:
    logger.error(f"Failed to import MarketSentimentService from sentiment.py: {str(e)}")
    
    # Fallback implementation if the import fails
    class MarketSentimentService:
        """Service for analyzing market sentiment (simplified fallback version in __init__.py)"""
        
        def __init__(self, cache_ttl_minutes=30, persistent_cache=True, cache_file=None, fast_mode=False):
            """Initialize the market sentiment service"""
            self.use_mock = False
            self.cache_ttl = 30 * 60
            self.fast_mode = fast_mode
            logger.warning("Using FALLBACK MarketSentimentService implementation - the full version could not be imported")
        
        async def get_market_sentiment(self, instrument):
            """Get market sentiment for a given instrument"""
            logger.warning(f"Using fallback get_market_sentiment for {instrument}")
            return self._create_error_sentiment(instrument, "Using fallback MarketSentimentService implementation")
                
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
        
        async def get_telegram_sentiment(self, instrument):
            """Get sentiment analysis formatted specifically for Telegram with rich emoji formatting"""
            try:
                # Get sentiment data
                sentiment_data = await self.get_market_sentiment(instrument)
                
                # Format the sentiment data for Telegram
                return self._format_compact_sentiment_text(
                    instrument, 
                    sentiment_data.get('bullish_percentage', 50), 
                    sentiment_data.get('bearish_percentage', 30),
                    sentiment_data.get('neutral_percentage', 20)
                )
            except Exception as e:
                logger.error(f"Error in get_telegram_sentiment: {str(e)}")
                return f"<b>🎯 {instrument} Market Analysis</b>\n\n⚠️ Error retrieving sentiment data: {str(e)}"
        
        def _format_compact_sentiment_text(self, instrument, bullish_pct, bearish_pct, neutral_pct=None):
            """Format sentiment in compact text format suitable for Telegram"""
            # Calculate neutral if not provided
            if neutral_pct is None:
                neutral_pct = 100 - bullish_pct - bearish_pct
                
            # Use the new format but with fallback message
            formatted_text = f"""<b>🎯 {instrument.upper()} MARKET SENTIMENT 📈</b>

<b>🟢 BULLISH</b> | <i>Market Intelligence Report</i>

<b>📊 SENTIMENT BREAKDOWN:</b>
🟢 Bullish: {bullish_pct}%
🔴 Bearish: {bearish_pct}%
⚪️ Neutral: {neutral_pct}%

<b>🔍 KEY MARKET DRIVERS:</b>
⚠️ <b>Service Unavailable</b>: Using fallback sentiment service. Please check configuration.

<b>📈 MARKET SUMMARY:</b>
Unable to retrieve detailed market analysis. Using fallback service with estimated sentiment values.

<i>Analysis powered by SigmaPips AI</i>"""

            return formatted_text

# Export the class
__all__ = ["MarketSentimentService"]
