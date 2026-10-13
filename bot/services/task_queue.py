"""SQLite WAL task queue for background video generation and crash recovery."""

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Literal

import aiosqlite
from aiogram import Bot
from aiogram.enums import ChatAction

from bot.services.video_service import (
    InsufficientBalanceError,
    VideoService,
)
from bot.utils.formatting import format_duration, truncate_text
from bot.utils.progress import get_stage_description, make_progress_bar

logger = logging.getLogger(__name__)

TaskStatus = Literal["pending", "submitting", "processing", "completed", "failed", "cancelled"]


@dataclass
class TaskRecord:
    """Represents a video generation task persisted in SQLite."""

    id: int
    task_id: str
    chat_id: int
    user_id: int
    message_id: int
    prompt: str
    model: str
    aspect_ratio: str
    duration: int
    image_url: str | None
    status: TaskStatus
    progress: int
    upstream_task_id: str | None
    video_url: str | None
    error_message: str | None
    created_at: float
    updated_at: float
    attempts: int


class TaskQueue:
    """Async SQLite-backed task queue with Write-Ahead Logging (WAL)."""

    def __init__(self, db_path: str = "data/tasks.db") -> None:
        self.db_path = db_path
        # Ensure parent directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    async def init_db(self) -> None:
        """Initializes database tables, indices, and WAL mode."""
        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode for high concurrency without locks
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA synchronous=NORMAL;")
            await db.execute("PRAGMA busy_timeout=5000;")

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS video_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    prompt TEXT NOT NULL,
                    model TEXT NOT NULL,
                    aspect_ratio TEXT NOT NULL,
                    duration INTEGER NOT NULL,
                    image_url TEXT,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    upstream_task_id TEXT,
                    video_url TEXT,
                    error_message TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON video_tasks(status);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_created ON video_tasks(created_at);"
            )
            await db.commit()
            logger.info("SQLite WAL task storage initialized at: %s", self.db_path)

    async def enqueue(
        self,
        chat_id: int,
        user_id: int,
        message_id: int,
        prompt: str,
        model: str,
        aspect_ratio: str = "16:9",
        duration: int = 5,
        image_url: str | None = None,
    ) -> TaskRecord:
        """Enqueues a new video generation task."""
        task_id = str(uuid.uuid4())
        now = time.time()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO video_tasks (
                    task_id, chat_id, user_id, message_id, prompt, model,
                    aspect_ratio, duration, image_url, status, progress,
                    created_at, updated_at, attempts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    task_id,
                    chat_id,
                    user_id,
                    message_id,
                    prompt,
                    model,
                    aspect_ratio,
                    duration,
                    image_url,
                    "pending",
                    0,
                    now,
                    now,
                    0,
                ),
            )
            row_id = cursor.lastrowid
            await db.commit()

        return TaskRecord(
            id=row_id,
            task_id=task_id,
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            duration=duration,
            image_url=image_url,
            status="pending",
            progress=0,
            upstream_task_id=None,
            video_url=None,
            error_message=None,
            created_at=now,
            updated_at=now,
            attempts=0,
        )

    async def get_active_tasks(self) -> list[TaskRecord]:
        """Fetches all tasks currently pending or processing."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM video_tasks
                WHERE status IN ('pending', 'submitting', 'processing')
                ORDER BY created_at ASC;
                """
            )
            rows = await cursor.fetchall()

        return [
            TaskRecord(
                id=row["id"],
                task_id=row["task_id"],
                chat_id=row["chat_id"],
                user_id=row["user_id"],
                message_id=row["message_id"],
                prompt=row["prompt"],
                model=row["model"],
                aspect_ratio=row["aspect_ratio"],
                duration=row["duration"],
                image_url=row["image_url"],
                status=row["status"],
                progress=row["progress"],
                upstream_task_id=row["upstream_task_id"],
                video_url=row["video_url"],
                error_message=row["error_message"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                attempts=row["attempts"],
            )
            for row in rows
        ]

    async def get_task(self, task_id: str) -> TaskRecord | None:
        """Fetches task by task_id."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM video_tasks WHERE task_id = ?;", (task_id,)
            )
            row = await cursor.fetchone()

        if not row:
            return None

        return TaskRecord(
            id=row["id"],
            task_id=row["task_id"],
            chat_id=row["chat_id"],
            user_id=row["user_id"],
            message_id=row["message_id"],
            prompt=row["prompt"],
            model=row["model"],
            aspect_ratio=row["aspect_ratio"],
            duration=row["duration"],
            image_url=row["image_url"],
            status=row["status"],
            progress=row["progress"],
            upstream_task_id=row["upstream_task_id"],
            video_url=row["video_url"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            attempts=row["attempts"],
        )

    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: int | None = None,
        upstream_task_id: str | None = None,
        video_url: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Updates task state in SQLite."""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            updates = ["status = ?", "updated_at = ?"]
            params: list[object] = [status, now]

            if progress is not None:
                updates.append("progress = ?")
                params.append(progress)
            if upstream_task_id is not None:
                updates.append("upstream_task_id = ?")
                params.append(upstream_task_id)
            if video_url is not None:
                updates.append("video_url = ?")
                params.append(video_url)
            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)

            params.append(task_id)
            query = f"UPDATE video_tasks SET {', '.join(updates)} WHERE task_id = ?;"
            await db.execute(query, params)
            await db.commit()

    async def increment_attempts(self, task_id: str) -> int:
        """Increment attempt counter for task and return new count."""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE video_tasks SET attempts = attempts + 1, updated_at = ? WHERE task_id = ?;",
                (now, task_id),
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT attempts FROM video_tasks WHERE task_id = ?;", (task_id,)
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else 1


