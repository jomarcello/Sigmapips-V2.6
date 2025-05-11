import asyncio
import os
import sys
from trading_bot.services.sentiment_service.sentiment import MarketSentimentService
from dotenv import load_dotenv

async def analyze_instrument(instrument: str):
    """Analyze market sentiment for given instrument"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Check API key exists
        if not os.getenv("OPENAI_API_KEY"):
            print("Error: OPENAI_API_KEY not found in environment variables")
            return

        # Initialize service with 30 minute cache
        service = MarketSentimentService(cache_ttl_minutes=30)
        
        # Get sentiment analysis
        result = await service.get_sentiment(instrument.upper())
        
        # Print formatted results
        print(f"🎯 {instrument.upper()} Market Sentiment Analysis")
        print(f"\n📈 Overall Sentiment: {result['overall_sentiment']} {result.get('sentiment_emoji', '')}")
        print(f"\n📊 Market Breakdown:")
        print(f"🟢 Bullish: {result['percentage_breakdown']['bullish']}%")
        print(f"🔴 Bearish: {result['percentage_breakdown']['bearish']}%")
        print(f"⚪️ Neutral: {result['percentage_breakdown']['neutral']}%")
        print(f"\n📰 Key Drivers:")
        for driver in result['key_drivers']:
            print(f"• {driver['factor']}: {driver['value']} (Impact: {driver['impact']}/10)")

        if 'news_summary' in result:
            print(f"\n📰 MARKET NEWS SYNTHESIS:\n{result['news_summary']}")
        
        if 'search_queries' in result:
            print(f"\n🔍 Search Queries Used:")
            for query in result['search_queries']:
                print(f"• {query}")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_sentiment.py [INSTRUMENT]")
        print("Example: python test_sentiment.py GBPUSD")
        sys.exit(1)
    
    instrument = sys.argv[1]
    asyncio.run(analyze_instrument(instrument))
