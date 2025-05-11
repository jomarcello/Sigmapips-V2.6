import asyncio
import logging
from trading_bot.services.sentiment_service import MarketSentimentService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_sentiment_format():
    logger.info("Testing sentiment formatting...")
    
    # Initialize the service
    service = MarketSentimentService()
    
    # Get formatted sentiment for GBPUSD
    formatted_data = await service.get_telegram_sentiment("GBPUSD")
    
    # Print the formatted data
    print("\n" + "-" * 80)
    print("FORMATTED SENTIMENT OUTPUT:")
    print("-" * 80)
    print(formatted_data)
    print("-" * 80)
    
    logger.info("Test completed")

if __name__ == "__main__":
    asyncio.run(test_sentiment_format()) 