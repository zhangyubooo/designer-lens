"""Text rules for Designer Lens: how Wikipedia text is judged and cut into
chunks. Pure functions only: no ChromaDB, no Wikipedia, no files, so tests
can call them directly.

Moved here unchanged from build_db.py and fetch_wikipedia.py (testing
assignment, Step 2). The two looks_like_a_list functions really are
different rules; they were two functions with the same name in two files.
"""

import re

MAX_WORDS = 150


# ---- from build_db.py ----

# Sections about a designer's life or fame, not how they design.
# Step 5 showed these crowding real answers (e.g. a bibliography matching
# "temporary shelters"; Noguchi "matching" Gehry through their Exhibitions
# sections). Only the last part of a title like
# "Works and publications > Fashion" is checked, so "Fashion" is kept.
SKIP_SECTION = re.compile(
    r"award|honou?r|recognition|personal life|^death$|works about|"
    r"bibliography|publications|writings|filmography|archives|exhibition", re.I)


def looks_like_a_list(text):
    """'Hanselmann House, Fort Wayne, Indiana, 1968' one per line: a list of
    names, not a description. Wikipedia prose comes as long paragraphs, so
    if most lines are short, it's a list."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 4:
        return False
    short = sum(1 for ln in lines if len(ln.split()) < 25)
    return short / len(lines) >= 0.6


def keep_section(section):
    title = section["section"].split(" > ")[-1]
    if SKIP_SECTION.search(title):
        return False
    if "quot" in title.lower():  # a designer's own words: short lines, but gold
        return True
    return not looks_like_a_list(section["text"])


def split_long(text, max_words=MAX_WORDS):
    """Split one paragraph that is too long, at sentence ends."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces, current = [], []
    for s in sentences:
        if current and len(" ".join(current + [s]).split()) > max_words:
            pieces.append(" ".join(current))
            current = []
        current.append(s)
    if current:
        pieces.append(" ".join(current))
    return pieces


def chunk_text(text, max_words=MAX_WORDS):
    """Pack whole paragraphs together until the next one would go over the
    limit, so a chunk usually ends where the author ended a thought."""
    paragraphs = []
    for p in text.split("\n"):
        p = p.strip()
        if not p:
            continue
        paragraphs.extend(split_long(p) if len(p.split()) > max_words else [p])

    chunks, current = [], []
    for p in paragraphs:
        if current and len(" ".join(current + [p]).split()) > max_words:
            chunks.append(" ".join(current))
            current = []
        current.append(p)
    if current:
        chunks.append(" ".join(current))
    return chunks


# ---- from fetch_wikipedia.py ----

# If the intro mentions none of these, we probably matched a different person.
DESIGN_WORDS = (
    "architect", "design", "artist", "typeface", "typograph",
    "interior", "studio", "firm", "practice", "fashion", "painter",
)


def looks_like_a_list_avg(text):
    """Sections like 'Works' are often just one building name per line.
    Those give the embedding model almost nothing to work with."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 4:
        return False
    avg_words = sum(len(ln.split()) for ln in lines) / len(lines)
    return avg_words < 8


def is_designer(intro):
    """Does this intro describe a designer? Disambiguation pages ('Wu Bin may
    refer to: ... a painter ...') mention design words too, so reject them."""
    text = intro.lower()
    if "may refer to" in text or "is the name of" in text:
        return False
    return any(word in text for word in DESIGN_WORDS)
