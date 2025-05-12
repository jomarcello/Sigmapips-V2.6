# Bot Instance Management for Deployment

This document explains how the bot instance management system works for different deployment scenarios.

## The Problem

When deploying the bot, especially on platforms like Railway, we face two main challenges:

1. **Multiple instances**: When a new deployment is triggered, the old instance might still be running, causing conflicts with the Telegram API.
2. **Telegram API conflicts**: The error `telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running` occurs when multiple bot instances try to connect simultaneously.

## Solution Overview

We've implemented a multi-layered approach to ensure only one bot instance is active at any time:

1. **Process-based management** (local development)
2. **Database-based management** (production/Railway)

## Local Development

For local development, use the `check_bot_running.py` script:

```bash
python check_bot_running.py
```

This script:
- Checks for existing Python processes running the trading bot
- Prevents starting a new instance if one is already running
- Can force-kill existing instances with `--force-kill`

## Railway Deployment

For Railway, we use a database-based approach with these components:

1. **Procfile**: Configures Railway to use our startup script
   ```
   web: python railway_startup.py
   ```

2. **railway_startup.py**: Handles Railway-specific startup
   - Deactivates old instances in the database
   - Registers the new instance
   - Starts the bot using the instance manager

3. **instance_manager.py**: Manages bot instances using the database
   - Registers the instance in the database
   - Maintains a heartbeat to indicate the instance is alive
   - Only starts the bot if this instance should be active

4. **Database tracking**: Uses a `bot_instances` table to track:
   - Instance IDs
   - Start times
   - Last heartbeat times
   - Active status

## How It Works in Production

When a new deployment is triggered on Railway:

1. Railway starts the new instance using `railway_startup.py`
2. The script deactivates all old instances in the database
3. It registers the new instance as active
4. The instance manager starts the bot
5. The heartbeat updater keeps the instance marked as active
6. If the old instance is still running, it will see it's no longer active and shut down

## Manual Management

If you need to manually manage instances:

### Check Active Instances

```sql
SELECT * FROM bot_instances WHERE is_active = TRUE;
```

### Deactivate All Instances

```sql
UPDATE bot_instances SET is_active = FALSE;
```

### Force a Specific Instance to be Active

```sql
UPDATE bot_instances SET is_active = FALSE;
UPDATE bot_instances SET is_active = TRUE WHERE instance_id = 'your-instance-id';
```

## Troubleshooting

If you're still experiencing issues with multiple bot instances:

1. Check the database for active instances:
   ```sql
   SELECT * FROM bot_instances WHERE is_active = TRUE;
   ```

2. Manually deactivate all instances:
   ```sql
   UPDATE bot_instances SET is_active = FALSE;
   ```

3. Restart the deployment on Railway

4. If using locally, kill all related processes:
   ```bash
   pkill -f trading_bot
   ``` 