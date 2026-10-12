"""Shared pytest fixtures."""

import os
import tempfile

import pytest
import pytest_asyncio

from bot.config import BotConfig
from bot.services.task_queue import TaskQueue
from bot.services.video_service import VideoService
from bot.services.whisper_service import WhisperService


@pytest.fixture
def mock_config() -> BotConfig:
    """Fixture providing valid testing configuration."""
    return BotConfig(
        telegram_bot_token="123456789:TEST_MOCK_TOKEN_ABC",
        normahub_api_key="nr_hub_test_key_123456",
        normahub_base_url="https://api.normahub.cc/v1",
        db_path=":memory:",
        default_video_model="seedance-2.5",
        default_whisper_model="whisper-1",
        max_concurrent_tasks=3,
        poll_interval_seconds=1.0,
        max_poll_timeout_seconds=30,
        log_level="DEBUG",
    )


@pytest_asyncio.fixture
async def temp_task_queue():
    """Provides a fresh TaskQueue on an isolated temporary SQLite file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    queue = TaskQueue(db_path=db_path)
    await queue.init_db()
    yield queue

    # Cleanup temp file
    if os.path.exists(db_path):
        os.remove(db_path)
    wal_file = f"{db_path}-wal"
    if os.path.exists(wal_file):
        os.remove(wal_file)
    shm_file = f"{db_path}-shm"
    if os.path.exists(shm_file):
        os.remove(shm_file)


@pytest.fixture
def whisper_service(mock_config: BotConfig) -> WhisperService:
    """Provides WhisperService with test config."""
    return WhisperService(
        api_key=mock_config.normahub_api_key.get_secret_value(),
        base_url=mock_config.normahub_base_url,
        default_model=mock_config.default_whisper_model,
    )


@pytest.fixture
def video_service(mock_config: BotConfig) -> VideoService:
    """Provides VideoService with test config."""
    return VideoService(
        api_key=mock_config.normahub_api_key.get_secret_value(),
        base_url=mock_config.normahub_base_url,
        default_model=mock_config.default_video_model,
    )
