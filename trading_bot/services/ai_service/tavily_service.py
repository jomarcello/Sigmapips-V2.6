
import json
from typing import Optional, Dict, Any
import asyncio
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

class TavilyService:
    def __init__(self, api_key: Optional[str] = None, api_timeout: int = 30, metrics=None):
        self.api_key = api_key or os.getenv('TAVILY_API_KEY')
        self.api_timeout = api_timeout
        self.metrics = metrics
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.MAX_RETRIES = 3  # Maximum number of retry attempts for API calls

    async def _get_tavily_sentiment_analysis(self, instrument: str, market_type: str, search_topic: str, retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """Get sentiment analysis from Tavily API."""
        if not self.client:
            logger.error(f"OpenAI client not available for {instrument}. Returning error structure.")
            return self._generate_error_sentiment(instrument, market_type, "OpenAI client not available during analysis.")
        
        prompt = f"""You are an expert financial market analyst specializing in {market_type} markets. Perform a comprehensive web search to analyze {instrument} and provide sentiment analysis in this EXACT format:

```json
{{
  "overall_sentiment": "bullish/bearish/neutral",
  "sentiment_emoji": "📈/📉/➖",
  "percentage_breakdown": {{
    "bullish": 0-100,
    "bearish": 0-100,
    "neutral": 0-100
  }},
  "sentiment_detail": "1-2 sentence summary of key market drivers",
  "key_drivers": [
    "Specific economic indicator 1",
    "Market event 2",
    "Technical pattern 3"
  ],
  "confidence_score": 0.0-1.0,
  "sources": ["news", "economic data", "technical analysis"],
  "timestamp": "ISO 8601",
  "version": "1.0.0"
}}
```

CRITICAL REQUIREMENTS:
1. Use web search to find the LATEST market data (last 24-48 hours)
2. Calculate sentiment percentages that sum to 100%
3. Include 3-5 specific, verifiable key drivers
4. Confidence score must reflect true certainty (≥0.7 to accept)
5. Format must be valid JSON that parses exactly as shown
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",  # Using supported model for function calling
                messages=[
                    {"role": "system", "content": """You are an AI financial market analyst. Your task is to:

1. Analyze {instrument} market conditions
2. Calculate sentiment percentages
3. Identify key drivers
4. Return analysis in JSON format

RULES:
- Use latest available data
- Confidence must be ≥0.7
- Percentages must sum to 100%
- Include emoji matching sentiment
- List verifiable sources"""},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=3000,
                response_format={"type": "json_object"},
                timeout=self.api_timeout,
                functions=[{
                    "name": "web_search",
                    "description": "Search for recent market news and analysis",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query for market news"}
                        },
                        "required": ["query"]
                    }
                }],
                function_call={"name": "web_search"}
            )

            if response.choices and response.choices[0].message and response.choices[0].message.content:
                content = response.choices[0].message.content
                try:
                    parsed_content = json.loads(content)
                    if parsed_content.get("confidence_score", 0) < 0.70 and retry_count < self.MAX_RETRIES:
                        logger.warning(f"Low confidence score ({parsed_content['confidence_score']}) for {instrument}. Retrying.")
                        await asyncio.sleep(min(2**retry_count, 30))
                        return await self._get_tavily_sentiment_analysis(instrument, market_type, search_topic, retry_count + 1)
                    return parsed_content
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response from Tavily for {instrument}: {e}. Response excerpt: {content[:200]}...")
                    self.metrics.record_error('tavily_json_decode_error', instrument)
                    return None

            if response.choices[0].message.tool_calls:
                search_query = json.loads(response.choices[0].message.tool_calls[0].function.arguments)['query']
                logger.info(f"Executing web search for: {search_query}")
                # Here you would implement the actual web search using the query
                # For now we'll return the standard analysis
                return await self._get_standard_analysis(instrument, market_type, search_topic)
            else:
                return await self._get_standard_analysis(instrument, market_type, search_topic)

        except Exception as e:
            logger.error(f"An unexpected error occurred during OpenAI API call for {instrument}: {str(e)}", exc_info=True)
            self.metrics.record_error('tavily_unexpected_error', instrument)
            return None