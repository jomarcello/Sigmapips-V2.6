import asyncio
import sys
import os

# Add the current directory to the path so we can import the modules
sys.path.append(os.getcwd())

from trading_bot.services.ai_service.tavily_service import TavilyService
from trading_bot.services.sentiment_service import MarketSentimentService

async def test_sentiment_flow():
    print("Testing GBPUSD sentiment analysis flow...")
    
    # Initialize the sentiment service
    service = MarketSentimentService()
    
    # Get the sentiment data
    print("Fetching sentiment data...")
    sentiment_data = await service.get_market_sentiment("GBPUSD")
    
    print("\n=== Raw Sentiment Data ===\n")
    print(sentiment_data)
    
    # Get the Telegram-formatted sentiment
    print("\n=== Telegram Formatted Sentiment ===\n")
    formatted_data = await service.get_telegram_sentiment("GBPUSD")
    print(formatted_data)
    
    return formatted_data

if __name__ == "__main__":
    result = asyncio.run(test_sentiment_flow())
