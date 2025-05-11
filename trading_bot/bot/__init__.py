import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from ..services.sentiment_service import MarketSentimentService
from ..states import MenuStates, SignalStates

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.set_state(MenuStates.select_instrument)
    await message.answer("Please select an instrument and market type for analysis.")

@router.callback_query(MenuStates.select_instrument)
async def select_instrument(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MenuStates.select_market)
    await callback.message.edit_text("Please select a market type.")

@router.callback_query(MenuStates.select_market)
async def select_market(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MenuStates.analysis_results)
    await callback.message.edit_text("Loading analysis results...")