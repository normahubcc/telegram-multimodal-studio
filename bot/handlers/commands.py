"""Command handlers: /start, /help, /models, /balance."""

import logging

import aiohttp
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import BotConfig
from bot.keyboards.inline import get_start_keyboard

logger = logging.getLogger(__name__)
router = Router(name="commands_router")


@router.message(Command("start"))
async def handle_start(message: Message) -> None:
    """Sends welcome message with studio introduction and action keyboard."""
    first_name = message.from_user.first_name if message.from_user else "друг"
    text = (
        f"👋 **Привет, {first_name}!**\n\n"
        "Добро пожаловать в **Telegram Multimodal Studio** — production-бота для работы "
        "с современными генеративными мультимодальными нейросетями через шлюз [NormaHub](https://normahub.cc).\n\n"
        "🌟 **Возможности студии:**\n"
        "• 🎙️ **Транскрипция голосовых и кружочков** — мгновенная расшифровка речи через Whisper-1.\n"
        "• 🎬 **Генерация видео SeeDance 2.5** — кинематографичные 1080p ролики от ByteDance.\n"
        "• ⚡ **Генерация видео Grok Imagine** — стилизованная динамическая анимация от xAI.\n"
        "• 🖼️ **Image-to-Video** — оживление фотографий и артов по текстовому описанию.\n\n"
        "💡 **Как начать?**\n"
        "1. Просто отправьте **голосовое** или **видео-кружочек** для расшифровки.\n"
        "2. Напишите `/video Футуристический неоновый город` для создания видео.\n"
        "3. Или воспользуйтесь кнопками меню ниже:"
    )
    await message.answer(text, reply_markup=get_start_keyboard())


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    """Displays detailed studio usage manual and command guide."""
    text = (
        "📖 **Руководство пользователя Multimodal Studio**\n\n"
        "**1. Расшифровка аудио и видео-кружочков:**\n"
        "• Отправьте боту любое голосовое сообщение (`.ogg`/`.oga`).\n"
        "• Отправьте видео-кружочек Telegram (`.mp4`).\n"
        "• Бот автоматически скачает файл и расшифрует речь через Whisper-1.\n"
        "• Из распознанного текста можно в 1 клик сгенерировать видеоролик!\n\n"
        "**2. Генерация видео (Text-to-Video):**\n"
        "• `/video <описание>` — создание видео по промпту моделью по умолчанию (`seedance-2.5`).\n"
        "• `/seedance <описание>` — принудительно использовать ByteDance SeeDance 2.5.\n"
        "• `/grok <описание>` — принудительно использовать xAI Grok Imagine Video 1.5.\n\n"
        "**3. Оживление картинок (Image-to-Video):**\n"
        "• Прикрепите фото и напишите в подписи `/video <что должно происходить>`.\n"
        "• Либо ответьте командой `/video <промпт>` на любое ранее отправленное фото.\n\n"
        "**4. Параметры соотношения сторон:**\n"
        "• Добавьте `--ratio 16:9` (горизонтальное), `--ratio 9:16` (вертикальное), или `--ratio 1:1` (квадрат).\n"
        "• Пример: `/video Неоновый кот летит в космосе --ratio 9:16`\n\n"
        "**5. Служебные команды:**\n"
        "• `/models` — каталог доступных нейросетей и их параметры.\n"
        "• `/balance` — проверка баланса и лимитов API NormaHub.\n"
        "• `/help` — это руководство."
    )
    await message.answer(text)


