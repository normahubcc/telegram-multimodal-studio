"""Video generation handlers (/video, /seedance, /grok) with interactive progress bars."""

import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.config import BotConfig
from bot.services.task_queue import TaskQueue
from bot.utils.formatting import truncate_text
from bot.utils.progress import make_progress_bar

logger = logging.getLogger(__name__)
router = Router(name="video_router")


def _parse_video_flags(raw_text: str) -> tuple[str, str, int]:
    """Extracts --ratio and --duration flags from prompt string.

    Returns:
        (clean_prompt, aspect_ratio, duration)
    """
    aspect_ratio = "16:9"
    duration = 5

    # Extract --ratio 16:9 | 9:16 | 1:1
    ratio_match = re.search(r"--ratio\s+(16:9|9:16|1:1)", raw_text, re.IGNORECASE)
    if ratio_match:
        aspect_ratio = ratio_match.group(1)
        raw_text = re.sub(r"--ratio\s+(16:9|9:16|1:1)", "", raw_text, flags=re.IGNORECASE)

    # Extract --duration 5 | 10
    duration_match = re.search(r"--duration\s+(\d+)", raw_text, re.IGNORECASE)
    if duration_match:
        val = int(duration_match.group(1))
        if val in (5, 10):
            duration = val
        raw_text = re.sub(r"--duration\s+(\d+)", "", raw_text, flags=re.IGNORECASE)

    clean_prompt = " ".join(raw_text.split()).strip()
    return clean_prompt, aspect_ratio, duration


@router.message(Command("video"))
async def handle_video_command(
    message: Message,
    command: CommandObject,
    bot: Bot,
    config: BotConfig,
    task_queue: TaskQueue,
) -> None:
    """Default video command using configured default model (seedance-2.5)."""
    raw_args = command.args or ""
    await _start_video_generation(
        message=message,
        raw_args=raw_args,
        model=config.default_video_model,
        bot=bot,
        task_queue=task_queue,
    )


@router.message(Command("seedance"))
async def handle_seedance_command(
    message: Message,
    command: CommandObject,
    bot: Bot,
    task_queue: TaskQueue,
) -> None:
    """Forces ByteDance SeeDance 2.5 model."""
    raw_args = command.args or ""
    await _start_video_generation(
        message=message,
        raw_args=raw_args,
        model="seedance-2.5",
        bot=bot,
        task_queue=task_queue,
    )


@router.message(Command("grok"))
async def handle_grok_command(
    message: Message,
    command: CommandObject,
    bot: Bot,
    task_queue: TaskQueue,
) -> None:
    """Forces xAI Grok Imagine Video 1.5 model."""
    raw_args = command.args or ""
    await _start_video_generation(
        message=message,
        raw_args=raw_args,
        model="grok-imagine-video-1.5",
        bot=bot,
        task_queue=task_queue,
    )


@router.message(F.photo & F.caption.startswith("/video"))
async def handle_photo_with_video_caption(
    message: Message,
    bot: Bot,
    config: BotConfig,
    task_queue: TaskQueue,
) -> None:
    """Handles Image-to-Video generation when user attaches a photo with /video in caption."""
    caption = message.caption or ""
    raw_args = caption[len("/video") :].strip()
    await _start_video_generation(
        message=message,
        raw_args=raw_args,
        model=config.default_video_model,
        bot=bot,
        task_queue=task_queue,
        is_photo_message=True,
    )


async def _start_video_generation(
    message: Message,
    raw_args: str,
    model: str,
    bot: Bot,
    task_queue: TaskQueue,
    is_photo_message: bool = False,
) -> None:
    """Validates input prompt, extracts optional image, and enqueues task into SQLite WAL."""
    clean_prompt, aspect_ratio, duration = _parse_video_flags(raw_args)

    # Check if this is a reply to an existing photo
    image_url: str | None = None
    photo_obj = None

    if is_photo_message and message.photo:
        photo_obj = message.photo[-1]
    elif message.reply_to_message and message.reply_to_message.photo:
        photo_obj = message.reply_to_message.photo[-1]

    if photo_obj:
        try:
            file_info = await bot.get_file(photo_obj.file_id)
            if file_info.file_path:
                token = bot.token
                image_url = f"https://api.telegram.org/file/bot{token}/{file_info.file_path}"
                logger.info("Found input image for I2V: %s", file_info.file_path)
        except Exception as e:
            logger.warning("Could not obtain photo URL for I2V: %s", e)

    if not clean_prompt:
        model_name = "ByteDance SeeDance 2.5" if "seedance" in model else "Grok Imagine Video"
        example_cmd = "/video" if "seedance" in model else "/grok"
        await message.reply(
            f"🎬 **Генерация видео ({model_name})**\n\n"
            "Пожалуйста, добавьте текстовый промпт после команды.\n\n"
            "**Примеры использования:**\n"
            f"• `{example_cmd} Парящий остров над облаками, водопад, золотой закат, 4k cinematic`\n"
            f"• `{example_cmd} Бегущий киберпанк-гепард по ночной неоновой трассе --ratio 9:16`\n"
            f"• `{example_cmd} Акварельная анимация цветения сакуры под весенним дождем --duration 10`\n\n"
            "💡 **Поддерживаемые флаги:**\n"
            "• `--ratio 16:9` (по умолчанию), `--ratio 9:16`, `--ratio 1:1`\n"
            "• `--duration 5` (по умолчанию), `--duration 10`"
        )
        return

    model_display = "ByteDance SeeDance 2.5" if "seedance" in model else "Grok Imagine Video"
    progress_bar = make_progress_bar(0, length=10)

    # Send initial progress message
    status_msg = await message.reply(
        f"🎬 **{model_display}**\n\n"
        f"{progress_bar} **0%**\n"
        "⏳ *Инициализация задачи и бронирование GPU в NormaHub...*\n\n"
        f"📐 Формат: `{aspect_ratio}` | ⏱️ Длительность: `{duration}с`\n"
        f"📝 *Промпт:* _{truncate_text(clean_prompt, 180)}_"
    )

    # Enqueue task into SQLite WAL storage
    task_record = await task_queue.enqueue(
        chat_id=message.chat.id,
        user_id=message.from_user.id if message.from_user else 0,
        message_id=status_msg.message_id,
        prompt=clean_prompt,
        model=model,
        aspect_ratio=aspect_ratio,
        duration=duration,
        image_url=image_url,
    )

    logger.info(
        "Enqueued video task %s for user %d (model: %s, prompt: %.40s...)",
        task_record.task_id,
        task_record.user_id,
        model,
        clean_prompt,
    )
