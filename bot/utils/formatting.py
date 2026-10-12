"""Formatting utilities for Telegram text and markdown."""

import re


def escape_md(text: str) -> str:
    """Escapes Telegram MarkdownV2 special characters."""
    special_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(special_chars)}])", r"\\\1", text)


def format_duration(seconds: float | int) -> str:
    """Formats seconds into human-readable duration string."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}с"
    minutes = seconds // 60
    rem_seconds = seconds % 60
    if rem_seconds == 0:
        return f"{minutes}м"
    return f"{minutes}м {rem_seconds}с"


def truncate_text(text: str, max_length: int = 300) -> str:
    """Safely truncates text adding an ellipsis if exceeded."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
