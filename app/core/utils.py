import hashlib
import re

def armor_text(text: str | None, user_id: str | int | None = None) -> str:
    """
    Advanced watermarking that hinders scraping and allows tracing.
    1. Deterministic phrasing variation based on user_id.
    2. Invisible zero-width markers at unique positions.
    3. Character-level spacing (original armor).
    """
    if not text:
        return ""

    user_seed = int(hashlib.sha256(str(user_id).encode()).hexdigest(), 16) if user_id else 0

    # 1. Deterministic Phrasing Variation (Synonym swapping)
    # This slightly alters the text without changing meaning, making every user's text unique.
    synonyms = {
        r"\bWhich\b": ["What", "Which"],
        r"\bselect\b": ["choose", "pick", "select"],
        r"\bcorrect\b": ["right", "correct", "accurate"],
        r"\bfollowing\b": ["subsequent", "following"],
        r"\bIdentify\b": ["Find", "Identify", "Locate"],
        r"\bExplain\b": ["Describe", "Explain"],
    }

    if user_id:
        for pattern, choices in synonyms.items():
            if re.search(pattern, text, re.IGNORECASE):
                # Pick a Choice based on user_seed
                choice = choices[user_seed % len(choices)]
                # Preserving Case
                def replace_case(match):
                    m = match.group(0)
                    if m.isupper(): return choice.upper()
                    if m[0].isupper(): return choice.capitalize()
                    return choice.lower()
                text = re.sub(pattern, replace_case, text, flags=re.IGNORECASE)

    # 2. Deterministic Invisible Markers
    # Inject \u200c (Zero Width Non-Joiner) at specific character indices
    if user_id:
        chars = list(text)
        # Choose 3 positions based on seed
        for i in range(3):
            pos = (user_seed >> (i * 8)) % len(chars)
            chars[pos] = chars[pos] + "\u200c" 
        text = "".join(chars)

    # 3. Original Armor (Zero Width Space between every char)
    return "\u200b".join(list(text))

