from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import load_settings
from app.db.base import database, init_database
from app.db.bootstrap import create_tables
from app.handlers.admin.panel import build_router as build_admin_router
from app.handlers.payments.stars import build_router as build_payment_router
from app.handlers.user.chat import build_router as build_chat_router
from app.handlers.user.start import build_router as build_start_router
from app.app_logging import setup_logging
from app.services.dialog_service import DialogService


async def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    init_database(settings.db_path)
    create_tables()
    database.connect(reuse_if_open=True)

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dialog_service = DialogService(settings)
    dp.include_router(build_payment_router(settings))
    dp.include_router(build_admin_router(settings))
    dp.include_router(build_start_router(settings))
    dp.include_router(build_chat_router(settings, dialog_service))

    try:
        await dp.start_polling(bot)
    finally:
        database.close()


if __name__ == "__main__":
    asyncio.run(main())
