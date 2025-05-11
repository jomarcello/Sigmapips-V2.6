"""
Configuration settings for the Trading Bot
"""

import os
import logging
from dotenv import load_dotenv
import re
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Browser settings
DISABLE_BROWSER = os.environ.get("DISABLE_BROWSER", "false").lower() == "true"

# Cache settings
CACHE_ENABLED = True
CACHE_TTL = 300  # 5 minutes in seconds

# API settings
API_TIMEOUT = 30  # seconds
API_RETRY_COUNT = 3

# OpenAI API Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AI_SERVICES_ENABLED = True

# Validate OpenAI API key format and existence
def validate_openai_key(key):
    """Validate OpenAI API key format and existence"""
    if not key or len(key) < 20:
        return False
    # Check for sk-proj- format (newer API keys)
    pattern = r"^sk-[a-zA-Z0-9_-]+$"
    if re.match(pattern, key):
        return True
    return False
        
if OPENAI_API_KEY and validate_openai_key(OPENAI_API_KEY):
    logger.info(f"Loaded OPENAI_API_KEY: {OPENAI_API_KEY[:4]}...")
    print("OpenAI API key loaded successfully")
else:
    logger.warning("OpenAI API key is missing or invalid. AI services will be disabled.")
    AI_SERVICES_ENABLED = False
    print("⚠️ OpenAI API key not configured. AI services disabled.")

# Chart settings
DEFAULT_CHART_TIMEFRAME = "1h"
