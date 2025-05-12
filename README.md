# Sigmapips Trading Bot

A trading signals and analysis bot for financial markets.

## Features

- **Technical Analysis**: Provides technical analysis for forex and cryptocurrency markets
- **Signal Generation**: Generates trading signals based on various indicators
- **Telegram Integration**: Delivers signals and analysis through Telegram

## Setup Instructions

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up your environment variables:
   ```
   OPENAI_API_KEY=your_openai_key
   TELEGRAM_BOT_TOKEN=your_telegram_token
   PERPLEXITY_API_KEY=your_perplexity_key
   ```
4. Run the bot:
   ```
   python -m trading_bot.main
   ```

## Documentation

For more detailed information, check the documentation in the `/docs` folder.

## Live Bot
Bot is live on Telegram: [@SignapipsAI_bot](https://t.me/SignapipsAI_bot)

## Features

### 1. Telegram Service
- Fully automated signal distribution
- AI-powered signal formatting using GPT-4
- Personalized preferences per user
- Support for multiple markets:
  - Forex
  - Indices 
  - Commodities
  - Crypto
- Interactive buttons for analysis

### 2. Real-time Analysis
- 📊 Technical Analysis Charts
  - Multiple timeframes (1m to 1d)
  - Automatic chart generation
  - Cached for quick access
- 🤖 Market Sentiment Analysis
  - AI-powered sentiment analysis
  - Real-time news processing
  - Perplexity AI integration
- 📅 Economic Calendar
  - Important economic events
  - Impact level filtering
  - Currency-specific events

### 3. Caching & Performance
- Redis caching for:
  - Trading signals
  - Technical analysis charts
  - Market sentiment data
  - Economic calendar events
- Base64 encoding for binary data
- Cache TTL: 1 hour
- Optimal performance through caching

## Tech Stack

### Backend
- FastAPI (Python 3.11)
- python-telegram-bot v20
- Redis for caching
- Supabase (PostgreSQL) for data storage

### AI Services
- OpenAI GPT-4 API for signal formatting
- Perplexity AI for market sentiment
- Custom prompts for consistent output

### Deployment
- Hosted on Railway
- Automatic deployments
- Webhook integration
- Health checks
- Auto-scaling
- Redis persistence

## Setup & Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/sigmapips-bot.git
cd sigmapips-bot
```

2. Create a .env file:
```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# Supabase
SUPABASE_URL=your_supabase_url 
SUPABASE_KEY=your_supabase_key

# Redis
REDIS_URL=your_redis_url

# OpenAI
OPENAI_API_KEY=your_openai_key

# Perplexity
PERPLEXITY_API_KEY=your_perplexity_key

# Railway
RAILWAY_PUBLIC_DOMAIN=your_railway_domain
```

3. Start locally with Docker:
```bash
docker-compose up -d
```

## Bot Commands

- `/start` - Start setting up trading preferences
- `/manage` - Manage existing preferences
- `/menu` - Show main menu
- `/help` - Show help information

## Database Schema

```sql
CREATE TABLE subscriber_preferences (
    id bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id bigint NOT NULL,
    market text NOT NULL,
    instrument text NOT NULL, 
    timeframe text NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()),
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()),
    is_active boolean DEFAULT true,
    UNIQUE(user_id, market, instrument, timeframe)
);
```

## API Endpoints

### Signal Endpoint
```http
POST /signal
{
    "symbol": "EURUSD",
    "action": "BUY/SELL",
    "price": "1.0850",
    "stopLoss": "1.0800",
    "takeProfit": "1.0900",
    "timeframe": "1h",
    "market": "forex"
}
```

### Webhook Endpoint
```http
POST /webhook
- Handles Telegram updates
```

### Health Check
```http
GET /health
- Returns service status
```

## Error Handling

- Extensive logging of all operations
- Automatic retry mechanisms for API calls
- Graceful degradation during service outages
- Fallback options for AI services

## Railway Deployment

The application runs on Railway with:
- Automatic deployments via GitHub
- Webhook integration for Telegram
- Redis persistence for caching
- Health checks for uptime monitoring
- Auto-scaling based on load
- Zero-downtime deployments

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## License

MIT License

## Contact

For questions or suggestions, open an issue or submit a PR.

# ForexFactory Economische Kalender

Deze tools halen economische evenementen op van de ForexFactory kalender en tonen ze in een geformatteerde tabel.

## Functies

- Haal economische evenementen op van ForexFactory.com
- Filter evenementen op datum, valuta en impact niveau
- Sorteer evenementen chronologisch
- Formatteer evenementen in een leesbare tabel
- Sla output op naar bestanden

## Vereisten

- Python 3.6+
- Requests module (`pip install requests`)

## Installatie

1. Download de scripts:
   - `forex_factory_json.py` - Hoofdscript voor het ophalen van de gegevens
   - `forex_events.sh` - Shell-script voor eenvoudig gebruik

2. Maak de scripts uitvoerbaar:
   ```bash
   chmod +x forex_factory_json.py
   chmod +x forex_events.sh
   ```

## Gebruik

### Via het shell-script

Het shell-script biedt een eenvoudige interface voor het Python-script:

```bash
./forex_events.sh [commando]
```

Beschikbare commando's:
- `vandaag` - Toon alle evenementen voor vandaag
- `morgen` - Toon alle evenementen voor morgen
- `gisteren` - Toon alle evenementen voor gisteren
- `week` - Toon alle evenementen voor deze week
- `usd` - Toon alle USD evenementen voor vandaag
- `eur` - Toon alle EUR evenementen voor vandaag
- `gbp` - Toon alle GBP evenementen voor vandaag
- `jpy` - Toon alle JPY evenementen voor vandaag
- `hoog` - Toon alle evenementen met hoge impact voor vandaag
- `usd-hoog` - Toon alle USD evenementen met hoge impact voor vandaag
- `eur-hoog` - Toon alle EUR evenementen met hoge impact voor vandaag
- `opslaan [commando]` - Sla de output op naar een bestand
- `help` - Toon hulptekst

Voorbeelden:
```bash
./forex_events.sh vandaag           # Toon alle evenementen voor vandaag
./forex_events.sh usd-hoog          # Toon alle USD evenementen met hoge impact voor vandaag
./forex_events.sh opslaan week      # Toon alle evenementen voor deze week en sla op naar bestand
```

### Via het Python-script

Voor meer geavanceerd gebruik kun je het Python-script direct aanroepen met argumenten:

```bash
python forex_factory_json.py [opties]
```

Beschikbare opties:
- `--date YYYY-MM-DD` - Toon evenementen voor een specifieke datum
- `--currency CODE` - Filter op valutacode (USD, EUR, GBP, etc.)
- `--impact {high,medium,low,all}` - Filter op impact niveau
- `--tomorrow` - Toon evenementen voor morgen
- `--yesterday` - Toon evenementen voor gisteren
- `--week` - Toon evenementen voor de hele week
- `--save` - Sla de output op naar een bestand

Voorbeelden:
```bash
python forex_factory_json.py --date 2025-05-15 --currency USD --impact high
python forex_factory_json.py --week --save
```

## Output

De output is een geformatteerde tabel met de volgende kolommen:
- Tijd - Tijdstip van het evenement
- Valuta - Valutacode (USD, EUR, etc.)
- Impact - Impact niveau met emoji (🔴 hoog, 🟠 medium, 🟡 laag)
- Evenement - Naam van het economische evenement
- Actueel - Actuele waarde (indien beschikbaar)
- Verwacht - Verwachte waarde (indien beschikbaar)
- Vorig - Vorige waarde (indien beschikbaar)

## Voorbeeld Output

```
Economische Evenementen voor Maandag 12 Mei:

