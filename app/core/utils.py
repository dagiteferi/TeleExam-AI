from __future__ import annotations

def armor_text(text: str | None) -> str:
    """Injects zero-width space (\u200b) between every character to hinder scraping and automatic search."""
    if not text:
        return ""
    # We join with zero-width space. This is invisible to the user but breaks string matching for bots.
    return "\u200b".join(list(text))
