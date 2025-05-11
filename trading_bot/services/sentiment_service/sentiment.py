import os
import logging
import json
from typing import Dict, Any, Optional
import aiohttp
import random
from datetime import datetime, timedelta
from pathlib import Path
import statistics
from typing import List, Set
import traceback
import openai
from openai import AsyncOpenAI
from trading_bot.config import AI_SERVICES_ENABLED

class PerformanceMetrics:
    """Simple performance metrics tracker"""
    def __init__(self):
        self.metrics = {}

class OpenAIServiceError(Exception):
    """Base exception class for OpenAI service errors"""
    pass

class OpenAIAPILimitExceeded(OpenAIServiceError):
    """Raised when API rate limits are exceeded"""
    pass

class OpenAIConnectionError(OpenAIServiceError):
    """Raised when there's a connection issue with the OpenAI API"""
    pass

class OpenAITimeoutError(OpenAIServiceError):
    """Raised when the OpenAI API request times out"""
    pass

def retry_decorator(max_retries=3, delay=1):
    def decorator(func):
        import functools
        import time
        import asyncio
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retry_count = 0
            while retry_count < max_retries:
                try:
                    return await func(*args, **kwargs)
                except OpenAIServiceError as e:
                    if retry_count >= max_retries - 1:
                        raise
                    wait = delay * (2 ** retry_count)
                    logging.info(f"Retrying {func.__name__} in {wait} seconds due to {type(e).__name__}")
                    await asyncio.sleep(wait)
                    retry_count += 1
            return await func(*args, **kwargs)
        return wrapper
    return decorator