| Tijd      | Valuta | Impact | Evenement                       | Actueel | Verwacht | Vorig    |
|-----------|--------|--------|--------------------------------|---------|----------|----------|
| 1:00am    | JPY    | 🟡     | Economy Watchers Sentiment      |         | 44.7     | 45.1     |
| 4:00am    | GBP    | 🟡     | MPC Member Lombardelli Speaks   |         |          |          |
| 4:03am    | CNY    | 🟠     | New Loans                       |         | 710B     | 3640B    |
...
```

## Opmerking

De data wordt direct opgehaald van de ForexFactory JSON API. Als je te veel verzoeken doet in korte tijd, kun je een 429 (Too Many Requests) foutcode krijgen.

# Sigmapips Trading Bot - Economic Calendar Service

[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A simplified and reliable economic calendar service for the Sigmapips Trading Bot that retrieves financial calendar data from the TradingView API.

## Overview

The Economic Calendar Service provides real-time economic event data for forex, indices, and cryptocurrency markets. This service has been simplified to use only the direct TradingView API, making it more reliable and easier to maintain.

## Features

- **Direct TradingView API Integration**: Reliable data source for economic events
- **Fallback Mechanism**: Continues working even if the API is temporarily unavailable
- **Currency Filtering**: Filter events by specific currencies (USD, EUR, GBP, etc.)
- **Impact Level Filtering**: Focus on high, medium, or low impact events
- **Telegram Integration**: Send formatted calendar updates to Telegram
- **Comprehensive Logging**: Detailed logs for easy troubleshooting
- **Caching**: Reduces API calls and improves performance

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/jomarcello/Sigmapips-V2.6.git
   cd Sigmapips-V2.6
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The service uses the following environment variables:

- `CALENDAR_FALLBACK`: Set to "true" to enable fallback mode if API calls fail
- `DEBUG`: Set to "true" for detailed logging
- `TELEGRAM_BOT_TOKEN`: Telegram bot token (for Telegram integration)
- `TELEGRAM_CHAT_ID`: Telegram chat ID (for Telegram integration)

## Usage

### Basic Usage

```python
from trading_bot.services.calendar_service.calendar import EconomicCalendarService

# Initialize the service
calendar_service = EconomicCalendarService()

# Get calendar data
events = await calendar_service.get_calendar(days_ahead=0, min_impact="Low")

# Format the calendar for display
formatted_calendar = await calendar_service.get_economic_calendar(
    currencies=["USD", "EUR", "GBP"],
    days_ahead=0,
    min_impact="Low"
)

# Get calendar for a specific instrument
instrument_calendar = await calendar_service.get_instrument_calendar(
    instrument="EURUSD",
    days_ahead=0,
    min_impact="Medium"
)
```

### Testing

Use the included test scripts to verify the service is working correctly:

```bash
# Test with fallback mode enabled
./run_calendar_test.sh

# Test with direct API (no fallback)
./run_calendar_direct_test.sh
```

### Telegram Integration

Send calendar updates to Telegram:

```bash
# Test mode (console output only)
python send_direct_calendar_update.py --test

# Send to Telegram
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
python send_direct_calendar_update.py
```

## Documentation

For more detailed information, see:

- [Calendar Service Guide](CALENDAR_SERVICE_GUIDE.md): Comprehensive guide for using the service
- [Calendar Service Configuration](CALENDAR_SERVICE_CONFIG.md): Configuration options and settings
- [Changes Summary](CHANGES_SUMMARY.md): Summary of changes made to simplify the service

## Troubleshooting

If you encounter issues:

1. Check logs for error messages
2. Test with `CALENDAR_FALLBACK=true` to see if fallback mode works
3. Try setting `DEBUG=true` for more detailed logging
4. Verify the TradingView API is available

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
