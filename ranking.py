"""Decisions Designer Lens makes on search results. Pure functions: they
take what collection.query() returned (or the ranking built from it), so
tests can pass hand-written results instead of running ChromaDB.

Moved out of app.py for the testing assignment, Step 2. The code inside
each function is the code that was in app.py, unchanged.
"""

# Chroma's default distance: lower = more similar. Picked by looking at real
# results: good matches were 1.0-1.3, a nonsense query ("how do I fix a flat
# bicycle tire") was ~1.7. But unrelated architecture also lands at 1.15-1.35,
# so a distance alone can't say "strong match". It is used for two things only:
RELATED = 1.45      # nothing closer than this -> say "no good match"
CLOSE_BAND = 0.08   # show only designers within this of the best one
# For ideas ("did someone already do this?") we need to be much stricter.
# The Napier's-rods idea, which nothing in the library resembles, scored 1.16.
# Only Wikipedia passages count here: short notes sit closer to short ideas
# just because both are short (a hotel-lobby note scored 0.89 against an
# unrelated ceiling idea).
IDEA_VERY_CLOSE = 0.90
IDEA_RELATED = 1.10


def rank_by_designer(texts, res, top=4):
    """Group chunk results by designer; each designer scores its best chunk.
    (Was the second half of app.similar_designers.)"""
    hits = {}  # designer_id -> list of (distance, document, metadata, query)
    for qi, query in enumerate(texts):
        for doc, meta, dist in zip(res["documents"][qi], res["metadatas"][qi],
                                   res["distances"][qi]):
            hits.setdefault(meta["designer_id"], []).append((dist, doc, meta, query))

    ranked = []
    for designer_id, found in hits.items():
        found.sort(key=lambda h: h[0])
        score = found[0][0]  # a designer's best-matching chunk
        name = found[0][2]["name_en"]
        if designer_id == "unassigned":
            name = "Your note"
        ranked.append({"id": designer_id, "name": name,
                       "discipline": found[0][2].get("discipline", ""),
                       "score": score, "hits": found[:2]})
    ranked.sort(key=lambda r: r["score"])
    return ranked[:top]


def pick_for_question(ranked):
    """Which results a question shows. (Was inside app.ask_question.)"""
    # My own notes are short, so they score closer than Wikipedia passages
    # (a note scored 1.00 against a matching question, the best Wikipedia
    # passage 1.21). If the band were measured from the note, every designer
    # would be cut and the brief would have nothing to say. So notes and
    # Wikipedia are filtered separately.
    own = [r for r in ranked if r["hits"][0][2]["source"] == "mine"]
    published = [r for r in ranked if r["hits"][0][2]["source"] != "mine"]
    if published:
        # Keep only designers about as close as the best one. Further down the
        # list the matches were mostly generic (I. M. Pei for "dirt raised into
        # rooms", because his excerpt mentioned building workers).
        best = published[0]["score"]
        published = [r for r in published if r["score"] < RELATED
                     and r["score"] <= best + CLOSE_BAND][:4]
    own = [r for r in own if r["score"] < RELATED][:2]
    ranked = sorted(published + own, key=lambda r: r["score"])
    return ranked


def idea_verdict(ranked):
    """Rough verdict when there is no language model: "very close",
    "related" or "new". (Was the end of app.add_idea.)"""
    published = [r["score"] for r in ranked if r["hits"][0][2]["source"] == "wikipedia"]
    best = min(published) if published else 9
    if best < IDEA_VERY_CLOSE:
        return "very close"
    elif best < IDEA_RELATED:
        return "related"
    return "new"
