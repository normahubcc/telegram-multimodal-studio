"""Service for downloading Telegram voice & video notes and transcribing via Whisper."""

import io
import logging
from dataclasses import dataclass
from typing import Literal

import aiohttp
from aiogram import Bot
from aiogram.types import VideoNote, Voice

logger = logging.getLogger(__name__)


class WhisperError(Exception):
    """Base exception for Whisper transcription errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class WhisperDownloadError(WhisperError):
    """Failed to download media file from Telegram servers."""


class WhisperAPIError(WhisperError):
    """NormaHub Whisper API request failure."""


class InsufficientBalanceError(WhisperAPIError):
    """NormaHub account balance is insufficient."""


@dataclass(frozen=True)
class TranscriptionResult:
    """Result of audio/video note transcription."""

    text: str
    media_type: Literal["voice", "video_note"]
    duration: int | None = None
    language: str | None = None
    filename: str = ""


class WhisperService:
    """Handles audio/video download from Telegram and transcription through NormaHub."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.normahub.cc/v1",
        default_model: str = "whisper-1",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._session = session
        self._owns_session = session is None

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or lazily create aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "Telegram-Multimodal-Studio/1.0.0"}
            )
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close HTTP session if managed internally."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def download_telegram_media(
        self,
        bot: Bot,
        media: Voice | VideoNote,
    ) -> tuple[bytes, str]:
        """Downloads voice note (.oga/.ogg) or video note (.mp4) bytes from Telegram.

        Returns:
            Tuple of (file_bytes, filename)
        """
        try:
            file_info = await bot.get_file(media.file_id)
            if not file_info.file_path:
                raise WhisperDownloadError("Telegram не предоставил путь к медиа-файлу.")

            buffer = io.BytesIO()
            await bot.download_file(file_info.file_path, destination=buffer)
            file_bytes = buffer.getvalue()

            if not file_bytes:
                raise WhisperDownloadError("Загруженный медиа-файл пуст.")

            # Determine appropriate filename and extension
            if isinstance(media, Voice):
                filename = "voice.oga"
            elif isinstance(media, VideoNote):
                filename = "video_note.mp4"
            else:
                ext = file_info.file_path.split(".")[-1] if "." in file_info.file_path else "ogg"
                filename = f"media.{ext}"

            logger.info(
                "Downloaded Telegram media: %s, size=%d bytes, duration=%ss",
                filename,
                len(file_bytes),
                getattr(media, "duration", None),
            )
            return file_bytes, filename

        except Exception as e:
            if isinstance(e, WhisperDownloadError):
                raise
            logger.exception("Error downloading Telegram media: %s", e)
            raise WhisperDownloadError(f"Ошибка скачивания медиа из Telegram: {e}") from e

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.oga",
        model: str | None = None,
        language: str | None = None,
        prompt: str | None = None,
    ) -> TranscriptionResult:
        """Sends audio/video bytes to NormaHub /v1/audio/transcriptions endpoint.

        NormaHub Whisper API natively accepts .oga, .ogg, .mp4, .m4a, .mp3, .wav.
        """
        model = model or self.default_model
        endpoint_url = f"{self.base_url}/audio/transcriptions"
        session = await self.get_session()

        form = aiohttp.FormData()
        # Guess mime type based on extension
        mime_type = "audio/ogg"
        if filename.endswith(".mp4"):
            mime_type = "video/mp4"
        elif filename.endswith(".mp3"):
            mime_type = "audio/mpeg"
        elif filename.endswith(".wav"):
            mime_type = "audio/wav"

        form.add_field("file", audio_bytes, filename=filename, content_type=mime_type)
        form.add_field("model", model)
        form.add_field("response_format", "json")

        if language:
            form.add_field("language", language)
        if prompt:
            form.add_field("prompt", prompt)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with session.post(
                endpoint_url,
                data=form,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as response:
                if response.status == 402:
                    error_text = await response.text()
                    logger.error("NormaHub 402 Insufficient Balance: %s", error_text)
                    raise InsufficientBalanceError(
                        "Недостаточно средств на балансе NormaHub. Пополните счет на https://normahub.cc",
                        status_code=402,
                    )

                if response.status != 200:
                    error_text = await response.text()
                    logger.error("NormaHub Whisper API error (%d): %s", response.status, error_text)
                    raise WhisperAPIError(
                        f"Ошибка Whisper API (HTTP {response.status}): {error_text[:200]}",
                        status_code=response.status,
                    )

                data = await response.json()
                text = (data.get("text") or "").strip()
                detected_lang = data.get("language")

                media_type: Literal["voice", "video_note"] = (
                    "video_note" if filename.endswith(".mp4") else "voice"
                )

                return TranscriptionResult(
                    text=text,
                    media_type=media_type,
                    language=detected_lang,
                    filename=filename,
                )

        except aiohttp.ClientError as e:
            logger.exception("Network error connecting to NormaHub Whisper: %s", e)
            raise WhisperAPIError(f"Сетевая ошибка обращения к NormaHub: {e}") from e


def create_whisper_service(
    api_key: str,
    base_url: str = "https://api.normahub.cc/v1",
    default_model: str = "whisper-1",
) -> WhisperService:
    """Factory function for WhisperService."""
    return WhisperService(api_key=api_key, base_url=base_url, default_model=default_model)
