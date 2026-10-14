"""Inline keyboards for video generation wizards, presets and quick actions."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CINEMATIC_PRESETS: dict[str, dict[str, str]] = {
    "cyberpunk": {
        "title": "🌃 Cyberpunk Neon",
        "description": "Ночной мегаполис, влажный асфальт с отражением неоновых вывесок, объемный туман, кинематографичная оптика.",
        "sample": "Футуристический таксист едет по многоуровневому ночному мегаполису будущего",
        "suffix": ", cyberpunk aesthetic, neon lights reflections, wet asphalt, volumetric haze, atmospheric cinematic lighting, 8k masterpiece",
    },
    "anime_shinkai": {
        "title": "🌸 Anime Shinkai",
        "description": "Стиль Макото Синкая: живописные перистые облака, золотой рассветный свет, падающие лепестки сакуры.",
        "sample": "Школьница стоит на железнодорожном переезде на закате в Токио",
        "suffix": ", Makoto Shinkai anime aesthetic, majestic sky and clouds, golden hour sunset, floating flower petals, breathtaking anime masterpiece",
    },
    "photoreal": {
        "title": "📸 35mm Cinema Photoreal",
        "description": "Анаморфотная 35мм кинолинза: естественная глубина резкости, мягкое пленочное зерно, живая кинематография.",
        "sample": "Шеф-повар посыпает золотой солью дымящийся стейк на открытой кухне",
        "suffix": ", shot on 35mm anamorphic lens, shallow depth of field, subtle film grain, natural rim lighting, photorealistic textures",
    },
    "drone_fpv": {
        "title": "🦅 FPV Drone Action",
        "description": "Динамичный полет от первого лица: головокружительные виражи, высокая скорость и панорамный горизонт.",
        "sample": "Спортивный дрон пикирует сквозь ледяное ущелье заснеженных Альп",
        "suffix": ", extreme dynamic FPV drone flythrough, ultra-fluid camera acrobatic motion, sweeping landscape, 60fps cinematic",
    },
    "slow_mo": {
        "title": "⏳ Phantom 1000fps Slow-Mo",
        "description": "Сверхскоростная съемка: микрокапли воды, разлетающиеся искры, застывшее во времени движение.",
        "sample": "Капля кофе падает в фарфоровую чашку с образованием идеальной короны",
        "suffix": ", 1000fps ultra slow motion, Phantom Flex 4K camera, micro-droplets, frozen motion physics, high contrast studio lighting",
    },
}


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Returns main menu keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 Сгенерировать видео", callback_data="menu:create_video"),
                InlineKeyboardButton(text="🎨 Стили и пресеты", callback_data="menu:presets"),
            ],
            [
                InlineKeyboardButton(text="🎙️ Транскрипция", callback_data="menu:transcribe_info"),
                InlineKeyboardButton(text="⚡ Каталог моделей", callback_data="menu:models"),
            ],
            [
                InlineKeyboardButton(text="💳 Мой баланс", callback_data="menu:balance"),
                InlineKeyboardButton(text="🌐 NormaHub", url="https://normahub.cc"),
            ],
        ]
    )


def get_presets_keyboard() -> InlineKeyboardMarkup:
    """Returns keyboard with all available cinematic style presets."""
    buttons = []
    for key, data in CINEMATIC_PRESETS.items():
        buttons.append([InlineKeyboardButton(text=data["title"], callback_data=f"preset:view:{key}")])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_preset_detail_keyboard(preset_key: str) -> InlineKeyboardMarkup:
    """Returns action buttons for a specific chosen preset."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎬 Запустить тестовый пример",
                    callback_data=f"preset:run_sample:{preset_key}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 К списку пресетов",
                    callback_data="menu:presets",
                ),
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
