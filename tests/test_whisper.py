"""Tests for WhisperService media downloading and transcription."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import File, VideoNote, Voice

from bot.services.whisper_service import (
    InsufficientBalanceError,
    WhisperAPIError,
    WhisperDownloadError,
    WhisperService,
)


@pytest.mark.asyncio
async def test_download_telegram_voice_success():
    """Verifies that Telegram voice (.oga) is properly downloaded."""
    service = WhisperService(api_key="mock_key")

    mock_bot = MagicMock()
    mock_file = File(file_id="voice_file_123", file_unique_id="uniq_123", file_path="voice/audio.oga")
    mock_bot.get_file = AsyncMock(return_value=mock_file)

    async def fake_download(file_path, destination):
        destination.write(b"mock_ogg_data")

    mock_bot.download_file = AsyncMock(side_effect=fake_download)

    voice = Voice(
        file_id="voice_file_123",
        file_unique_id="uniq_123",
        duration=12,
        mime_type="audio/ogg",
    )

    data, filename = await service.download_telegram_media(mock_bot, voice)
    assert data == b"mock_ogg_data"
    assert filename == "voice.oga"
    mock_bot.get_file.assert_awaited_once_with("voice_file_123")


@pytest.mark.asyncio
async def test_download_telegram_video_note_success():
    """Verifies that Telegram video note (.mp4 circle) is properly downloaded."""
    service = WhisperService(api_key="mock_key")

    mock_bot = MagicMock()
    mock_file = File(file_id="circle_file_456", file_unique_id="uniq_456", file_path="video_notes/note.mp4")
    mock_bot.get_file = AsyncMock(return_value=mock_file)

    async def fake_download(file_path, destination):
        destination.write(b"mock_mp4_video_data")

    mock_bot.download_file = AsyncMock(side_effect=fake_download)

    video_note = VideoNote(
        file_id="circle_file_456",
        file_unique_id="uniq_456",
        length=240,
        duration=5,
    )

    data, filename = await service.download_telegram_media(mock_bot, video_note)
    assert data == b"mock_mp4_video_data"
    assert filename == "video_note.mp4"


@pytest.mark.asyncio
async def test_download_telegram_empty_file_error():
    """Fails with WhisperDownloadError if Telegram provides empty bytes."""
    service = WhisperService(api_key="mock_key")

    mock_bot = MagicMock()
    mock_file = File(file_id="f1", file_unique_id="u1", file_path="voice/f1.oga")
    mock_bot.get_file = AsyncMock(return_value=mock_file)
    mock_bot.download_file = AsyncMock()  # doesn't write anything

    voice = Voice(file_id="f1", file_unique_id="u1", duration=2)

    with pytest.raises(WhisperDownloadError, match="пуст"):
        await service.download_telegram_media(mock_bot, voice)


@pytest.mark.asyncio
async def test_transcribe_success():
    """Verifies successful transcription call via NormaHub /v1/audio/transcriptions."""
    service = WhisperService(api_key="test_key", base_url="https://api.normahub.cc/v1")

    # Mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "text": "Привет, это тестовая голосовая заметка для студии.",
        "language": "ru",
        "duration": 4.5,
    })

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))

    service._session = mock_session
    service._owns_session = False

    result = await service.transcribe(
        audio_bytes=b"sample_bytes",
        filename="voice.oga",
    )

    assert result.text == "Привет, это тестовая голосовая заметка для студии."
    assert result.language == "ru"
    assert result.media_type == "voice"


@pytest.mark.asyncio
async def test_transcribe_insufficient_balance():
    """Verifies that HTTP 402 raises InsufficientBalanceError."""
    service = WhisperService(api_key="test_key")

    mock_response = AsyncMock()
    mock_response.status = 402
    mock_response.text = AsyncMock(return_value='{"error": {"code": "insufficient_quota"}}')

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))

    service._session = mock_session
    service._owns_session = False

    with pytest.raises(InsufficientBalanceError, match="Недостаточно средств"):
        await service.transcribe(audio_bytes=b"sample_bytes", filename="voice.oga")


@pytest.mark.asyncio
async def test_transcribe_api_error():
    """Verifies that HTTP 500 raises WhisperAPIError."""
    service = WhisperService(api_key="test_key")

    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.text = AsyncMock(return_value="Internal Server Error")

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))

    service._session = mock_session
    service._owns_session = False

    with pytest.raises(WhisperAPIError, match="HTTP 500"):
        await service.transcribe(audio_bytes=b"sample_bytes", filename="voice.oga")
