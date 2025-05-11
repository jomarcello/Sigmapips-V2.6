# Economic Calendar Chronological Formatter

This module provides functions to format economic calendar events in chronological order by time. It is designed to work with the existing TradingViewCalendarService implementation in the trading bot.

## Features

- Display economic calendar events in chronological order by time
- Group events by currency with chronological ordering within groups
- Support for major currencies (USD, EUR, GBP, JPY, CHF, AUD, NZD, CAD)
- Filtering by currency and impact level
- Emoji indicators for currencies and impact levels
- Display of forecast and previous values

## Integration

The chronological formatter has been integrated with the existing TradingViewCalendarService and EconomicCalendarService classes. It provides the following new methods:

### TradingViewCalendarService

```python
async def format_calendar_chronologically(self, events: List[Dict], 
                                         today_formatted: str = None, 
                                         group_by_currency: bool = False) -> str:
    """Format calendar events in chronological order by time."""
```

### EconomicCalendarService

```python
async def format_calendar_chronologically(self, events: List[Dict], 
                                         today_formatted: str = None, 
                                         group_by_currency: bool = False) -> str:
    """Format calendar events in chronological order by time."""
```

## Usage

### Basic Usage

```python
from trading_bot.services.calendar_service.tradingview_calendar import TradingViewCalendarService

# Initialize the service
calendar_service = TradingViewCalendarService()

# Get calendar events
events = await calendar_service.get_calendar(days_ahead=0, min_impact="Low")

# Format events chronologically
chronological_calendar = await calendar_service.format_calendar_chronologically(
    events, today_formatted=None, group_by_currency=False
)
print(chronological_calendar)

# Format events grouped by currency
currency_grouped_calendar = await calendar_service.format_calendar_chronologically(
    events, today_formatted=None, group_by_currency=True
)
print(currency_grouped_calendar)
```

### Direct Usage of Formatter Functions

You can also use the formatter functions directly:

```python
from trading_bot.services.calendar_service.chronological_formatter import (
    format_calendar_events_chronologically,
    format_calendar_events_by_currency
)

# Format events chronologically
chronological_calendar = format_calendar_events_chronologically(events, today_formatted=None)
print(chronological_calendar)

# Format events grouped by currency
currency_grouped_calendar = format_calendar_events_by_currency(events, today_formatted=None)
print(currency_grouped_calendar)
```

## Testing

A test script is provided to demonstrate the chronological formatter with the existing TradingViewCalendarService:

```bash
python test_chronological_calendar.py
```

## Output Examples

### Chronological Order

```
📅 Economic Calendar for Monday, 01 January 2024

Impact: 🔴 High   🟠 Medium   🟢 Low

00:30 - 🇦🇺 AUD - 🟢 Manufacturing PMI
01:45 - 🇨🇳 CNY - 🟠 Caixin Manufacturing PMI
07:00 - 🇬🇧 GBP - 🟢 Nationwide HPI m/m
08:30 - 🇺🇸 USD - 🔴 Non-Farm Employment Change
```

### Grouped by Currency

```
📅 Economic Calendar for Monday, 01 January 2024

Impact: 🔴 High   🟠 Medium   🟢 Low

🇺🇸 USD
  08:30 - 🔴 Non-Farm Employment Change
  10:00 - 🟠 ISM Manufacturing PMI
  14:00 - 🟢 FOMC Meeting Minutes

🇪🇺 EUR
  04:00 - 🟠 Manufacturing PMI
  05:00 - 🟢 CPI Flash Estimate y/y

🇬🇧 GBP
  07:00 - 🟢 Nationwide HPI m/m
```

## Implementation Details

The chronological formatter is implemented in the following files:

- `trading_bot/services/calendar_service/chronological_formatter.py` - Core formatting functions
- `trading_bot/services/calendar_service/tradingview_calendar.py` - Integration with TradingViewCalendarService
- `trading_bot/services/calendar_service/calendar.py` - Integration with EconomicCalendarService
- `test_chronological_calendar.py` - Test script

## Dependencies

The chronological formatter depends on the following modules:

- `datetime` - For date formatting
- `logging` - For logging
- `typing` - For type hints 