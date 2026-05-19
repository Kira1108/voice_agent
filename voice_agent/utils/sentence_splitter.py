import re
import time
SENTENCE_ENDING_PUNCTUATION: frozenset[str] = frozenset(
    {
        # Latin script punctuation (most European languages, Filipino, etc.)
        ".",
        "!",
        "?",
        ";",
        "…",
        # East Asian punctuation (Chinese (Traditional & Simplified), Japanese, Korean)
        "。",  # Ideographic full stop
        "？",  # Full-width question mark
        "！",  # Full-width exclamation mark
        "；",  # Full-width semicolon
        "．",  # Full-width period
        "｡",  # Halfwidth ideographic period
        # Indic scripts punctuation (Hindi, Sanskrit, Marathi, Nepali, Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati, Punjabi, Oriya, Assamese)
        "।",  # Devanagari danda (single vertical bar)
        "॥",  # Devanagari double danda (double vertical bar)
        # Arabic script punctuation (Arabic, Persian, Urdu, Pashto)
        "؟",  # Arabic question mark
        "؛",  # Arabic semicolon
        "۔",  # Urdu full stop
        "؏",  # Arabic sign misra (classical texts)
        # Thai
        "।",  # Thai uses Devanagari-style punctuation in some contexts
        # Myanmar/Burmese
        "၊",  # Myanmar sign little section
        "။",  # Myanmar sign section
        # Khmer
        "។",  # Khmer sign khan
        "៕",  # Khmer sign bariyoosan
        # Lao
        "໌",  # Lao cancellation mark (used as period)
        "༎",  # Tibetan mark delimiter tsheg bstar (also used in Lao contexts)
        # Tibetan
        "།",  # Tibetan mark intersyllabic tsheg
        "༎",  # Tibetan mark delimiter tsheg bstar
        # Armenian
        "։",  # Armenian full stop
        "՜",  # Armenian exclamation mark
        "՞",  # Armenian question mark
        # Ethiopic script (Amharic)
        "።",  # Ethiopic full stop
        "፧",  # Ethiopic question mark
        "፨",  # Ethiopic paragraph separator
        ".",
        "!", 
        "?", 
        ";", 
        "…"
    }
)

SENTENCE_ENDING_PUNCTUATION_STR = "".join(SENTENCE_ENDING_PUNCTUATION)

def sentence_tokenize(text: str) -> list[str]:
    
    parts = re.split(f"([{SENTENCE_ENDING_PUNCTUATION_STR}]+)", text)
    sentences = []
    
    for i in range(0, len(parts) - 1, 2):
        sentences.append(parts[i] + parts[i+1])
        
    if parts[-1]:
        sentences.append(parts[-1])
        
    return [s.strip() for s in sentences if s.strip()]

