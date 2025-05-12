# Bot Management

## Preventing Multiple Bot Instances

The error `telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running` occurs when multiple instances of the bot are trying to connect to the Telegram API simultaneously.

To solve this issue, we've created a script that checks for running bot instances and ensures only one instance is active at a time.

## Using the Bot Management Script

### Basic Usage

To start the bot with instance checking:

```bash
python check_bot_running.py
```

This will:
1. Check if any bot instance is already running
2. If no instance is found, start a new bot
3. If an instance is found, exit with a warning

### Force Killing Existing Instances

If you need to restart the bot or are sure you want to kill any existing instances:

```bash
python check_bot_running.py --force-kill
```

This will:
1. Check for existing bot instances
2. If found, terminate them
3. Start a new bot instance

### Additional Options

- `--debug`: Enable debug mode for the bot
- `--log-level [LEVEL]`: Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

Example with all options:

```bash
python check_bot_running.py --force-kill --debug --log-level DEBUG
```

## Automatic Bot Startup

For automatic startup on system boot, you can use this script in your startup configuration.

### For Linux (using systemd)

Create a service file `/etc/systemd/system/trading-bot.service`:

```
[Unit]
Description=Trading Bot Service
After=network.target

[Service]
User=your_username
WorkingDirectory=/path/to/bot
ExecStart=/usr/bin/python3 /path/to/bot/check_bot_running.py --force-kill
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable trading-bot.service
sudo systemctl start trading-bot.service
```

### For macOS (using launchd)

Create a plist file `~/Library/LaunchAgents/com.user.tradingbot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.tradingbot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/bot/check_bot_running.py</string>
        <string>--force-kill</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/path/to/bot</string>
    <key>StandardErrorPath</key>
    <string>/path/to/bot/logs/error.log</string>
    <key>StandardOutPath</key>
    <string>/path/to/bot/logs/output.log</string>
</dict>
</plist>
```

Load the service:

```bash
launchctl load ~/Library/LaunchAgents/com.user.tradingbot.plist
```

## Troubleshooting

If you're still experiencing issues with multiple bot instances:

1. Check for zombie processes:
   ```bash
   ps aux | grep python | grep -i trading_bot
   ```

2. Kill all related processes:
   ```bash
   pkill -f trading_bot
   ```

3. Restart the bot using the script:
   ```bash
   python check_bot_running.py --force-kill
   ``` 