class QueueWorker:
    """Background worker that continuously processes queued tasks and updates Telegram."""

    def __init__(
        self,
        bot: Bot,
        queue: TaskQueue,
        video_service: VideoService,
        max_concurrent: int = 5,
        poll_interval: float = 3.0,
        max_poll_timeout: int = 600,
    ) -> None:
        self.bot = bot
        self.queue = queue
        self.video_service = video_service
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.poll_interval = poll_interval
        self.max_poll_timeout = max_poll_timeout
        self._running = False
        self._worker_task: asyncio.Task[None] | None = None
        self._processing_tasks: set[str] = set()

    def start(self) -> None:
        """Starts background worker task."""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._run_loop())
            logger.info("Task queue background worker started.")

    async def stop(self) -> None:
        """Stops background worker task cleanly."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Task queue background worker stopped.")

    async def _run_loop(self) -> None:
        """Main queue monitoring loop."""
        # Initial sleep to allow bot to complete connection
        await asyncio.sleep(1.0)
        logger.info("QueueWorker running loop active, checking for recoverable tasks...")

        while self._running:
            try:
                active_tasks = await self.queue.get_active_tasks()
                for task in active_tasks:
                    if task.task_id not in self._processing_tasks:
                        self._processing_tasks.add(task.task_id)
                        asyncio.create_task(self._process_task_wrapper(task))

            except Exception as e:
                logger.exception("Error in QueueWorker run loop: %s", e)

            await asyncio.sleep(self.poll_interval)

    async def _process_task_wrapper(self, task: TaskRecord) -> None:
        """Acquires semaphore and executes task processing."""
        try:
            async with self.semaphore:
                await self._execute_task(task)
        finally:
            self._processing_tasks.discard(task.task_id)

    async def _execute_task(self, task: TaskRecord) -> None:
        """Handles single task lifecycle: submit, poll with progress, deliver video."""
        logger.info("Processing task %s (model: %s)", task.task_id, task.model)
        start_time = task.created_at

        # DLQ check: increment attempt counter and quarantine if repeatedly failing
        current_attempts = await self.queue.increment_attempts(task.task_id)
        if current_attempts > 3:
            logger.error(
                "Task %s exceeded retry threshold (attempts=%d). Moving to Dead-Letter Queue (DLQ).",
                task.task_id,
                current_attempts,
            )
            await self._fail_task(
                task,
                "⚠️ **Задача помещена в карантин (Dead-Letter Queue).**\n"
                "Превышено максимальное число повторных попыток (3). Пожалуйста, создайте задачу заново.",
            )
            return

        # 1. Submit upstream if not already submitted
        upstream_id = task.upstream_task_id
        if not upstream_id:
            try:
                await self.queue.update_status(task.task_id, "submitting", progress=5)
                upstream_id = await self.video_service.create_task(
                    prompt=task.prompt,
                    model=task.model,
                    duration=task.duration,
                    aspect_ratio=task.aspect_ratio,
                    image_url=task.image_url,
                )
                await self.queue.update_status(
                    task.task_id,
                    "processing",
                    progress=10,
                    upstream_task_id=upstream_id,
                )
            except InsufficientBalanceError as e:
                logger.error("Insufficient balance for task %s: %s", task.task_id, e)
                await self._fail_task(
                    task,
                    "💳 **Недостаточно средств на балансе NormaHub.**\n"
                    "Пожалуйста, пополните счет в рублях через СБП/МИР на [normahub.cc](https://normahub.cc).",
                )
                return
            except Exception as e:
                logger.exception("Failed to submit task %s: %s", task.task_id, e)
                await self._fail_task(task, f"❌ **Ошибка отправки задачи в нейросеть:** {e}")
                return

        # 2. Poll upstream task with progress updates
        last_edit_time = 0.0
        last_progress = task.progress
        poll_delay = self.poll_interval

        while time.time() - start_time < self.max_poll_timeout:
            elapsed = int(time.time() - start_time)

            try:
                status_info = await self.video_service.get_task_status(upstream_id)

                if status_info.status == "completed":
                    if not status_info.video_url:
                        await self._fail_task(task, "❌ Задача завершена, но URL видео пуст.")
                        return

                    await self._complete_task(task, status_info.video_url, elapsed)
                    return

                if status_info.status == "failed":
                    err_msg = status_info.error or "Генерация отклонена нейросетью"
                    await self._fail_task(task, f"❌ **Генерация не удалась:** {err_msg}")
                    return

                # Calculate progress
                reported_progress = status_info.progress
                # Synthesize visual progress if backend returns 0 during processing
                if reported_progress <= 0:
                    simulated = min(92, 10 + int(elapsed * 1.5))
                    display_progress = max(last_progress, simulated)
                else:
                    display_progress = reported_progress

                # Update database
                await self.queue.update_status(
                    task.task_id,
                    "processing",
                    progress=display_progress,
                )

                # Update Telegram message every ~4 seconds to avoid FloodWait
                now = time.time()
                if (now - last_edit_time >= 4.0) or (display_progress - last_progress >= 15):
                    last_edit_time = now
                    last_progress = display_progress
                    await self._update_telegram_progress(task, display_progress, elapsed)

            except Exception as e:
                logger.warning("Transient error polling task %s: %s", upstream_id, e)

            await asyncio.sleep(poll_delay)
            # Gentle exponential backoff up to 7s
            poll_delay = min(poll_delay * 1.1, 7.0)

        # Timeout reached
        await self._fail_task(
            task,
            f"⌛ **Превышено время ожидания генерации** ({self.max_poll_timeout}с). "
            "Нейросеть перегружена. Попробуйте повторить запрос позже.",
        )

    async def _update_telegram_progress(
        self,
        task: TaskRecord,
        progress: int,
        elapsed_seconds: int,
    ) -> None:
        """Edits status message in Telegram with animated progress bar."""
        try:
            await self.bot.send_chat_action(chat_id=task.chat_id, action=ChatAction.RECORD_VIDEO)

            progress_bar = make_progress_bar(progress, length=10)
            stage_text = get_stage_description(progress, task.model)
            model_name = "ByteDance SeeDance 2.5" if "seedance" in task.model.lower() else "Grok Imagine Video"

            text = (
                f"🎬 **{model_name}**\n\n"
                f"{progress_bar} **{progress}%**\n"
                f"⏳ *{stage_text}*\n\n"
                f"⏱️ Прошло: `{format_duration(elapsed_seconds)}`\n"
                f"📝 *Промпт:* _{truncate_text(task.prompt, 180)}_"
            )

            await self.bot.edit_message_text(
                chat_id=task.chat_id,
                message_id=task.message_id,
                text=text,
            )
        except Exception as e:
            # Telegram message not modified or FloodWait - ignore gracefully
            logger.debug("Could not edit progress message %s: %s", task.message_id, e)

    async def _complete_task(
        self,
        task: TaskRecord,
        video_url: str,
        elapsed_seconds: int,
    ) -> None:
        """Marks task as completed in DB and sends video to Telegram."""
        logger.info("Task %s completed in %ds! Video URL: %s", task.task_id, elapsed_seconds, video_url)
        await self.queue.update_status(task.task_id, "completed", progress=100, video_url=video_url)

        try:
            # Update status message
            try:
                await self.bot.edit_message_text(
                    chat_id=task.chat_id,
                    message_id=task.message_id,
                    text="✨ **Видео готово! Отправляю файл в Telegram...**",
                )
            except Exception:
                pass

            await self.bot.send_chat_action(chat_id=task.chat_id, action=ChatAction.UPLOAD_VIDEO)

            model_label = "ByteDance SeeDance 2.5" if "seedance" in task.model.lower() else "Grok Imagine Video"
            caption = (
                f"🎬 **{model_label}**\n\n"
                f"📝 **Промпт:** {task.prompt}\n"
                f"📐 Соотношение: `{task.aspect_ratio}` | ⏱️ Длительность: `{task.duration}с`\n"
                f"⚡ Время рендеринга: `{format_duration(elapsed_seconds)}`\n\n"
                f"🚀 Сгенерировано через шлюз [NormaHub](https://normahub.cc)"
            )

            await self.bot.send_video(
                chat_id=task.chat_id,
                video=video_url,
                caption=caption,
            )

            # Optionally remove status message after delivery
            try:
                await self.bot.delete_message(chat_id=task.chat_id, message_id=task.message_id)
            except Exception:
                pass

        except Exception as e:
            logger.exception("Error sending completed video to user %s: %s", task.user_id, e)
            try:
                await self.bot.send_message(
                    chat_id=task.chat_id,
                    text=(
                        f"✨ **Видео готово**, но возникла ошибка при прямой отправке файла: {e}\n\n"
                        f"🔗 [Скачать готовое видео по прямой ссылке]({video_url})"
                    ),
                )
            except Exception:
                pass

    async def _fail_task(self, task: TaskRecord, error_message: str) -> None:
        """Marks task as failed and notifies user."""
        logger.error("Task %s failed: %s", task.task_id, error_message)
        await self.queue.update_status(
            task.task_id,
            "failed",
            error_message=error_message,
        )
        try:
            await self.bot.edit_message_text(
                chat_id=task.chat_id,
                message_id=task.message_id,
                text=error_message,
            )
        except Exception:
            try:
                await self.bot.send_message(chat_id=task.chat_id, text=error_message)
            except Exception:
                pass
