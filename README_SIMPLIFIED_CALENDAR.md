# Economic Calendar Service

[![GitHub Repository](https://img.shields.io/badge/GitHub-Sigmapips--V2.6-blue.svg)](https://github.com/jomarcello/Sigmapips-V2.6)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

This simplified Economic Calendar Service uses the **direct TradingView API** to retrieve economic calendar data, making configuration and maintenance easier.

## Why This Simplification?

The original implementation used multiple services (TradingView API, ScrapingAnt, OpenAI) which caused confusion and deployment issues. By choosing a single technique (direct TradingView API), the code is:

1. Easier to understand
2. Simpler to maintain
3. Less dependent on external services
4. More reliable in production

## What Changed?

We've made the following changes:

1. Removed all alternative services (OpenAI o4-mini, ScrapingAnt, BrowserBase)
2. Simplified the calendar.py file to use only the TradingView API
3. Modified __init__.py to activate only the TradingView API
4. Updated documentation to reflect the simplification
5. Added comprehensive error handling and logging

## How It Works

The service makes direct HTTP requests to the TradingView Economic Calendar API to retrieve economic events. If the API is unavailable, it falls back to generated fallback data.

## Configuration

The service uses the following environment variables:

- `CALENDAR_FALLBACK`: Set to "true" to activate fallback mode with mock data if API calls fail
- `DEBUG`: Set to "true" for detailed logging

## Usage

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
```

## Testing

Use the included test script to test the service:

```bash
# Make the script executable
chmod +x run_calendar_test.sh

# Run the test script
./run_calendar_test.sh
```

For testing with the direct API (no fallback):

```bash
# Make the script executable
chmod +x run_calendar_direct_test.sh

# Run the test script
./run_calendar_direct_test.sh
```

## Telegram Integration

Send calendar updates to Telegram:

```bash
# Test mode (console output only)
python send_direct_calendar_update.py --test

# Send to Telegram
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
python send_direct_calendar_update.py
```

## Troubleshooting

If the service doesn't work as expected:

1. Check logs for error messages
2. Test with `CALENDAR_FALLBACK=true` to see if fallback mode works
3. Try setting `DEBUG=true` for more detailed logging
4. Verify the TradingView API is available

## Deployment

When deploying to production:

1. Set up good logging to capture errors
2. Consider a monitoring service to alert on failures
3. Set up automatic retries for API calls
4. Implement rate limiting to avoid API quota issues

## Documentation

For more detailed information, see:

- [Calendar Service Configuration](CALENDAR_SERVICE_CONFIG.md)
- [Calendar Service Guide](CALENDAR_SERVICE_GUIDE.md)
- [Changes Summary](CHANGES_SUMMARY.md)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 