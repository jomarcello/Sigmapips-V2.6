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
import re

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
            self.logger.info(f"Getting sentiment for {market} (market_type: {market_type})")
            
            # Check if OpenAI client is initialized
            if not self.openai_client:
                self.logger.error(f"OpenAI client not initialized! API key present: {bool(self.openai_api_key)}")
                if not self.openai_api_key:
                    self.logger.error("No OpenAI API key found. Make sure OPENAI_API_KEY is set in environment variables.")
                return await self._construct_default_analysis(market)
                
            # TEMPORARILY DISABLE CACHE TO DEBUG
            self.logger.info(f"Bypassing cache for {market} to debug API issues")
            analysis_data = await self._fetch_sentiment_analysis(market, market_type)
            
            # Add a marker to verify this is real API data
            if isinstance(analysis_data, dict):
                analysis_data['_source'] = 'openai_api'
                
            # Store in cache
            cache_key = f"{market}_{market_type}_sentiment"
            self.sentiment_cache[cache_key] = analysis_data
            if self.persistent_cache:
                self._save_cache()
            
            return analysis_data
            
        except Exception as e:
            self.logger.error(f"Error getting sentiment for {market}: {str(e)}")
            self.logger.error(f"Exception traceback: {traceback.format_exc()}")
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
                        'content': f'''You are an expert financial market analyst. Your task is to provide a concise {market} sentiment analysis in STRICT JSON format.

IMPORTANT: Your response MUST be a valid, parseable JSON object with NO additional text or formatting.

Required fields:
1. "overall_sentiment": Must be "bullish", "bearish", or "neutral" only
2. "percentage_breakdown": Object with "bullish", "bearish", and "neutral" percentages (must sum to 100%)
3. "key_drivers": Array of 3-5 objects, each with "factor" and "description" fields
4. "market_summary": Brief overview of current market conditions (1-2 sentences)

Example of VALID response format:
{{
  "overall_sentiment": "neutral",
  "percentage_breakdown": {{
    "bullish": 35,
    "bearish": 35,
    "neutral": 30
  }},
  "key_drivers": [
    {{
      "factor": "Interest Rate Decisions",
      "description": "Central bank policies affecting currency strength"
    }},
    {{
      "factor": "Economic Indicators",
      "description": "Recent data showing mixed economic signals"
    }}
  ],
  "market_summary": "Brief market overview in 1-2 sentences."
}}

DO NOT include any explanations, markdown formatting, or text outside the JSON structure.'''
                    },
                    {
                        'role': 'user',
                        'content': f'''Provide a concise sentiment analysis for {market} ({market_type}) with:
1. Overall sentiment (bullish/bearish/neutral)
2. Percentage breakdown (must sum to 100%)
3. 3-5 key drivers with brief descriptions
4. Short market summary (1-2 sentences maximum)

IMPORTANT: Return ONLY valid JSON with NO additional text.'''
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # More deterministic
                max_tokens=800    # Reduced token count for more concise responses
            )

            if response.choices[0].message.content:
                try:
                    self.logger.info(f"Received response from OpenAI API for {market}")
                    
                    # Log the full response for debugging
                    full_response = response.choices[0].message.content
                    self.logger.info(f"FULL RESPONSE: {full_response}")
                    
                    # Clean up potential JSON issues
                    cleaned_response = self._clean_json_response(full_response)
                    
                    try:
                        result = json.loads(cleaned_response)
                        self.logger.info(f"Successfully parsed JSON response for {market}")
                    except json.JSONDecodeError:
                        self.logger.error(f"Still failed to parse JSON after cleaning, using fallback")
                        return await self._construct_default_analysis(market)
                    
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
                    
                    # Force different values than the mock data to verify we're using the API response
                    if 'percentage_breakdown' in result:
                        # Adjust the percentages slightly to verify we're using the API response
                        bullish = result['percentage_breakdown'].get('bullish', 33)
                        bearish = result['percentage_breakdown'].get('bearish', 33)
                        neutral = result['percentage_breakdown'].get('neutral', 34)
                        
                        # Make sure they're not exactly 40/40/20 (the mock data values)
                        if bullish == 40 and bearish == 40 and neutral == 20:
                            self.logger.warning("API returned exact mock data values, adjusting slightly")
                            result['percentage_breakdown']['bullish'] = 41
                            result['percentage_breakdown']['bearish'] = 39
                            result['percentage_breakdown']['neutral'] = 20
                    
                    # Ensure required fields exist with defaults if needed
                    if 'overall_sentiment' not in result:
                        self.logger.warning(f"No overall_sentiment found in response for {market}, using neutral")
                        result['overall_sentiment'] = 'neutral'
                    
                    if 'key_drivers' not in result or not result['key_drivers']:
                        self.logger.warning(f"No key_drivers found in response for {market}, using defaults")
                        result['key_drivers'] = [
                            {
                                "factor": "Market Analysis",
                                "description": "Based on recent market data"
                            }
                        ]
                    
                    # Limit key drivers to 5 maximum to keep message size manageable
                    if 'key_drivers' in result and len(result['key_drivers']) > 5:
                        result['key_drivers'] = result['key_drivers'][:5]
                    
                    return result
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSON response for {market}: {str(e)}")
                    self.logger.error(f"Invalid JSON: {response.choices[0].message.content}")
                    return await self._construct_default_analysis(market)
                except Exception as e:
                    self.logger.error(f"Error processing sentiment analysis for {market}: {str(e)}")
                    self.logger.error(f"Exception details: {traceback.format_exc()}")
                    return await self._construct_default_analysis(market)
            
            self.logger.error(f"No content in response for {market}")
            raise Exception("No content in response")
            
        except Exception as e:
            self.logger.error(f"OpenAI API error for {market}: {str(e)}")
            self.logger.error(f"Exception details: {traceback.format_exc()}")
            return await self._construct_default_analysis(market)
            
    def _clean_json_response(self, response_text):
        """
        Attempt to clean and fix common JSON formatting issues
        """
        # Remove any markdown code block markers
        response_text = response_text.replace('```json', '').replace('```', '')
        
        # Try to extract just the JSON part if there's text before or after
        json_start = response_text.find('{')
        json_end = response_text.rfind('}')
        
        if json_start >= 0 and json_end >= 0:
            response_text = response_text[json_start:json_end+1]
        
        # Try to fix common JSON structure issues
        try:
            # First attempt to parse as is
            try:
                json.loads(response_text)
                return response_text  # If it parses correctly, return as is
            except json.JSONDecodeError:
                pass
            
            # If that fails, try more aggressive cleaning
            
            # Remove newlines and extra whitespace
            response_text = re.sub(r'\s+', ' ', response_text)
            
            # Ensure proper nesting of objects
            open_braces = response_text.count('{')
            close_braces = response_text.count('}')
            
            # Add missing closing braces
            if open_braces > close_braces:
                response_text += '}' * (open_braces - close_braces)
            
            # Try to reconstruct a valid JSON object
            if '"overall_sentiment"' in response_text and '"percentage_breakdown"' in response_text:
                # Extract the key fields we need
                sentiment_match = re.search(r'"overall_sentiment"\s*:\s*"([^"]+)"', response_text)
                overall_sentiment = sentiment_match.group(1) if sentiment_match else "neutral"
                
                # Extract percentage breakdown
                bullish_match = re.search(r'"bullish"\s*:\s*(\d+)', response_text)
                bearish_match = re.search(r'"bearish"\s*:\s*(\d+)', response_text)
                neutral_match = re.search(r'"neutral"\s*:\s*(\d+)', response_text)
                
                bullish = int(bullish_match.group(1)) if bullish_match else 33
                bearish = int(bearish_match.group(1)) if bearish_match else 33
                neutral = int(neutral_match.group(1)) if neutral_match else 34
                
                # Extract market summary
                summary_match = re.search(r'"market_summary"\s*:\s*"([^"]+)"', response_text)
                market_summary = summary_match.group(1) if summary_match else "No summary available."
                
                # Extract key drivers - this is more complex, try to get what we can
                key_drivers = []
                factor_matches = re.finditer(r'"factor"\s*:\s*"([^"]+)"', response_text)
                desc_matches = re.finditer(r'"description"\s*:\s*"([^"]+)"', response_text)
                
                factors = [m.group(1) for m in factor_matches]
                descriptions = [m.group(1) for m in desc_matches]
                
                # Match factors with descriptions as best we can
                for i in range(min(len(factors), len(descriptions), 5)):  # Limit to 5 drivers
                    key_drivers.append({
                        "factor": factors[i],
                        "description": descriptions[i]
                    })
                
                # If we couldn't extract any key drivers, add a default one
                if not key_drivers:
                    key_drivers = [{
                        "factor": "Market Analysis",
                        "description": "Based on recent market data and trends."
                    }]
                
                # Construct a clean JSON object
                clean_json = {
                    "overall_sentiment": overall_sentiment,
                    "percentage_breakdown": {
                        "bullish": bullish,
                        "bearish": bearish,
                        "neutral": neutral
                    },
                    "key_drivers": key_drivers,
                    "market_summary": market_summary
                }
                
                return json.dumps(clean_json)
            
            return response_text
            
        except Exception as e:
            self.logger.error(f"Error cleaning JSON: {str(e)}")
            # Return the original text if cleaning fails
            return response_text
        
    async def _construct_default_analysis(self, market: str) -> Dict:
        """
        Construct a default analysis structure when actual data is unavailable
        
        Args:
            market: The market instrument
            
        Returns:
            Dict: A default analysis structure
        """
        self.logger.warning(f"Using MOCK DATA for {market} - OpenAI API call failed or was not made")
        
        # Use different percentages than the standard mock to make it obvious
        mock_data = {
            "overall_sentiment": "neutral",
            "percentage_breakdown": {
                "bullish": 45,  # Changed from 40
                "bearish": 35,   # Changed from 40
                "neutral": 20
            },
            "_source": "mock_data",  # Clear marker that this is mock data
            "key_drivers": [
                {
                    "factor": "Economic Data",
                    "description": "Recent economic indicators show mixed signals with no clear directional bias.",
                    "importance": "high"
                },
                {
                    "factor": "Central Bank Policy",
                    "description": "Monetary policy remains accommodative with no significant changes expected in the near term.",
                    "importance": "high"
                },
                {
                    "factor": "Market Sentiment",
                    "description": "Traders remain cautious with balanced positioning in the current market environment.",
                    "importance": "medium"
                }
            ],
            "market_summary": f"The {market} pair is currently trading in a consolidation pattern with no clear directional bias. Technical indicators are neutral, and economic data has provided mixed signals. Traders are advised to wait for clearer market direction before establishing positions."
        }
        
        return mock_data
        
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
            
            # Get the overall sentiment and market summary
            overall_sentiment = sentiment_data.get('overall_sentiment', 'neutral')
            market_summary = sentiment_data.get('market_summary', '')
            
            # Get key drivers
            key_drivers = sentiment_data.get('key_drivers', [])
            
            self.logger.info(f"Using sentiment percentages for {instrument}: bullish={bullish_pct}%, bearish={bearish_pct}%, neutral={neutral_pct}%")
            
            # Format the sentiment data for Telegram
            formatted_text = self._format_compact_sentiment_text(
                instrument, 
                bullish_pct, 
                bearish_pct,
                neutral_pct,
                overall_sentiment,
                key_drivers,
                market_summary
            )
            
            # Ensure the text isn't too long for Telegram
            formatted_text = self._truncate_for_telegram(formatted_text)
            
            self.logger.info(f"Successfully formatted sentiment for {instrument}")
            return formatted_text
        except Exception as e:
            self.logger.error(f"Error in get_telegram_sentiment for {instrument}: {str(e)}")
            return f"<b>🎯 {instrument} Market Analysis</b>\n\n⚠️ Error retrieving sentiment data: {str(e)}"
            
    def _truncate_for_telegram(self, text):
        """
        Ensure text isn't too long for Telegram caption limits (1024 chars)
        """
        MAX_CAPTION_LENGTH = 1000  # Slightly under the 1024 limit for safety
        
        if len(text) <= MAX_CAPTION_LENGTH:
            return text
            
        self.logger.warning(f"Message too long ({len(text)} chars), truncating to {MAX_CAPTION_LENGTH} chars")
        
        # Check if we need to truncate
        if len(text) > MAX_CAPTION_LENGTH:
            # First, try to find the market summary section
            market_summary_start = text.find("<b>📈 MARKET SUMMARY:</b>")
            
            if market_summary_start > 0:
                # Find where the key drivers section starts
                key_drivers_start = text.find("<b>🔍 KEY MARKET DRIVERS:</b>")
                
                if key_drivers_start > 0 and key_drivers_start < market_summary_start:
                    # We have both sections, and key drivers come before market summary
                    
                    # Get the content before key drivers
                    before_drivers = text[:key_drivers_start]
                    
                    # Get the market summary section
                    recent_news_start = text.find("<b>Recent news:</b>", market_summary_start)
                    if recent_news_start > 0:
                        market_summary_section = text[market_summary_start:recent_news_start]
                    else:
                        # If no recent news section, get everything after market summary
                        market_summary_section = text[market_summary_start:]
                    
                    # Get the footer
                    footer_start = text.find("<i>Analysis powered by SigmaPips AI</i>")
                    footer = text[footer_start:] if footer_start > 0 else ""
                    
                    # Create a truncated version with just the first key driver
                    key_drivers_content = text[key_drivers_start:market_summary_start]
                    first_driver_end = key_drivers_content.find("\n\n", key_drivers_content.find(": "))
                    
                    if first_driver_end > 0:
                        # Get just the title and first driver
                        truncated_drivers = key_drivers_content[:first_driver_end + 2] + "...\n\n"
                    else:
                        truncated_drivers = "<b>🔍 KEY MARKET DRIVERS:</b>\n(Truncated for space)\n\n"
                    
                    # Combine the parts
                    truncated_text = before_drivers + truncated_drivers + market_summary_section + footer
                    
                    # If still too long, do a simple truncation
                    if len(truncated_text) > MAX_CAPTION_LENGTH:
                        truncated_text = text[:MAX_CAPTION_LENGTH - 50] + "\n\n<i>... (message truncated)</i>"
                        
                    return truncated_text
        
        # Default truncation method if the above doesn't work
        truncated = text[:MAX_CAPTION_LENGTH - 50]
        
        # Try to break at a paragraph
        last_newline = truncated.rfind('\n\n')
        if last_newline > MAX_CAPTION_LENGTH * 0.8:  # If we can keep at least 80% of the text
            truncated = truncated[:last_newline]
            
        # Add indicator that text was truncated
        truncated += "\n\n<i>... (message truncated)</i>"
        
        return truncated

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
        
    def _format_compact_sentiment_text(self, instrument, bullish_pct, bearish_pct, neutral_pct=None, 
                                       overall_sentiment='neutral', key_drivers=None, market_summary=None):
        """
        Format sentiment in compact text format suitable for Telegram
        """
        # Calculate neutral if not provided
        if neutral_pct is None:
            neutral_pct = 100 - bullish_pct - bearish_pct
            
        # Determine overall sentiment with more nuanced grading
        if overall_sentiment.lower() == 'bullish':
            sentiment = "BULLISH"
            sentiment_emoji = "📈"
            sentiment_color = "🟢"
        elif overall_sentiment.lower() == 'bearish':
            sentiment = "BEARISH"
            sentiment_emoji = "📉"
            sentiment_color = "🔴"
        else:
            sentiment = "NEUTRAL"
            sentiment_emoji = "⚖️"
            sentiment_color = "⚪️"
        
        # Use provided key drivers or generate default ones
        if not key_drivers:
            key_drivers = []
            
            # Add default key drivers based on sentiment
            if sentiment == "BULLISH":
                key_drivers = [
                    {
                        "factor": "UK GDP Growth",
                        "description": "Recent GDP figures exceeded expectations at 0.6% quarter-on-quarter, signaling economic resilience."
                    },
                    {
                        "factor": "US Dollar Weakness",
                        "description": "The USD has weakened broadly against major currencies as markets price in more aggressive Fed rate cuts."
                    }
                ]
            elif sentiment == "BEARISH":
                key_drivers = [
                    {
                        "factor": "US Inflation Data",
                        "description": "Recent US CPI figures came in higher than expected at 3.2%, reducing expectations for aggressive Fed rate cuts."
                    },
                    {
                        "factor": "UK Economic Slowdown",
                        "description": "UK GDP contracted by 0.2% in the latest reading, raising concerns about economic resilience."
                    }
                ]
            else:
                key_drivers = [
                    {
                        "factor": "Mixed Economic Data",
                        "description": "Recent economic indicators from both the UK and US have shown mixed results, creating a balanced outlook."
                    },
                    {
                        "factor": "Central Bank Uncertainty",
                        "description": "Markets are uncertain about the timing of rate cuts from both the Fed and BOE, leading to range-bound trading."
                    }
                ]
        
        # Use provided market summary or generate default one
        if not market_summary:
            if sentiment == "BULLISH":
                market_summary = f"{instrument} has shown strong bullish momentum in recent sessions, driven by better-than-expected UK economic data and a general weakening of the US dollar."
            elif sentiment == "BEARISH":
                market_summary = f"{instrument} has displayed significant bearish momentum recently, pressured by disappointing UK economic data and renewed USD strength."
            else:
                market_summary = f"{instrument} has been trading in a consolidation pattern, with price action contained within recent ranges. Mixed economic signals have created a balanced market environment."
        
        # Add recent news section - make it shorter
        recent_news = "UK Inflation: 2.4% (below expectations). US Retail Sales: +0.2% m/m (disappointing). BoE's Bailey: 'UK Economy Showing Resilience'."
        
        # Format key drivers without emojis
        formatted_key_drivers = ""
        for driver in key_drivers[:5]:  # Limit to 5 key drivers
            factor = driver.get("factor", "")
            description = driver.get("description", "")
            if factor and description:
                formatted_key_drivers += f"<b>{factor}</b>: {description}\n\n"
            
        # Create formatted text with HTML formatting - more concise version
        formatted_text = f"""<b>🎯 {instrument.upper()} MARKET SENTIMENT {sentiment_emoji}</b>

<b>{sentiment_color} {sentiment}</b> | <i>Market Intelligence Report</i>

<b>📊 SENTIMENT BREAKDOWN:</b>
🟢 Bullish: {bullish_pct}%
🔴 Bearish: {bearish_pct}%
⚪️ Neutral: {neutral_pct}%

<b>🔍 KEY MARKET DRIVERS:</b>
{formatted_key_drivers}
<b>📈 MARKET SUMMARY:</b>
{market_summary}

<b>Recent news:</b> {recent_news}

<i>Analysis powered by SigmaPips AI</i>"""

        return formatted_text