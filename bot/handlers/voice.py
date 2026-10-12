"""Handlers for voice messages and video notes (кружочки) via Whisper-1."""

import logging
import uuid

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.types import CallbackQuery, Message

from bot.keyboards.inline import get_voice_actions_keyboard
from bot.services.task_queue import TaskQueue
from bot.services.whisper_service import (
    InsufficientBalanceError,
    WhisperDownloadError,
    WhisperError,
    WhisperService,
)
from bot.utils.formatting import format_duration

logger = logging.getLogger(__name__)
router = Router(name="voice_router")

# Temporary in-memory cache for recent voice transcriptions (id -> text prompt)
_transcription_cache: dict[str, str] = {}


@router.message(F.voice)
async def handle_voice_message(
    message: Message,
    bot: Bot,
    whisper_service: WhisperService,
) -> None:
    """Handles Telegram voice notes (.oga/.ogg)."""
    if not message.voice:
        return

    duration = message.voice.duration
    status_msg = await message.answer(
        f"🎧 **Слушаю голосовое сообщение ({format_duration(duration)})...**\n"
        "⏳ Скачиваю аудио и отправляю в Whisper-1..."
    )
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VOICE)

    try:
        # Download bytes from Telegram
        audio_bytes, filename = await whisper_service.download_telegram_media(
            bot=bot,
            media=message.voice,
        )

        # Transcribe through NormaHub Whisper API
        result = await whisper_service.transcribe(
            audio_bytes=audio_bytes,
            filename=filename,
        )

        await _respond_with_transcription(
            message=message,
            status_msg=status_msg,
            text=result.text,
            media_type_label="🎙️ Голосовое сообщение",
            duration=duration,
            language=result.language,
        )

    except InsufficientBalanceError as e:
        logger.error("Insufficient balance during voice transcription: %s", e)
        await status_msg.edit_text(
            "💳 **Недостаточно средств на балансе NormaHub.**\n"
            "Пополните счет в рублях через СБП/МИР на [normahub.cc](https://normahub.cc)."
        )
    except WhisperDownloadError as e:
        logger.warning("Telegram media download failed: %s", e)
        await status_msg.edit_text("❌ Не удалось загрузить аудио из Telegram. Попробуйте еще раз.")
    except WhisperError as e:
        logger.error("Whisper error: %s", e)
        await status_msg.edit_text(f"❌ **Ошибка распознавания речи:** {e.message}")
    except Exception as e:
        logger.exception("Unexpected error in voice processing: %s", e)
        await status_msg.edit_text(f"❌ **Непредвиденная ошибка:** {e}")


@router.message(F.video_note)
async def handle_video_note_message(
    message: Message,
    bot: Bot,
    whisper_service: WhisperService,
) -> None:
    """Handles Telegram round video circles (кружочки) (.mp4)."""
    if not message.video_note:
        return

    duration = message.video_note.duration
    status_msg = await message.answer(
        f"📹 **Обрабатываю видео-кружочек ({format_duration(duration)})...**\n"
        "⏳ Извлекаю аудиопоток и отправляю в Whisper-1..."
    )
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VOICE)

    try:
        # Download video note bytes from Telegram
        video_bytes, filename = await whisper_service.download_telegram_media(
            bot=bot,
            media=message.video_note,
        )

        # Transcribe through NormaHub Whisper API
        result = await whisper_service.transcribe(
            audio_bytes=video_bytes,
            filename=filename,
        )

        await _respond_with_transcription(
            message=message,
            status_msg=status_msg,
            text=result.text,
            media_type_label="📹 Видео-кружочек",
            duration=duration,
            language=result.language,
        )

    except InsufficientBalanceError as e:
        logger.error("Insufficient balance during video note transcription: %s", e)
        await status_msg.edit_text(
            "💳 **Недостаточно средств на балансе NormaHub.**\n"
            "Пополните счет в рублях через СБП/МИР на [normahub.cc](https://normahub.cc)."
        )
    except WhisperDownloadError as e:
        logger.warning("Telegram video note download failed: %s", e)
        await status_msg.edit_text("❌ Не удалось загрузить кружочек из Telegram. Попробуйте еще раз.")
    except WhisperError as e:
        logger.error("Whisper error: %s", e)
        await status_msg.edit_text(f"❌ **Ошибка распознавания кружочка:** {e.message}")
    except Exception as e:
        logger.exception("Unexpected error in video note processing: %s", e)
        await status_msg.edit_text(f"❌ **Непредвиденная ошибка:** {e}")


async def _respond_with_transcription(
    message: Message,
    status_msg: Message,
    text: str,
    media_type_label: str,
    duration: int | None,
    language: str | None,
) -> None:
    """Formats and sends transcription output with prompt-to-video action button."""
    clean_text = text.strip()
    if not clean_text:
        await status_msg.edit_text(
            f"🔇 **{media_type_label} распознано, но речь не обнаружена.**\n"
            "Возможно, запись была слишком тихой или содержала только фоновый шум."
        )
        return

    # Cache for 1-click video generation button
    cache_id = str(uuid.uuid4())[:8]
    _transcription_cache[cache_id] = clean_text

    # Keep cache from growing unbounded
    if len(_transcription_cache) > 200:
        oldest_key = next(iter(_transcription_cache))
        _transcription_cache.pop(oldest_key, None)

    dur_str = f" • ⏱️ {format_duration(duration)}" if duration else ""
    lang_str = f" • 🌐 {language.upper()}" if language else ""

    response_text = (
        f"📝 **{media_type_label}**{dur_str}{lang_str}\n\n"
        f"🗣️ **Распознанный текст:**\n"
        f"«{clean_text}»\n\n"
        f"💡 _Хотите сгенерировать видео по этому сценарию? Нажмите кнопку ниже:_"
    )

    await status_msg.edit_text(
        text=response_text,
        reply_markup=get_voice_actions_keyboard(cache_id),
    )


# ==============================================================================
# Callback Query: Voice Prompt -> Video Generation
# ==============================================================================


@router.callback_query(F.data.startswith("voice_to_video:"))
async def handle_voice_to_video_callback(
    callback: CallbackQuery,
    task_queue: TaskQueue,
) -> None:
    """Enqueues video generation using previously transcribed voice prompt."""
    await callback.answer()
    if not callback.data or not callback.message:
        return

    parts = callback.data.split(":")
    if len(parts) < 3:
        return

    model_type = parts[1]  # "seedance" or "grok"
    cache_id = parts[2]

    prompt = _transcription_cache.get(cache_id)
    if not prompt:
        await callback.message.reply(
            "⚠️ Срок действия этой подсказки истек. Пожалуйста, отправьте команду `/video <промпт>` вручную."
        )
        return

    model = "seedance-2.5" if model_type == "seedance" else "grok-imagine-video-1.5"
    model_name = "SeeDance 2.5" if model_type == "seedance" else "Grok Imagine Video"

    chat_id = callback.message.chat.id
    user_id = callback.from_user.id

    status_msg = await callback.message.reply(
        f"🎬 **Создание видео из голосового промпта ({model_name})...**\n"
        f"[░░░░░░░░░░] **0%**\n"
        "⏳ Задача поставлена в очередь GPU-кластера NormaHub..."
    )

    task_record = await task_queue.enqueue(
        chat_id=chat_id,
        user_id=user_id,
        message_id=status_msg.message_id,
        prompt=prompt,
        model=model,
        aspect_ratio="16:9",
        duration=5,
    )

    logger.info("Enqueued voice-to-video task %s for user %d", task_record.task_id, user_id)
