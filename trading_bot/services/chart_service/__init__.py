"""
Chart Service module
"""
import logging
from trading_bot.services.chart_service.chart import ChartService as _ChartService
from trading_bot.services.chart_service.binance_provider import BinanceProvider
from trading_bot.services.chart_service.tradingview_provider import TradingViewProvider

# Re-export under the service namespace
ChartService = _ChartService

# Initialize logging
logger = logging.getLogger(__name__)
logger.info("Chart Service module loaded")



