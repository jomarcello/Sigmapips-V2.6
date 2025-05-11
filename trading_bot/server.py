"""
FastAPI server entry point for the trading bot
"""

import os
import logging
import uvicorn
from trading_bot.app import app

# Configure logging
logger = logging.getLogger("trading_bot.server")

def run_server():
    """Run the FastAPI server with uvicorn"""
    # Get port from environment or use default
    port = int(os.environ.get("PORT", 8000))
    
    # Get host from environment or use default
    host = os.environ.get("HOST", "0.0.0.0")
    
    # Log startup information
    logger.info(f"Starting FastAPI server on {host}:{port}")
    logger.info(f"API documentation available at http://{host}:{port}/docs")
    
    # Run the server
    uvicorn.run(
        "trading_bot.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    run_server() 