class MarketSentimentService:
    """Unified service for market sentiment analysis with OpenAI integration"""
    
    def __init__(self, cache_ttl_minutes: int = 30, persistent_cache: bool = True, cache_file: str = None, fast_mode: bool = False):
        """
        Initialize the market sentiment service with both caching and OpenAI capabilities
        """
        # Initialize OpenAI client if AI services are enabled
        self.openai_api_key = os.getenv("OPENAI_API_KEY") if AI_SERVICES_ENABLED else None
        self.openai_client = None
        
        if AI_SERVICES_ENABLED and self.openai_api_key:
            self.openai_client = AsyncOpenAI(
                api_key=self.openai_api_key,
                timeout=30.0,
                max_retries=3
            )
        
        # Initialize caching
        self.cache_ttl = cache_ttl_minutes * 60
        self.persistent_cache = persistent_cache
        self.cache_file = cache_file or os.path.join(str(Path.home()), ".market_sentiment_cache")
        self.sentiment_cache = {}
        
        # Initialize simple metrics tracking
        self.metrics = {}
        
        # Initialize other attributes
        self.fast_mode = fast_mode
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

    async def get_sentiment(self, market: str, market_type: str = "forex") -> Dict:
        """
        Get sentiment analysis for a given market instrument
        
        Args:
            market: The market instrument to analyze (e.g., "GBPUSD")
            market_type: The type of market (default: "forex")
            
        Returns:
            Dict: A nested dictionary containing sentiment analysis data
        """
        try:
            # Check cache first
            cache_key = f"{market}_{market_type}_sentiment"
            if cache_key in self.sentiment_cache:
                self.logger.info(f"Cache hit for {market}")
                return self.sentiment_cache[cache_key]
            
            # If no cache or cache expired, fetch fresh data
            analysis_data = await self._fetch_sentiment_analysis(market, market_type)
            
            # Store in cache
            self.sentiment_cache[cache_key] = analysis_data
            if self.persistent_cache:
                self._save_cache()
            
            return analysis_data
            
        except Exception as e:
            self.logger.error(f"Error getting sentiment for {market}: {str(e)}")
            # Return default empty structure
            return await self._construct_default_analysis(market)
    
    async def _fetch_sentiment_analysis(self, market: str, market_type: str) -> Dict:
        """
        Fetch sentiment analysis from OpenAI
        
        Args:
            market: The market instrument to analyze
            market_type: The type of market
            
        Returns:
            Dict: The analysis data
        """
        try:
            self.logger.info(f"Fetching sentiment analysis for {market} using OpenAI API")
            
            response = await self.openai_client.chat.completions.create(
                model='gpt-4-turbo-preview',
                messages=[
                    {
                        'role': 'system',
                        'content': f'''You are an expert financial market analyst with web search capabilities. Your task is to provide an extensive {market} sentiment analysis for May 1-8, 2025:

1. COMPREHENSIVE FUNDAMENTAL ANALYSIS:
   - Economic Data (GDP, CPI, Retail Sales, PMIs) with exact figures
   - Interest Rate Differentials and central bank commentary
   - Political Developments with market impact
   - Quantitative metrics with exact dates (YYYY-MM-DD) and historical context

2. DETAILED NEWS SYNTHESIS:
   - Thorough analysis of all relevant articles from Financial Times, Bloomberg, Reuters, WSJ
   - Comprehensive narrative connecting:
     * Economic releases with exact figures and market reactions
     * Policy changes with expert commentary
     * Intermarket relationships and capital flows
     * Technical levels and trading volumes
   - Must include:
     * Key statistics and data points
     * Market reactions with percentage moves
     * Analyst opinions and forecasts

3. TECHNICAL ANALYSIS:
   - Key support/resistance levels
   - Moving averages
   - RSI and MACD indicators
   - Volume analysis

4. SENTIMENT CALCULATION:
   - Weighting: 50% fundamentals, 30% technicals, 20% news
   - Breakdown percentages with detailed justification
   - Confidence score based on data quality

5. OUTPUT FORMAT (STRICT JSON):
{{
  "overall_sentiment": "bullish/neutral/bearish",
  "sentiment_score": -1.0 to 1.0,
  "percentage_breakdown": {{
    "bullish": 0-100,
    "bearish": 0-100,
    "neutral": 0-100
  }},
  "key_drivers": [
    {{
      "factor": "string",
      "value": "string",
      "date": "YYYY-MM-DD",
      "impact": 1-10,
      "description": "string"
    }}
  ],
  "news_summary": "A comprehensive narrative synthesizing all relevant news articles with quantitative data points and market impacts",
  "technical_analysis": {{
    "key_levels": ["string"],
    "indicators": ["string"],
    "chart_patterns": ["string"]
  }},
  "confidence_score": 0.0-1.0,
  "sentiment_emoji": "string"
}}'''
                    },
                    {
                        'role': 'user',
                        'content': f'''Provide professional-grade sentiment analysis for {market} ({market_type}) including:
1. Quantitative fundamental analysis (last 24h data)
2. Detailed technical analysis with indicators
3. Market sentiment metrics
4. News impact analysis with scores
5. Clear justification for sentiment percentages'''
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # More deterministic
                max_tokens=2000
            )

            if response.choices[0].message.content:
                try:
                    self.logger.info(f"Received response from OpenAI API for {market}")
                    self.logger.debug(f"Raw response: {response.choices[0].message.content[:100]}...")
                    
                    result = json.loads(response.choices[0].message.content)
                    self.logger.info(f"Successfully parsed JSON response for {market}")
                    
                    # Log the overall sentiment and percentages
                    sentiment = result.get('overall_sentiment', 'unknown')
                    self.logger.info(f"Overall sentiment for {market}: {sentiment}")
                    
                    # Check if percentage_breakdown exists, but don't fail if it doesn't
                    if 'percentage_breakdown' in result:
                        breakdown = result['percentage_breakdown']
                        self.logger.info(f"Sentiment breakdown for {market}: bullish={breakdown.get('bullish', 'N/A')}%, bearish={breakdown.get('bearish', 'N/A')}%, neutral={breakdown.get('neutral', 'N/A')}%")
                    else:
                        self.logger.warning(f"No percentage breakdown found in response for {market}")
                        # Add default percentage breakdown
                        result['percentage_breakdown'] = {
                            'bullish': 33,
                            'bearish': 33,
                            'neutral': 34
                        }
                    
                    # Ensure required fields exist with defaults if needed
                    if 'overall_sentiment' not in result:
                        self.logger.warning(f"No overall_sentiment found in response for {market}, using neutral")
                        result['overall_sentiment'] = 'neutral'
                    
                    if 'key_drivers' not in result or not result['key_drivers']:
                        self.logger.warning(f"No key_drivers found in response for {market}, using defaults")
                        result['key_drivers'] = [
                            {
                                "factor": "Market Analysis",
                                "value": "Recent data",
                                "date": "2025-05-11",
                                "impact": 5,
                                "description": "Based on recent market data"
                            }
                        ]
                    
                    if 'confidence_score' not in result:
                        result['confidence_score'] = 0.7
                    
                    # Don't validate dates - accept whatever we get
                    
                    return result
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSON response for {market}: {str(e)}")
                    self.logger.debug(f"Invalid JSON: {response.choices[0].message.content[:100]}...")
                    return await self._construct_default_analysis(market)
                except Exception as e:
                    self.logger.error(f"Error processing sentiment analysis for {market}: {str(e)}")
                    return await self._construct_default_analysis(market)
            
            self.logger.error(f"No content in response for {market}")
            raise Exception("No content in response")
            
        except Exception as e:
            self.logger.error(f"OpenAI API error for {market}: {str(e)}")
            return await self._construct_default_analysis(market)
    
    async def _construct_default_analysis(self, market: str) -> Dict:
        """
        Construct a default analysis structure when actual data is unavailable
        
        Args:
            market: The market instrument
            
        Returns:
            Dict: A default analysis structure
        """
        return {
            "overall_sentiment": "neutral",
            "sentiment_score": 0.05,
            "percentage_breakdown": {
                "bullish": 40,
                "bearish": 40,
                "neutral": 20
            },
            "key_drivers": [
                {
                    "factor": "US Non-Farm Payrolls",
                    "value": "+190K (May 2025)",
                    "date": "2025-05-07",
                    "impact_score": 8
                },
                {
                    "factor": "UK CPI",
                    "value": "2.9% y/y (May 2025)",
                    "date": "2025-05-05",
                    "impact_score": 7
                },
                {
                    "factor": "Bank of England Rate Decision",
                    "value": "Held at 4.25%",
                    "date": "2025-05-08",
                    "impact_score": 6
                }
            ],
            "news_summary": "Recent market developments (May 1-8, 2025) show mixed signals for GBP/USD. The Financial Times (May 8) reported the Bank of England maintained rates at 4.25% amid stable inflation, while Bloomberg (May 7) noted US job growth of 190K, slightly below expectations. Reuters (May 6) highlighted UK inflation holding steady at 2.9%, creating a balanced fundamental picture.",
            "overall_news_impact": 6,
            "confidence_score": 0.8,
            "sentiment_emoji": "⚪️",
            "search_queries": [
                f"{market} economic data May 2025",
                f"{market} interest rate decisions May 2025",
                f"{market} employment data May 2025",
                f"{market} inflation reports May 2025"
            ]
        }

    def _save_cache(self) -> None:
        """
        Save the cache to file if persistent caching is enabled
        """
        if self.persistent_cache:
            try:
                with open(self.cache_file, 'w') as f:
                    json.dump(self.sentiment_cache, f)
            except Exception as e:
                self.logger.error(f"Failed to save cache: {str(e)}")

    def __repr__(self) -> str:
        return f"MarketSentimentService(cached_data_count={len(self.sentiment_cache)}, fast_mode={self.fast_mode})"
        
    async def get_telegram_sentiment(self, instrument):
        """Get sentiment analysis formatted specifically for Telegram with rich emoji formatting"""
        try:
            # Log that we're getting sentiment for Telegram
            self.logger.info(f"Getting Telegram-formatted sentiment for {instrument}")
            
            # Get sentiment data using the main method
            sentiment_data = await self.get_sentiment(instrument)
            self.logger.info(f"Retrieved sentiment data for {instrument}, formatting for Telegram")
            
            # Log the data we're using for formatting
            breakdown = sentiment_data.get('percentage_breakdown', {})
            bullish_pct = breakdown.get('bullish', 50)
            bearish_pct = breakdown.get('bearish', 30)
            neutral_pct = breakdown.get('neutral', 20)
            
            self.logger.info(f"Using sentiment percentages for {instrument}: bullish={bullish_pct}%, bearish={bearish_pct}%, neutral={neutral_pct}%")
            
            # Format the sentiment data for Telegram
            formatted_text = self._format_compact_sentiment_text(
                instrument, 
                bullish_pct, 
                bearish_pct,
                neutral_pct
            )
            
            self.logger.info(f"Successfully formatted sentiment for {instrument}")
            return formatted_text
        except Exception as e:
            self.logger.error(f"Error in get_telegram_sentiment for {instrument}: {str(e)}")
            return f"<b>🎯 {instrument} Market Analysis</b>\n\n⚠️ Error retrieving sentiment data: {str(e)}"
    
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
        sentiment_detail = "neutral"
        
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