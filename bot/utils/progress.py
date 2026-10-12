"""Visual progress bar generator for Telegram video generation."""


def make_progress_bar(percent: int, length: int = 10) -> str:
    """Renders a unicode progress bar with filled and empty blocks.

    Examples:
        make_progress_bar(0)   -> "[░░░░░░░░░░]"
        make_progress_bar(50)  -> "[█████░░░░░]"
        make_progress_bar(100) -> "[██████████]"
    """
    clamped = max(0, min(100, percent))
    filled_count = round((clamped / 100) * length)
    empty_count = length - filled_count
    return f"[{'█' * filled_count}{'░' * empty_count}]"


def get_stage_description(percent: int, model: str) -> str:
    """Returns human-friendly stage description based on generation progress."""
    model_lower = model.lower()
    is_grok = "grok" in model_lower

    if percent <= 5:
        return "В очереди GPU-кластера NormaHub..."
    elif percent <= 25:
        return f"Инициализация нейросети {'Grok Imagine' if is_grok else 'SeeDance 2.5'} и токенизация..."
    elif percent <= 50:
        return "Диффузионный рендеринг ключевых кадров и физики сцены..."
    elif percent <= 75:
        return "Синтез межкадровой когерентности и интерполяция движения..."
    elif percent <= 95:
        return "Финальный апскейл и кодирование MP4-потока..."
    else:
        return "Рендеринг завершен! Передача видео в Telegram..."
