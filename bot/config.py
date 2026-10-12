"""Application configuration using Pydantic Settings."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseSettings):
    """Production configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Credentials
    telegram_bot_token: SecretStr = Field(
        ...,
        validation_alias="TELEGRAM_BOT_TOKEN",
        description="Telegram Bot API token obtained from @BotFather",
    )

    # NormaHub AI Gateway
    normahub_api_key: SecretStr = Field(
        ...,
        validation_alias="NORMAHUB_API_KEY",
        description="NormaHub API key (nr_hub_... from https://normahub.cc)",
    )
    normahub_base_url: str = Field(
        default="https://api.normahub.cc/v1",
        validation_alias="NORMAHUB_BASE_URL",
        description="NormaHub API base URL",
    )

    # SQLite WAL Persistent Queue Storage
    db_path: str = Field(
        default="data/tasks.db",
        validation_alias="DB_PATH",
        description="SQLite database path for task queue persistence",
    )

    # Default Models
    default_video_model: str = Field(
        default="seedance-2.5",
        validation_alias="DEFAULT_VIDEO_MODEL",
        description="Default AI video model: seedance-2.5, seedance-2.0, grok-imagine-video-1.5",
    )
    default_whisper_model: str = Field(
        default="whisper-1",
        validation_alias="DEFAULT_WHISPER_MODEL",
        description="Default Whisper model for audio/video transcription",
    )

    # Queue Worker Settings
    max_concurrent_tasks: int = Field(
        default=5,
        validation_alias="MAX_CONCURRENT_TASKS",
        description="Maximum concurrent polling tasks for video generation",
        ge=1,
        le=50,
    )
    poll_interval_seconds: float = Field(
        default=3.0,
        validation_alias="POLL_INTERVAL_SECONDS",
        description="Base polling interval in seconds for video status checks",
        ge=1.0,
        le=60.0,
    )
    max_poll_timeout_seconds: int = Field(
        default=600,
        validation_alias="MAX_POLL_TIMEOUT_SECONDS",
        description="Maximum wait timeout before timing out a generation task (seconds)",
        ge=60,
        le=1800,
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )


def load_config() -> BotConfig:
    """Instantiate and validate BotConfig."""
    return BotConfig()
