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

# Validate OpenAI API key format and existence
def validate_openai_key(key):
    """Validate OpenAI API key format and existence"""
    if not key or len(key) < 20:
        return False
    # Check for sk- format (common API key format)
    pattern = r"^sk-[a-zA-Z0-9_-]+$"
    if re.match(pattern, key):
        return True
    return False

# Get OpenAI API key and sanitize it
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
        
# Initialize AI services enabled flag based on key validation
AI_SERVICES_ENABLED = False

# Validate the key and set AI_SERVICES_ENABLED accordingly
if OPENAI_API_KEY and validate_openai_key(OPENAI_API_KEY):
    logger.info(f"Loaded OPENAI_API_KEY: {OPENAI_API_KEY[:4]}...")
    print("OpenAI API key loaded successfully")
    AI_SERVICES_ENABLED = True
else:
    logger.warning("OpenAI API key is missing or invalid. AI services will be disabled.")
    print("⚠️ OpenAI API key not configured or invalid. AI services disabled.")
    AI_SERVICES_ENABLED = False

# Chart settings
DEFAULT_CHART_TIMEFRAME = "1h"
