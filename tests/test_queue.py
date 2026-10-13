"""Tests for TaskQueue SQLite WAL storage and crash recovery."""

import pytest

from bot.services.task_queue import TaskQueue


@pytest.mark.asyncio
async def test_task_queue_enqueue_and_get(temp_task_queue: TaskQueue):
    """Tests enqueuing a task and retrieving it by task_id."""
    queue = temp_task_queue

    task = await queue.enqueue(
        chat_id=1001,
        user_id=2002,
        message_id=3003,
        prompt="A neon cyber punk city with flying cars",
        model="seedance-2.5",
        aspect_ratio="16:9",
        duration=5,
    )

    assert task.task_id is not None
    assert task.chat_id == 1001
    assert task.status == "pending"
    assert task.progress == 0

    fetched = await queue.get_task(task.task_id)
    assert fetched is not None
    assert fetched.prompt == "A neon cyber punk city with flying cars"
    assert fetched.model == "seedance-2.5"


@pytest.mark.asyncio
async def test_task_queue_status_transitions(temp_task_queue: TaskQueue):
    """Tests updating status, progress, upstream task id, and completion."""
    queue = temp_task_queue

    task = await queue.enqueue(
        chat_id=1001,
        user_id=2002,
        message_id=3003,
        prompt="Grok stylized space render",
        model="grok-imagine-video-1.5",
    )

    # Transition to submitting
    await queue.update_status(task.task_id, "submitting", progress=10)
    t1 = await queue.get_task(task.task_id)
    assert t1 is not None
    assert t1.status == "submitting"
    assert t1.progress == 10

    # Transition to processing with upstream task ID
    await queue.update_status(
        task.task_id,
        "processing",
        progress=45,
        upstream_task_id="up_video_9999",
    )
    t2 = await queue.get_task(task.task_id)
    assert t2 is not None
    assert t2.status == "processing"
    assert t2.progress == 45
    assert t2.upstream_task_id == "up_video_9999"

    # Mark completed
    await queue.update_status(
        task.task_id,
        "completed",
        progress=100,
        video_url="https://api.normahub.cc/v1/videos/downloads/render.mp4",
    )
    t3 = await queue.get_task(task.task_id)
    assert t3 is not None
    assert t3.status == "completed"
    assert t3.progress == 100
    assert t3.video_url == "https://api.normahub.cc/v1/videos/downloads/render.mp4"


@pytest.mark.asyncio
async def test_task_queue_crash_recovery(temp_task_queue: TaskQueue):
    """Verifies that active tasks remain in active list across restarts."""
    queue = temp_task_queue

    # 1. Enqueue task 1 (pending)
    t1 = await queue.enqueue(
        chat_id=1, user_id=1, message_id=1, prompt="Task 1", model="seedance-2.5"
    )
    # 2. Enqueue task 2 and mark processing
    t2 = await queue.enqueue(
        chat_id=2, user_id=2, message_id=2, prompt="Task 2", model="grok-imagine-video-1.5"
    )
    await queue.update_status(t2.task_id, "processing", progress=50, upstream_task_id="up_2")

    # 3. Enqueue task 3 and mark completed
    t3 = await queue.enqueue(
        chat_id=3, user_id=3, message_id=3, prompt="Task 3", model="seedance-2.5"
    )
    await queue.update_status(t3.task_id, "completed", progress=100, video_url="http://done.mp4")

    # Simulate bot crash/restart: create new queue instance pointing to the same SQLite DB file
    recovered_queue = TaskQueue(db_path=queue.db_path)
    active_tasks = await recovered_queue.get_active_tasks()

    # Active tasks must contain t1 and t2, but NOT completed t3
    active_ids = {t.task_id for t in active_tasks}
    assert t1.task_id in active_ids
    assert t2.task_id in active_ids
    assert t3.task_id not in active_ids
    assert len(active_tasks) == 2


@pytest.mark.asyncio
async def test_task_queue_increment_attempts(temp_task_queue: TaskQueue):
    """Verifies attempt counting and incrementation for DLQ quarantine."""
    queue = temp_task_queue

    task = await queue.enqueue(
        chat_id=1, user_id=1, message_id=1, prompt="DLQ test", model="seedance-2.5"
    )

    count1 = await queue.increment_attempts(task.task_id)
    assert count1 == 1

    count2 = await queue.increment_attempts(task.task_id)
    assert count2 == 2

    count3 = await queue.increment_attempts(task.task_id)
    assert count3 == 3

    fetched = await queue.get_task(task.task_id)
    assert fetched is not None
    assert fetched.attempts == 3
