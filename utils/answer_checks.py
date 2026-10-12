import re

# Phrases that state the candidate does not know / cannot answer (compared after normalisation:
# lower case, apostrophes dropped, other punctuation turned into spaces).
_PHRASES = [
    "i do not know", "do not know", "i dont know", "dont know", "dunno", "idk",
    "i have no idea", "i dont have any idea", "i dont have an idea", "i dont have idea", "no idea",
    "i have no clue", "no clue",
    "i am not sure", "im not sure", "not sure",
    "i do not remember", "i dont remember", "dont remember",
    "i cannot answer", "i cant answer", "cant answer", "cannot answer",
    "i dont have an answer", "i have no knowledge", "no knowledge", "no experience",
    "not familiar", "no comment",
]
_PHRASE_RX = re.compile(r"\b(?:" + "|".join(sorted((re.escape(p) for p in _PHRASES), key=len, reverse=True)) + r")\b")

# A reply that is only one of these words is also a non-answer. Kept exact-match because
# "pass" or "skip" can be part of a real answer ("pass by reference").
_EXACT = {"pass", "skip", "next", "next question", "no answer", "nothing", "nope", "na", "n a"}

# Words that add no technical content; if nothing else is left after removing the phrase, it is a non-answer.
_FILLER = set("""
um umm uh hmm sorry sir maam madam honestly well ok okay actually really truly about this that it the question topic
answer to be honest at all right now currently thank you thanks please so but yet i im am a sure exactly one also of
with on in for not no dont know have any idea clue fully as today afraid unfortunately yes yeah nope remember with
familiar experience knowledge an
""".split())

_SHORT_WORDS = 6  # a statement of ignorance this short is a non-answer even if it names the topic


def _normalise(text: str) -> str:
    text = (text or "").lower().replace("’", "'").replace("'", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text)).strip()


def is_non_answer(text: str) -> bool:
    """True when the candidate only says they don't know / can't answer, so a follow-up would be pointless.

    A real answer that happens to include such a phrase ("I'm not sure about edge cases, but a HashMap
    resizes at its load factor") is NOT a non-answer.
    """
    norm = _normalise(text)
    if not norm:
        return False
    if norm in _EXACT:
        return True

    if not _PHRASE_RX.search(norm):
        return False
    if len(norm.split()) <= _SHORT_WORDS:
        return True
    leftover = _PHRASE_RX.sub(" ", norm).split()
    return all(word in _FILLER for word in leftover)
