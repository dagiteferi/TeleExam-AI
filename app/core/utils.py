import hashlib
import re

def armor_text(text: str | None, user_id: str | int | None = None) -> str:
   
    if not text:
        return ""

    user_seed = int(hashlib.sha256(str(user_id).encode()).hexdigest(), 16) if user_id else 0

   
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
                
                choice = choices[user_seed % len(choices)]
                
                def replace_case(match):
                    m = match.group(0)
                    if m.isupper(): return choice.upper()
                    if m[0].isupper(): return choice.capitalize()
                    return choice.lower()
                text = re.sub(pattern, replace_case, text, flags=re.IGNORECASE)

  
    if user_id:
        chars = list(text)
       
        for i in range(3):
            pos = (user_seed >> (i * 8)) % len(chars)
            chars[pos] = chars[pos] + "\u200c" 
        text = "".join(chars)

    
    return "\u200b".join(list(text))

