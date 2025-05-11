import json
import os
from typing import Optional, Dict, Any, List
import asyncio
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

class TavilyService:
    def __init__(self, api_key: Optional[str] = None, api_timeout: int = 30, metrics=None):
        # Use OpenAI API key directly
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.api_timeout = api_timeout
        self.metrics = metrics
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.MAX_RETRIES = 3  # Maximum number of retry attempts for API calls
        
        # Log initialization
        if self.client:
            masked_key = f"sk-...{self.api_key[-4:]}" if len(self.api_key) > 8 else "sk-..."
            logger.info(f"TavilyService initialized with OpenAI API key: {masked_key}")
        else:
            logger.warning("No OpenAI API key provided. Service will not work.")

    async def _get_tavily_sentiment_analysis(self, instrument: str, market_type: str, search_topic: str, retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """Get sentiment analysis using OpenAI gpt-4o-mini model."""
        if not self.client:
            logger.error(f"OpenAI client not available for {instrument}. Returning error structure.")
            return self._generate_error_sentiment(instrument, market_type, "OpenAI client not available during analysis.")
        
        prompt = f"""Provide a comprehensive market sentiment analysis for {instrument} in the {market_type} market.

Please include:
1. A thorough analysis of recent market movements
2. Relevant economic data and their impact
3. Technical analysis insights
4. Central bank policies affecting the instrument
5. Geopolitical factors if relevant

Format your response as the following JSON:

```json
{{
  "overall_sentiment": "bullish/bearish/neutral",
  "sentiment_emoji": "📈/📉/➖",
  "percentage_breakdown": {{
    "bullish": 0-100,
    "bearish": 0-100,
    "neutral": 0-100
  }},
  "market_summary": "A comprehensive 2-3 paragraph summary of the current market situation, including key economic indicators, recent price movements, and market sentiment",
  "key_drivers": [
    {{
      "factor": "Economic indicator or event name",
      "impact": "Detailed explanation of how this factor impacts the market (2-3 sentences)",
      "importance": "high/medium/low"
    }},
    // Include 4-6 key drivers with detailed explanations
  ],
  "technical_analysis": {{
    "trend": "uptrend/downtrend/sideways",
    "support_levels": [level1, level2],
    "resistance_levels": [level1, level2],
    "key_indicators": [
      {{
        "indicator": "Name of technical indicator",
        "signal": "Description of what this indicator is showing (1-2 sentences)",
        "direction": "bullish/bearish/neutral"
      }},
      // Include 3-4 technical indicators
    ]
  }},
  "news_analysis": [
    {{
      "headline": "Important news headline",
      "summary": "Brief summary of the news and its market impact (2-3 sentences)",
      "impact_level": "high/medium/low",
      "sentiment": "bullish/bearish/neutral"
    }},
    // Include 3-5 recent significant news items
  ]
}}
```

CRITICAL REQUIREMENTS:
1. Provide detailed and substantive analysis, not just brief headlines
2. Calculate sentiment percentages that sum to 100%
3. Include 4-6 detailed key drivers with thorough explanations
4. Ensure technical analysis includes specific price levels and indicator readings
5. Include 3-5 recent significant news items with detailed summaries
6. Format must be valid JSON that parses exactly as shown
        """

        try:
            logger.info(f"Sending request to OpenAI gpt-4o-mini for {instrument} sentiment analysis")
            
            # Create API request with minimal parameters for gpt-4o-mini
            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Correct model name
                messages=[
                    {"role": "system", "content": "You are an expert financial market analyst with deep knowledge of global markets, economic indicators, and technical analysis. Provide comprehensive, detailed, and insightful market analysis with specific data points and thorough explanations."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            # Process the synchronous response
            if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
                content = completion.choices[0].message.content
                try:
                    parsed_content = json.loads(content)
                    logger.info(f"Successfully generated detailed sentiment analysis for {instrument}")
                    return parsed_content
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response for {instrument}: {e}. Response excerpt: {content[:200]}...")
                    self.metrics.record_error('json_decode_error', instrument)
                    return None
            else:
                logger.warning(f"Empty response from OpenAI for {instrument}")
                return await self._get_standard_analysis(instrument, market_type, search_topic)

        except Exception as e:
            logger.error(f"An unexpected error occurred during OpenAI API call for {instrument}: {str(e)}", exc_info=True)
            self.metrics.record_error('openai_unexpected_error', instrument)
            return None
            
    async def _get_standard_analysis(self, instrument: str, market_type: str, search_topic: str) -> Dict[str, Any]:
        """Generate a standard fallback analysis when API calls fail"""
        logger.warning(f"Using fallback standard analysis for {instrument}")
        
        # Create a basic sentiment analysis with neutral stance
        return {
            "overall_sentiment": "neutral",
            "sentiment_emoji": "➖",
            "percentage_breakdown": {
                "bullish": 33,
                "bearish": 33,
                "neutral": 34
            },
            "market_summary": f"Unable to retrieve detailed market analysis for {instrument}. Using neutral sentiment by default. The market appears to be in a consolidation phase with no clear directional bias at this time. Traders should wait for more definitive signals before taking positions.",
            "key_drivers": [
                {
                    "factor": "API limitations",
                    "impact": "Unable to retrieve real-time market data due to technical limitations.",
                    "importance": "high"
                }
            ],
            "technical_analysis": {
                "trend": "sideways",
                "support_levels": [0, 0],
                "resistance_levels": [0, 0],
                "key_indicators": [
                    {
                        "indicator": "No data available",
                        "signal": "No signal available due to data retrieval issues",
                        "direction": "neutral"
                    }
                ]
            },
            "news_analysis": [
                {
                    "headline": "No recent news available",
                    "summary": "Unable to retrieve recent market news due to technical limitations.",
                    "impact_level": "medium",
                    "sentiment": "neutral"
                }
            ]
        }
    
    def _generate_error_sentiment(self, instrument: str, market_type: str, error_message: str) -> Dict[str, Any]:
        """Generate an error sentiment response"""
        return {
            "overall_sentiment": "neutral",
            "sentiment_emoji": "⚠️",
            "percentage_breakdown": {
                "bullish": 0,
                "bearish": 0,
                "neutral": 100
            },
            "market_summary": f"Error: {error_message}. Unable to perform market analysis for {instrument} at this time.",
            "key_drivers": [
                {
                    "factor": "Service unavailable",
                    "impact": "Market analysis service is currently experiencing technical difficulties.",
                    "importance": "high"
                }
            ],
            "technical_analysis": {
                "trend": "unknown",
                "support_levels": [],
                "resistance_levels": [],
                "key_indicators": [
                    {
                        "indicator": "Error",
                        "signal": "No signal available due to service error",
                        "direction": "neutral"
                    }
                ]
            },
            "news_analysis": [
                {
                    "headline": "Service Error",
                    "summary": "Unable to retrieve market news due to service error.",
                    "impact_level": "high",
                    "sentiment": "neutral"
                }
            ]
        }
        
    def format_telegram_sentiment(self, sentiment_data: Dict[str, Any], instrument: str) -> str:
        """
        Format sentiment data in a Telegram-friendly format with rich emoji formatting
        
        Args:
            sentiment_data: The sentiment data dictionary
            instrument: The market instrument
            
        Returns:
            str: Formatted text for Telegram with HTML formatting and emojis
        """
        # Extract data
        overall = sentiment_data.get("overall_sentiment", "neutral").lower()
        
        # Get emoji based on sentiment
        if overall == "bullish":
            sentiment_emoji = "📈"
            sentiment_header = "🟢 BULLISH"
        elif overall == "bearish":
            sentiment_emoji = "📉"
            sentiment_header = "🔴 BEARISH"
        else:
            sentiment_emoji = "⚖️"
            sentiment_header = "⚪️ NEUTRAL"
            
        # Get percentage breakdown
        breakdown = sentiment_data.get("percentage_breakdown", {})
        bullish_pct = breakdown.get("bullish", 33)
        bearish_pct = breakdown.get("bearish", 33)
        neutral_pct = breakdown.get("neutral", 34)
        
        # Get market summary and other components
        market_summary = sentiment_data.get("market_summary", "No market summary available.")
        
        # Format key drivers with emojis
        key_drivers_data = sentiment_data.get("key_drivers", [])
        key_drivers_text = ""
        
        driver_emojis = {
            "high": "🔥",
            "medium": "⚡️",
            "low": "ℹ️"
        }
        
        for i, driver in enumerate(key_drivers_data[:5]):  # Limit to 5 key drivers
            importance = driver.get("importance", "medium")
            emoji = driver_emojis.get(importance, "⚡️")
            factor = driver.get("factor", "Unknown factor")
            impact = driver.get("impact", "No impact information available.")
            key_drivers_text += f"{emoji} <b>{factor}</b>: {impact}\n\n"
            
        # Format news as a summary paragraph and combine with market summary
        news_data = sentiment_data.get("news_analysis", [])
        
        # Create a combined market and news summary
        combined_summary = f"{market_summary}\n\n"
        
        # If we have news items, format them into a paragraph
        if news_data:
            # Extract headlines and summaries
            news_items = []
            
            for news in news_data[:4]:  # Limit to 4 news items for the summary
                headline = news.get("headline", "")
                summary = news.get("summary", "")
                sentiment = news.get("sentiment", "neutral")
                
                # Add this news item to our collection if it has content
                if headline and summary:
                    news_items.append({
                        "headline": headline,
                        "summary": summary,
                        "sentiment": sentiment
                    })
            
            # Create a coherent paragraph from the news items
            if news_items:
                # Add a smooth transition between market summary and news items
                # without an explicit header
                combined_summary += "Recent market news shows "
                
                # Add appropriate sentiment context based on overall sentiment
                if overall == "bullish":
                    combined_summary += "supportive developments: "
                elif overall == "bearish":
                    combined_summary += "challenging conditions: "
                else:
                    combined_summary += "mixed signals: "
                
                # Add each news item to the summary
                for i, item in enumerate(news_items):
                    # Add transitional phrases between news items
                    if i > 0:
                        if i == len(news_items) - 1:
                            combined_summary += " Finally, "
                        else:
                            combined_summary += " Additionally, "
                    
                    # Add the news item content
                    combined_summary += f"{item['headline']}: {item['summary'].rstrip('.')}. "
        
        # Combine all sections with fancy formatting
        formatted_text = f"""<b>🎯 {instrument.upper()} MARKET SENTIMENT {sentiment_emoji}</b>

<b>{sentiment_header}</b> | <i>Market Intelligence Report</i>

<b>📊 SENTIMENT BREAKDOWN:</b>
🟢 Bullish: {bullish_pct}%
🔴 Bearish: {bearish_pct}%
⚪️ Neutral: {neutral_pct}%

<b>🔍 KEY MARKET DRIVERS:</b>
{key_drivers_text}
<b>📈 MARKET SUMMARY:</b>
{combined_summary}

<i>Analysis powered by SigmaPips AI</i>"""

        return formatted_text