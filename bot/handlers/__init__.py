"""Handlers package exports."""

from bot.handlers.commands import router as commands_router
from bot.handlers.video import router as video_router
from bot.handlers.voice import router as voice_router

__all__ = ["commands_router", "video_router", "voice_router"]