@router.message(Command("models"))
async def handle_models(message: Message) -> None:
    """Displays information about available AI models in the studio."""
    text = (
        "🤖 **Каталог нейросетей Multimodal Studio**\n\n"
        "**1. ByteDance SeeDance 2.5 (`seedance-2.5`)**\n"
        "• Флагманская модель генерации видео от ByteDance.\n"
        "• Разрешение: Full HD 1080p, кинематографическая физика света и динамики.\n"
        "• Поддерживает форматы 16:9, 9:16, 1:1.\n"
        "• Режимы: Text-to-Video (T2V) и Image-to-Video (I2V).\n\n"
        "**2. ByteDance SeeDance 2.0 Fast (`seedance-2.0-fast`)**\n"
        "• Облегченная версия для быстрого драфта и раскадровки.\n"
        "• Быстрый рендер (до 45 секунд).\n\n"
        "**3. xAI Grok Imagine Video 1.5 (`grok-imagine-video-1.5`)**\n"
        "• Модель генерации видео от команды xAI.\n"
        "• Отличается глубокой стилизацией, сюрреалистичными сценами и смелой динамикой.\n\n"
        "**4. OpenAI Whisper-1 (`whisper-1`)**\n"
        "• Мультиязычная модель распознавания речи.\n"
        "• Точно распознает русский язык, сленг, технические термины и шумные записи.\n"
        "• Поддерживает прямую подачу аудио из Telegram кружочков и голосовых.\n\n"
        "🌐 Полный каталог нейросетей доступен на [normahub.cc/models](https://normahub.cc/models)"
    )
    await message.answer(text)


@router.message(Command("balance"))
async def handle_balance(message: Message, config: BotConfig) -> None:
    """Checks NormaHub API status and provides billing information."""
    api_key_masked = "nr_hub_..." + config.normahub_api_key.get_secret_value()[-4:]
    base_url = config.normahub_base_url

    # Check connectivity and key validity via NormaHub /models or /dashboard/billing
    status_text = "🟢 Подключение активно"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {config.normahub_api_key.get_secret_value()}"},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    status_text = "🟢 Ключ активен, шлюз NormaHub доступен"
                elif resp.status == 401:
                    status_text = "🔴 Ошибка авторизации (неверный API ключ)"
                elif resp.status == 402:
                    status_text = "🟡 Баланс исчерпан (требуется пополнение)"
                else:
                    status_text = f"🟡 HTTP {resp.status}"
    except Exception as e:
        logger.warning("Could not ping NormaHub: %s", e)
        status_text = "⚪ Не удалось связаться со шлюзом"

    text = (
        "💳 **Статус подключения и баланс NormaHub**\n\n"
        f"• **Шлюз:** `{base_url}`\n"
        f"• **API-ключ:** `{api_key_masked}`\n"
        f"• **Состояние:** {status_text}\n\n"
        "🇷🇺 **Оплата и тарифы в РФ:**\n"
        "• Оплата в рублях без зарубежных карт и крипты.\n"
        "• Поддержка СБП, карт МИР, безналичный расчет для юрлиц (с НДС 20% и ЭДО Диадок).\n\n"
        "👉 [Пополнить баланс и посмотреть статистику в личном кабинете](https://normahub.cc/dashboard)"
    )
    await message.answer(text)


# ==============================================================================
# Callback Query Handlers for Menu Buttons
# ==============================================================================


@router.callback_query(F.data == "menu:create_video")
async def cb_create_video(callback: CallbackQuery) -> None:
    """Explains video prompt format."""
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "🎬 **Как создать видео:**\n\n"
            "Напишите команду с описанием желаемой сцены, например:\n"
            "`/video Неоновый киберпанк-самурай идет по дождливому Токио, 4k cinematic`\n\n"
            "Либо отправьте боту фото с подписью `/video Оживи это изображение`."
        )


@router.callback_query(F.data == "menu:transcribe_info")
async def cb_transcribe_info(callback: CallbackQuery) -> None:
    """Explains transcription feature."""
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "🎙️ **Транскрипция речи:**\n\n"
            "Просто запишите и отправьте в этот диалог **голосовое сообщение** или **видео-кружочек**.\n\n"
            "Бот мгновенно переведет речь в текст с помощью Whisper-1 и предложит создать видео на основе сказанного!"
        )


@router.callback_query(F.data == "menu:models")
async def cb_models(callback: CallbackQuery) -> None:
    """Shows models info."""
    await callback.answer()
    if callback.message:
        await handle_models(callback.message)


@router.callback_query(F.data == "menu:balance")
async def cb_balance(callback: CallbackQuery, config: BotConfig) -> None:
    """Shows balance info."""
    await callback.answer()
    if callback.message:
        await handle_balance(callback.message, config)
