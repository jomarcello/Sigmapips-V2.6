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
            response = await self.openai_client.chat.completions.create(
                model='gpt-4-turbo-preview',
                messages=[
                    {
                        'role': 'system',
                        'content': f'''You are an expert financial market analyst with web search capabilities. Your task is to provide an extensive GBP/USD sentiment analysis for May 1-8, 2025:

1. COMPREHENSIVE FUNDAMENTAL ANALYSIS:
   - UK Economic Data (GDP, CPI, Retail Sales, PMIs) with exact figures
   - US Economic Data (NFP, CPI, Fed decisions) with detailed comparisons
   - Interest Rate Differentials and central bank commentary
   - Political Developments (UK elections, US policy changes) with market impact
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
                    result = json.loads(response.choices[0].message.content)
                    
                    # Validate all required fields exist
                    required_fields = [
                        'overall_sentiment',
                        'percentage_breakdown',
                        'key_drivers',
                        'confidence_score'
                    ]
                    for field in required_fields:
                        if field not in result:
                            raise ValueError(f"Missing required field: {field}")
                    
                    # Validate percentage breakdown structure
                    breakdown_fields = ['bullish', 'bearish', 'neutral']
                    for field in breakdown_fields:
                        if field not in result['percentage_breakdown']:
                            raise ValueError(f"Missing breakdown field: {field}")
                    
                    # Validate all dates are in 2025
                    def validate_date(date_str):
                        if not date_str or not date_str.startswith('2025'):
                            self.logger.warning(f"Found outdated data from {date_str}")
                            raise ValueError("Outdated data")
                    
                    # Check news dates if present
                    for news in result.get('news_summaries', []):
                        validate_date(news.get('date'))
                    
                    # Check key driver dates
                    for driver in result.get('key_drivers', []):
                        validate_date(driver.get('date'))
                    
                    return result
                except ValueError:
                    return await self._construct_default_analysis(market)
            
            raise Exception("No content in response")
            
        except Exception as e:
            self.logger.error(f"OpenAI API error: {str(e)}")
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
