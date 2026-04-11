import random
import re


def typing_delay(text: str) -> int:
    """Calculate a realistic typing delay in milliseconds for a text message.

    Simulates 30-50ms per character with some variance, plus a base delay.
    """
    base_delay = random.randint(400, 800)
    per_char = random.uniform(30, 50)
    delay = base_delay + int(len(text) * per_char)
    # Add some randomness (up to +/- 20%)
    variance = random.uniform(0.8, 1.2)
    return int(delay * variance)


def split_response(text: str) -> list[str]:
    """Split a long response into multiple text-message-sized chunks.

    Only splits if the text is longer than 150 characters.
    Splits at sentence boundaries.
    """
    if len(text) <= 150:
        return [text]

    # Split on sentence-ending punctuation followed by a space
    sentences = re.split(r"(?<=[.!?])\s+", text)

    if len(sentences) <= 1:
        return [text]

    # Group sentences into chunks, each under ~160 chars if possible
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if current_chunk and len(current_chunk) + len(sentence) + 1 > 160:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk = (current_chunk + " " + sentence).strip() if current_chunk else sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    # Limit to 2-3 messages max
    if len(chunks) > 3:
        # Re-merge into 2 chunks
        mid = len(sentences) // 2
        chunks = [
            " ".join(sentences[:mid]).strip(),
            " ".join(sentences[mid:]).strip(),
        ]

    return [c for c in chunks if c]


def check_emoji_restraint(text: str) -> str:
    """Strip excessive emojis — keep at most 1 emoji per message."""
    # Match common emoji unicode ranges
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map
        "\U0001f1e0-\U0001f1ff"  # flags
        "\U00002702-\U000027b0"
        "\U000024c2-\U0001f251"
        "\U0001f900-\U0001f9ff"  # supplemental
        "\U0001fa00-\U0001fa6f"
        "\U0001fa70-\U0001faff"
        "]+",
        flags=re.UNICODE,
    )

    emojis_found = emoji_pattern.findall(text)

    if len(emojis_found) <= 1:
        return text

    # Keep only the first emoji occurrence
    count = 0
    def _replace(match):
        nonlocal count
        count += 1
        if count == 1:
            return match.group()
        return ""

    return emoji_pattern.sub(_replace, text).strip()


def check_repetition(text: str, recent_messages: list[str]) -> str:
    """Flag and mildly adjust repeated phrases.

    If the response starts with the same opening as a recent message,
    rephrase the start slightly.
    """
    if not recent_messages:
        return text

    # Check if we're starting the same way as recent assistant messages
    openers = [
        "yeah", "so", "honestly", "look", "nah", "hey", "and", "but",
    ]

    text_lower = text.lower().strip()
    for recent in recent_messages[-3:]:
        recent_lower = recent.lower().strip()
        # Check if both start with the same word
        text_first = text_lower.split()[0] if text_lower.split() else ""
        recent_first = recent_lower.split()[0] if recent_lower.split() else ""

        if text_first == recent_first and text_first in openers:
            # Swap to a different opener
            alternatives = [o for o in openers if o != text_first]
            new_opener = random.choice(alternatives)
            # Replace first word
            words = text.split()
            if words:
                words[0] = new_opener
                text = " ".join(words)
            break

    return text


def humanize(text: str, recent_messages: list[str] | None = None) -> list[dict]:
    """Run all post-processing on a response and return message chunks with delays.

    Returns a list of dicts: [{"text": str, "delay_ms": int}, ...]
    """
    recent = recent_messages or []

    # Strip excessive emojis
    text = check_emoji_restraint(text)

    # Check for repetitive openers
    text = check_repetition(text, recent)

    # Split into chunks
    chunks = split_response(text)

    # Build output with delays
    result = []
    for i, chunk in enumerate(chunks):
        delay = typing_delay(chunk) if i > 0 else 0  # No delay for first message
        result.append({"text": chunk, "delay_ms": delay})

    return result
