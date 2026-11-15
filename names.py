"""Name helpers for Designer Lens. Pure functions only.

Moved here unchanged from fetch_wikipedia.py (name_tokens, title_matches)
and app.py (slug, body) for the testing assignment, Step 2.
"""

import hashlib
import re
import unicodedata


# ---- from fetch_wikipedia.py ----

def name_tokens(text):
    """'Álvaro Siza' -> {'alvaro', 'siza'} (accents removed, lowercase)."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return set(re.findall(r"[a-z0-9]+", plain.lower()))


def title_matches(title, name):
    """'Qi Kang (architect)' matches 'Qi Kang'. The words must be exactly the
    same, so 'Liu Xiaodong' can't stand in for 'Li Xiaodong' and
    'Xiao Hui Wang' can't stand in for 'Wang Hui'."""
    core = re.sub(r"\s*\(.*\)\s*$", "", title)
    return name_tokens(core) == name_tokens(name)


# ---- from app.py ----

def slug(name):
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    result = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")
    if result:
        return result
    # Nothing survived ASCII conversion (e.g. a Chinese name). If the name has
    # real letters, give it a stable id derived from the name so different
    # names don't collide.
    if any(c.isalnum() for c in name):
        return "n-" + hashlib.sha1(name.strip().encode("utf-8")).hexdigest()[:10]
    return "unnamed"


def body(document):
    """Stored text is 'Designer - Section: text'. Return just the text."""
    return document.split(": ", 1)[-1]
