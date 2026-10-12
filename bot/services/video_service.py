"""Service for ByteDance SeeDance 2.5 and Grok Imagine Video generation via NormaHub."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

import aiohttp

logger = logging.getLogger(__name__)


class VideoServiceError(Exception):
    """Base exception for video generation errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class VideoGenerationFailedError(VideoServiceError):
    """Upstream model generation failed."""


class VideoTimeoutError(VideoServiceError):
    """Generation exceeded maximum polling wait time."""


class InsufficientBalanceError(VideoServiceError):
    """NormaHub balance is insufficient."""


@dataclass(frozen=True)
class VideoTaskStatus:
    """Status snapshot of an asynchronous video generation task."""

    task_id: str
    status: Literal["queued", "processing", "completed", "failed", "unknown"]
    progress: int  # 0 to 100
    video_url: str | None = None
    error: str | None = None
    raw_response: dict[str, Any] | None = None

    @property
    def is_finished(self) -> bool:
        return self.status in ("completed", "failed")

    @property
    def is_successful(self) -> bool:
        return self.status == "completed" and bool(self.video_url)


class VideoService:
    """Async client for creating and monitoring SeeDance 2.5 and Grok Imagine Video tasks."""

    SUPPORTED_MODELS = {
        "seedance-2.5": "ByteDance SeeDance 2.5 (1080p Cinematic, T2V/I2V)",
        "seedance-2.0": "ByteDance SeeDance 2.0 (HD)",
        "seedance-2.0-fast": "ByteDance SeeDance 2.0 Fast (Draft/Preview)",
        "grok-imagine-video-1.5": "xAI Grok Imagine Video 1.5 (Stylized)",
    }

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.normahub.cc/v1",
        default_model: str = "seedance-2.5",
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
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Telegram-Multimodal-Studio/1.0.0",
                }
            )
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close managed session."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def create_task(
        self,
        prompt: str,
        model: str | None = None,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        image_url: str | None = None,
    ) -> str:
        """Submits video generation task to NormaHub.

        Returns:
            task_id returned by upstream provider
        """
        model = model or self.default_model
        session = await self.get_session()

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt.strip(),
            "duration": duration,
            "aspect_ratio": aspect_ratio,
        }
        if image_url:
            payload["image_url"] = image_url

        primary_url = f"{self.base_url}/videos"
        fallback_url = f"{self.base_url}/videos/generations"

        # Try primary endpoint, then fallback if 404
        for url in (primary_url, fallback_url):
            try:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=45),
                ) as response:
                    if response.status == 404 and url == primary_url:
                        logger.warning("Primary endpoint %s returned 404, falling back to %s", url, fallback_url)
                        continue

                    if response.status == 402:
                        err_text = await response.text()
                        logger.error("NormaHub 402 Insufficient Balance: %s", err_text)
                        raise InsufficientBalanceError(
                            "Недостаточно средств на балансе NormaHub. Пополните счет на https://normahub.cc",
                            status_code=402,
                        )

                    if response.status not in (200, 201, 202):
                        err_text = await response.text()
                        logger.error("Video task creation failed (HTTP %d): %s", response.status, err_text)
                        raise VideoServiceError(
                            f"Ошибка создания задачи видео (HTTP {response.status}): {err_text[:200]}",
                            status_code=response.status,
                        )

                    data = await response.json()
                    task_id = str(data.get("id") or data.get("task_id") or "")
                    if not task_id:
                        raise VideoServiceError(f"Сервер не вернул task_id: {data}")

                    logger.info("Created video task %s with model %s", task_id, model)
                    return task_id

            except aiohttp.ClientError as e:
                logger.exception("Network error calling %s: %s", url, e)
                raise VideoServiceError(f"Сетевая ошибка обращения к NormaHub Video API: {e}") from e

        raise VideoServiceError("Не удалось связаться с сервером генерации видео.")

    async def get_task_status(self, task_id: str) -> VideoTaskStatus:
        """Polls current status of a specific video generation task."""
        session = await self.get_session()
        primary_url = f"{self.base_url}/videos/status/{task_id}"
        fallback_url = f"{self.base_url}/videos/tasks/{task_id}"

        for url in (primary_url, fallback_url):
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 404 and url == primary_url:
                        continue

                    if response.status != 200:
                        err_text = await response.text()
                        raise VideoServiceError(
                            f"Ошибка запроса статуса (HTTP {response.status}): {err_text[:200]}",
                            status_code=response.status,
                        )

                    data = await response.json()

                    raw_status = (data.get("status") or "").lower()
                    if raw_status in ("completed", "succeeded", "success"):
                        normalized_status = "completed"
                    elif raw_status in ("failed", "error", "canceled"):
                        normalized_status = "failed"
                    elif raw_status in ("processing", "running", "in_progress"):
                        normalized_status = "processing"
                    elif raw_status in ("queued", "pending", "submitted"):
                        normalized_status = "queued"
                    else:
                        normalized_status = "processing" if data.get("progress") else "unknown"

                    progress = int(data.get("progress") or 0)
                    if normalized_status == "completed":
                        progress = 100

                    video_url = data.get("video_url") or data.get("url")
                    error = data.get("error") or data.get("error_message")

                    return VideoTaskStatus(
                        task_id=task_id,
                        status=normalized_status,
                        progress=progress,
                        video_url=video_url,
                        error=error,
                        raw_response=data,
                    )

            except aiohttp.ClientError as e:
                logger.warning("Network issue polling status %s: %s", task_id, e)
                raise VideoServiceError(f"Сетевая ошибка проверки статуса: {e}") from e

        raise VideoServiceError(f"Не удалось проверить статус задачи {task_id}")

    async def poll_until_complete(
        self,
        task_id: str,
        initial_delay: float = 3.0,
        max_interval: float = 8.0,
        backoff_factor: float = 1.2,
        timeout: float = 600.0,
    ) -> VideoTaskStatus:
        """Polls task status with exponential backoff until completed or failed."""
        elapsed = 0.0
        current_delay = initial_delay

        while elapsed < timeout:
            status = await self.get_task_status(task_id)
            if status.is_finished:
                if status.status == "failed":
                    raise VideoGenerationFailedError(
                        status.error or "Генерация видео завершилась ошибкой нейросети"
                    )
                return status

            await asyncio.sleep(current_delay)
            elapsed += current_delay
            current_delay = min(current_delay * backoff_factor, max_interval)

        raise VideoTimeoutError(f"Превышено время ожидания генерации ({int(timeout)} сек).")


def create_video_service(
    api_key: str,
    base_url: str = "https://api.normahub.cc/v1",
    default_model: str = "seedance-2.5",
) -> VideoService:
    """Factory function for VideoService."""
    return VideoService(api_key=api_key, base_url=base_url, default_model=default_model)
