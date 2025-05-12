# Economic Calendar for Telegram

This script fetches economic calendar events from TradingView and can display them in the console or send them to a Telegram channel/group.

## Features

- Fetches real-time economic calendar data from TradingView
- Filters events for major currencies (US, EU, GB, JP, CN)
- Supports displaying events for today or future days
- Shows event time, country, impact level, name, previous value, and forecast
- Sorts events by impact level (high to low) and then by time
- Formats output for both console and Telegram
- Handles long messages by splitting them for Telegram

## Requirements

- Python 3.7+
- Required packages:
  - aiohttp
  - pytz
  - python-telegram-bot

## Installation

1. Install the required packages:

```bash
pip install aiohttp pytz python-telegram-bot
```

2. Set up environment variables for Telegram (optional):

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

## Usage

### Basic Usage

Display economic events for today:

```bash
python economic_calendar.py
```

Display economic events for tomorrow:

```bash
python economic_calendar.py --days=1
```

### Advanced Options

- `--days=N`: Show events N days ahead (0=today, 1=tomorrow, etc.)
- `--all-currencies`: Show events for all currencies (default: only major currencies)
- `--debug`: Show additional debug information
- `--telegram`: Send the output to Telegram
- `--bot-token`: Telegram bot token (if not set as environment variable)
- `--chat-id`: Telegram chat ID (if not set as environment variable)

### Examples

Send today's economic events to Telegram:

```bash
python economic_calendar.py --telegram
```

Send tomorrow's economic events to Telegram:

```bash
python economic_calendar.py --days=1 --telegram
```

Show all currencies for today:

```bash
python economic_calendar.py --all-currencies
```

## Setting up as a Scheduled Task

### Using Cron (Linux/macOS)

To send economic events to Telegram every day at 8:00 AM:

```bash
0 8 * * * cd /path/to/script && /usr/bin/python economic_calendar.py --telegram
```

### Using Task Scheduler (Windows)

1. Create a batch file (run_calendar.bat):

```batch
@echo off
cd /path/to/script
python economic_calendar.py --telegram
```

2. Set up a scheduled task to run this batch file daily.

## Customization

You can modify the `MAJOR_CURRENCIES` list in the script to include or exclude specific currencies:

```python
MAJOR_CURRENCIES = ["US", "EU", "GB", "JP", "CN"]
```

## Troubleshooting

- If you get an error about missing modules, make sure you've installed all required packages.
- For Telegram errors, check that your bot token and chat ID are correct.
- If no events are shown, check your internet connection and the TradingView API status. 