"""
Name Detection System for Dymo Code
Automatically detects when a user mentions their name and saves it
"""

import re
from typing import Optional, Tuple

from .memory import memory
from .logger import log_debug


# ═══════════════════════════════════════════════════════════════════════════════
# Name Detection Patterns
# ═══════════════════════════════════════════════════════════════════════════════

# Patterns that indicate user is telling their name
NAME_PATTERNS = [
    # English patterns
    r"(?:my name is|i'm|i am|call me|they call me|name's|i go by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    r"(?:i'm|i am)\s+([A-Z][a-z]+)(?:\s|,|\.|\!|$)",
    r"^([A-Z][a-z]+)\s+(?:here|speaking)",

    # Spanish patterns
    r"(?:me llamo|mi nombre es|soy|llámame|me dicen)\s+([A-Z][a-zñáéíóú]+(?:\s+[A-Z][a-zñáéíóú]+)?)",
    r"(?:soy)\s+([A-Z][a-zñáéíóú]+)(?:\s|,|\.|\!|$)",

    # Direct introduction patterns
    r"^(?:hey,?\s+)?(?:i'm|i am|soy|me llamo)\s+([A-Z][a-z]+)",
]

# Words that look like names but aren't (false positives)
FALSE_POSITIVES = {
    "the", "and", "or", "but", "so", "yes", "no", "ok", "okay",
    "please", "thanks", "thank", "sorry", "hello", "hi", "hey",
    "good", "great", "nice", "sure", "yeah", "yep", "nope",
    "maybe", "perhaps", "well", "just", "only", "very",
    "here", "there", "where", "when", "what", "who", "why", "how",
    "this", "that", "these", "those", "some", "any", "all",
    "can", "could", "would", "should", "will", "might",
    "have", "has", "had", "do", "does", "did", "done",
    "be", "been", "being", "am", "is", "are", "was", "were",
    "not", "now", "then", "also", "too", "really",
    "create", "make", "build", "write", "read", "open", "close",
    "file", "folder", "code", "project", "app", "system",
    "python", "javascript", "java", "node", "react", "vue",
}

# Common names for validation (add more as needed)
COMMON_NAMES = {
    # English names
    "james", "john", "robert", "michael", "david", "william", "richard",
    "joseph", "thomas", "charles", "christopher", "daniel", "matthew",
    "anthony", "mark", "donald", "steven", "paul", "andrew", "joshua",
    "mary", "patricia", "jennifer", "linda", "elizabeth", "barbara",
    "susan", "jessica", "sarah", "karen", "nancy", "lisa", "betty",
    "alex", "sam", "jordan", "taylor", "morgan", "casey", "riley",

    # Spanish names
    "carlos", "miguel", "jose", "juan", "pedro", "luis", "antonio",
    "francisco", "manuel", "rafael", "fernando", "roberto", "alberto",
    "maria", "carmen", "ana", "isabel", "rosa", "laura", "sofia",
    "lucia", "elena", "paula", "marta", "cristina", "patricia",
    "javier", "sergio", "diego", "pablo", "alejandro", "adrian",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Name Detection Functions
# ═══════════════════════════════════════════════════════════════════════════════

def extract_name(text: str) -> Optional[str]:
    """
    Extract a potential name from user input.
    Returns the name if detected, None otherwise.
    """
    if not text:
        return None

    # Try each pattern
    for pattern in NAME_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            potential_name = match.group(1).strip()

            # Validate the name
            if is_valid_name(potential_name): return potential_name.title()  # Capitalize properly

    return None


def is_valid_name(name: str) -> bool:
    """
    Validate if a string is likely a real name.
    """
    if not name: return False

    name_lower = name.lower()

    # Check against false positives
    if name_lower in FALSE_POSITIVES: return False

    # Check length (names are usually 2-20 characters)
    if len(name) < 2 or len(name) > 20: return False

    # Check if it's mostly letters
    if not name.replace(" ", "").isalpha(): return False

    # Check if it's a common name (bonus points)
    if name_lower in COMMON_NAMES: return True

    # If starts with capital and has reasonable length, accept it
    if name[0].isupper() and len(name) >= 2: return True

    return False


def detect_and_save_name(user_input: str, assistant_response: str = None) -> Optional[str]:
    """
    Detect if user mentioned their name and save it.
    Returns the detected name if found and saved, None otherwise.
    """
    # First check user input
    name = extract_name(user_input)

    if name:
        # Check if we already have this name
        existing_name = memory.get_profile("name")
        if existing_name and existing_name.lower() == name.lower(): return None  # Already saved

        # Save the name
        memory.set_profile("name", name, category="identity")
        log_debug(f"Auto-detected and saved user name: {name}")
        return name

    return None


def get_saved_name() -> Optional[str]:
    """Get the saved user name if any"""
    return memory.get_profile("name")


# ═══════════════════════════════════════════════════════════════════════════════
# Integration with Agent
# ═══════════════════════════════════════════════════════════════════════════════

def check_for_name_in_message(message: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a message contains a name introduction.
    Returns (found, name) tuple.
    """
    name = extract_name(message)
    if name: return True, name
    return False, None
