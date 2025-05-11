"""
FastAPI web application for the trading bot
"""

import os
import sys
import json
import logging
import platform
import psutil
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import importlib.util

# Set up logger
logger = logging.getLogger("trading_bot.api")

# Create FastAPI app
app = FastAPI(
    title="Trading Bot API",
    description="API for the trading bot",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint returning basic information"""
    return {
        "message": "Trading Bot API is running",
        "version": os.environ.get("APP_VERSION", "1.0.0"),
        "environment": os.environ.get("RAILWAY_ENVIRONMENT", "development"),
        "documentation": "/docs"
    }

@app.get("/health")
async def health_check():
    """Enhanced health check endpoint with detailed diagnostics"""
    
    # Initialize response
    health_data = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": os.environ.get("APP_VERSION", "unknown"),
        "environment": os.environ.get("RAILWAY_ENVIRONMENT", "development"),
        "system": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "cpu_count": psutil.cpu_count(),
            "memory": {
                "total": psutil.virtual_memory().total / (1024 * 1024),  # MB
                "available": psutil.virtual_memory().available / (1024 * 1024),  # MB
                "percent_used": psutil.virtual_memory().percent
            },
            "disk": {
                "total": psutil.disk_usage('/').total / (1024 * 1024 * 1024),  # GB
                "free": psutil.disk_usage('/').free / (1024 * 1024 * 1024),  # GB
                "percent_used": psutil.disk_usage('/').percent
            }
        },
        "services": {
            "ai_services": {
                "enabled": os.environ.get("AI_SERVICES_ENABLED", "false").lower() == "true",
                "openai_key_available": bool(os.environ.get("OPENAI_API_KEY", "")),
                "tavily_key_available": bool(os.environ.get("TAVILY_API_KEY", "")),
                "scrapingant_key_available": bool(os.environ.get("SCRAPINGANT_API_KEY", "")),
            },
            "telegram": {
                "bot_token_available": bool(os.environ.get("TELEGRAM_BOT_TOKEN", "")),
                "proxy_configured": bool(os.environ.get("TELEGRAM_PROXY_URL", "")),
            },
            "calendar": {
                "use_calendar_fallback": os.environ.get("USE_CALENDAR_FALLBACK", "false").lower() == "true",
                "use_scrapingant": os.environ.get("USE_SCRAPINGANT", "false").lower() == "true",
            }
        },
        "logs": {
            "recent_errors": []
        }
    }
    
    # Check for recent errors in logs
    try:
        logger = logging.getLogger("trading_bot")
        error_handler = None
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                error_handler = handler
                break
                
        if error_handler and hasattr(error_handler, 'baseFilename'):
            log_file = error_handler.baseFilename
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    # Get last 10 lines containing ERROR
                    lines = f.readlines()
                    error_lines = [line for line in lines if "ERROR" in line][-10:]
                    health_data["logs"]["recent_errors"] = error_lines
    except Exception as e:
        health_data["logs"]["error_reading_logs"] = str(e)
    
    # Check for AI service modules
    try:
        def check_module(module_path):
            spec = importlib.util.find_spec(module_path)
            return spec is not None
            
        health_data["services"]["ai_services"].update({
            "tavily_service_available": check_module("trading_bot.services.ai_service.tavily_service"),
            "deepseek_service_available": check_module("trading_bot.services.ai_service.deepseek_service"),
            "tradingview_calendar_available": check_module("trading_bot.services.calendar_service.tradingview_calendar"),
        })
    except Exception as e:
        health_data["services"]["module_check_error"] = str(e)
    
    # Return health data
    return health_data

# Add a simple ping endpoint for quick testing
@app.get("/ping")
async def ping():
    """Simple ping endpoint for quick testing"""
    return {"ping": "pong", "timestamp": datetime.now().isoformat()} 