"""Tests for VideoService SeeDance and Grok video generation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.video_service import (
    InsufficientBalanceError,
    VideoService,
)


@pytest.mark.asyncio
async def test_create_video_task_success():
    """Tests creating video task via POST /videos."""
    service = VideoService(api_key="test_key")

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"id": "task_seedance_12345"})

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp)))

    service._session = mock_session
    service._owns_session = False

    task_id = await service.create_task(
        prompt="A soaring eagle over rocky mountains",
        model="seedance-2.5",
        duration=5,
        aspect_ratio="16:9",
    )

    assert task_id == "task_seedance_12345"


@pytest.mark.asyncio
async def test_create_video_task_insufficient_balance():
    """Tests HTTP 402 raises InsufficientBalanceError."""
    service = VideoService(api_key="test_key")

    mock_resp = AsyncMock()
    mock_resp.status = 402
    mock_resp.text = AsyncMock(return_value='{"error": "insufficient_funds"}')

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp)))

    service._session = mock_session
    service._owns_session = False

    with pytest.raises(InsufficientBalanceError, match="Недостаточно средств"):
        await service.create_task(prompt="test", model="seedance-2.5")


@pytest.mark.asyncio
async def test_get_task_status_processing():
    """Tests polling status while processing."""
    service = VideoService(api_key="test_key")

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "status": "processing",
        "progress": 45,
    })

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp)))

    service._session = mock_session
    service._owns_session = False

    status = await service.get_task_status("task_seedance_12345")
    assert status.status == "processing"
    assert status.progress == 45
    assert not status.is_finished


@pytest.mark.asyncio
async def test_get_task_status_completed():
    """Tests polling status when completed."""
    service = VideoService(api_key="test_key")

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "status": "completed",
        "progress": 100,
        "video_url": "https://api.normahub.cc/v1/videos/downloads/12345.mp4",
    })

    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp)))

    service._session = mock_session
    service._owns_session = False

    status = await service.get_task_status("task_seedance_12345")
    assert status.status == "completed"
    assert status.progress == 100
    assert status.is_successful
    assert status.video_url == "https://api.normahub.cc/v1/videos/downloads/12345.mp4"


def test_parse_video_flags_with_preset():
    """Verify --preset flag appends style suffix and cleans args."""
    from bot.handlers.video import _parse_video_flags
    from bot.keyboards.inline import CINEMATIC_PRESETS

    raw = "Neon car race --preset cyberpunk --ratio 9:16 --duration 10"
    prompt, ratio, duration = _parse_video_flags(raw)

    assert ratio == "9:16"
    assert duration == 10
    assert "Neon car race" in prompt
    assert CINEMATIC_PRESETS["cyberpunk"]["suffix"] in prompt
    assert "--preset" not in prompt


def test_presets_keyboard_generation():
    """Verify preset keyboards structure and content."""
    from bot.keyboards.inline import (
        CINEMATIC_PRESETS,
        get_preset_detail_keyboard,
        get_presets_keyboard,
    )

    kb = get_presets_keyboard()
    assert len(kb.inline_keyboard) == len(CINEMATIC_PRESETS) + 1  # presets + back

    detail_kb = get_preset_detail_keyboard("cyberpunk")
    assert len(detail_kb.inline_keyboard) == 2
    assert "preset:run_sample:cyberpunk" in detail_kb.inline_keyboard[0][0].callback_data

