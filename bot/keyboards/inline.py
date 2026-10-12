"""Inline keyboards for video generation wizards and quick actions."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Returns main menu keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 Сгенерировать видео", callback_data="menu:create_video"),
                InlineKeyboardButton(text="🎙️ Транскрипция", callback_data="menu:transcribe_info"),
            ],
            [
                InlineKeyboardButton(text="⚡ Каталог моделей", callback_data="menu:models"),
                InlineKeyboardButton(text="💳 Мой баланс", callback_data="menu:balance"),
            ],
            [
                InlineKeyboardButton(text="🌐 Личный кабинет NormaHub", url="https://normahub.cc"),
            ],
        ]
    )


def get_voice_actions_keyboard(task_cache_id: str) -> InlineKeyboardMarkup:
    """Buttons presented after voice/video note transcription."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎬 Сгенерировать видео (SeeDance 2.5)",
                    callback_data=f"voice_to_video:seedance:{task_cache_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚡ Сгенерировать видео (Grok Imagine)",
                    callback_data=f"voice_to_video:grok:{task_cache_id}",
                ),
            ],
        ]
    )


def get_model_selection_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting video generator model."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌟 ByteDance SeeDance 2.5 (1080p Cinematic)",
                    callback_data="set_model:seedance-2.5",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚡ xAI Grok Imagine Video 1.5",
                    callback_data="set_model:grok-imagine-video-1.5",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚡ SeeDance 2.0 Fast (Превью)",
                    callback_data="set_model:seedance-2.0-fast",
                ),
            ],
        ]
    )


def get_aspect_ratio_keyboard(model: str) -> InlineKeyboardMarkup:
    """Keyboard for picking video aspect ratio."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📺 16:9 (Широкий экран)", callback_data=f"ratio:{model}:16:9"),
                InlineKeyboardButton(text="📱 9:16 (Reels/Shorts)", callback_data=f"ratio:{model}:9:16"),
            ],
            [
                InlineKeyboardButton(text="🔲 1:1 (Квадрат)", callback_data=f"ratio:{model}:1:1"),
            ],
        ]
    )
