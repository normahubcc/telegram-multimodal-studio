"""Telegram Multimodal Studio bot entry point powered by aiogram 3.15+."""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import load_config
from bot.handlers import commands_router, video_router, voice_router
from bot.services.task_queue import QueueWorker, TaskQueue
from bot.services.video_service import VideoService
from bot.services.whisper_service import WhisperService

logger = logging.getLogger("telegram_multimodal_studio")


def setup_logging(log_level: str = "INFO") -> None:
    """Configures structured console logging."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # Suppress verbose HTTP engine logs
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


async def main() -> None:
    """Initializes dependencies, services, queue worker, and runs aiogram polling."""
    config = load_config()
    setup_logging(config.log_level)

    logger.info("Starting Telegram Multimodal Studio...")

    # 1. Initialize Bot & Dispatcher
    bot = Bot(
        token=config.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher()

    # 2. Initialize Services & SQLite WAL Task Queue
    task_queue = TaskQueue(db_path=config.db_path)
    await task_queue.init_db()

    whisper_service = WhisperService(
        api_key=config.normahub_api_key.get_secret_value(),
        base_url=config.normahub_base_url,
        default_model=config.default_whisper_model,
    )

    video_service = VideoService(
        api_key=config.normahub_api_key.get_secret_value(),
        base_url=config.normahub_base_url,
        default_model=config.default_video_model,
    )

    queue_worker = QueueWorker(
        bot=bot,
        queue=task_queue,
        video_service=video_service,
        max_concurrent=config.max_concurrent_tasks,
        poll_interval=config.poll_interval_seconds,
        max_poll_timeout=config.max_poll_timeout_seconds,
    )

    # 3. Inject dependencies into Dispatcher workflow
    dp["config"] = config
    dp["task_queue"] = task_queue
    dp["whisper_service"] = whisper_service
    dp["video_service"] = video_service

    # 4. Include Routers
    dp.include_router(commands_router)
    dp.include_router(video_router)
    dp.include_router(voice_router)

    # 5. Lifecycle Hooks
    async def on_startup() -> None:
        bot_info = await bot.get_me()
        logger.info(
            "Bot connected as @%s (id=%d). Starting background task queue worker...",
            bot_info.username,
            bot_info.id,
        )
        queue_worker.start()

    async def on_shutdown() -> None:
        logger.info("Shutting down Telegram Multimodal Studio...")
        await queue_worker.stop()
        await whisper_service.close()
        await video_service.close()
        await bot.session.close()
        logger.info("Graceful shutdown completed.")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # 6. Delete webhook if set and start long-polling
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Polling started. Waiting for updates...")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution terminated by user.")
