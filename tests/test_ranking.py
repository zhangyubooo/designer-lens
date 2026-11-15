"""ranking: what Designer Lens shows after a search.

These tests use hand-written search results instead of ChromaDB. Distances:
lower = more similar. Thresholds (from ranking.py):
  RELATED = 1.45          nothing at or above this is shown for a question
  CLOSE_BAND = 0.08       designers must be within best + 0.08
  IDEA_VERY_CLOSE = 0.90  /  IDEA_RELATED = 1.10   (idea verdicts)
"""

from ranking import idea_verdict, pick_for_question, rank_by_designer


def result(designer, score, source="wikipedia"):
    """One entry of a ranking, shaped like rank_by_designer's output."""
    meta = {"designer_id": designer, "name_en": designer, "source": source,
            "section": "S", "discipline": ""}
    return {"id": designer, "name": designer, "discipline": "", "score": score,
            "hits": [(score, f"{designer} - S: text", meta, "q")]}


def query_result(*per_query):
    """Fake collection.query() output. Each argument is one query's list of
    (designer_id, distance) pairs."""
    res = {"documents": [], "metadatas": [], "distances": []}
    for pairs in per_query:
        res["documents"].append([f"{d} - S: chunk" for d, _ in pairs])
        res["metadatas"].append([{"designer_id": d, "name_en": d.title(),
                                  "discipline": "graphic", "section": "S",
                                  "source": "wikipedia"} for d, _ in pairs])
        res["distances"].append([dist for _, dist in pairs])
    return res


def ids(ranked):
    return [r["id"] for r in ranked]


# ---- rank_by_designer: rank designers, not chunks ----

def test_a_designer_with_many_chunks_appears_once_with_its_best_score():
    res = query_result([("scher", 1.30), ("scher", 1.10), ("scher", 1.20), ("ando", 1.15)])
    ranked = rank_by_designer(["q"], res, top=4)
    assert ids(ranked) == ["scher", "ando"]
    assert ranked[0]["score"] == 1.10


def test_ranking_is_sorted_closest_first_and_cut_to_top():
    res = query_result([("a", 1.4), ("b", 1.1), ("c", 1.3), ("d", 1.2)])
    assert ids(rank_by_designer(["q"], res, top=3)) == ["b", "d", "c"]


def test_results_from_several_queries_are_merged():
    res = query_result([("a", 1.30)], [("a", 1.05), ("b", 1.20)])
    ranked = rank_by_designer(["q1", "q2"], res, top=4)
    assert ids(ranked) == ["a", "b"]
    assert ranked[0]["score"] == 1.05


def test_unassigned_notes_are_called_your_note():
    res = query_result([("unassigned", 1.0)])
    assert rank_by_designer(["q"], res)[0]["name"] == "Your note"


def test_no_hits_gives_an_empty_ranking():
    assert rank_by_designer(["q"], query_result([])) == []


# ---- pick_for_question ----

def test_designers_within_the_band_are_kept_and_beyond_it_dropped():
    ranked = [result("a", 1.20), result("b", 1.25), result("c", 1.30)]
    assert ids(pick_for_question(ranked)) == ["a", "b"]


def test_exactly_best_plus_band_is_kept():
    ranked = [result("a", 1.20), result("b", 1.28)]   # 1.20 + 0.08 = 1.28
    assert ids(pick_for_question(ranked)) == ["a", "b"]


def test_nothing_at_or_above_related_is_shown():
    ranked = [result("a", 1.45), result("b", 1.46)]
    assert pick_for_question(ranked) == []


def test_at_most_four_designers():
    ranked = [result(c, 1.20) for c in "abcdef"]
    assert len(pick_for_question(ranked)) == 4


def test_a_close_note_does_not_cut_the_designers():
    # Notes are short, so they sit closer. The band must be measured from the
    # best designer (1.21), not from the note (1.00), or every designer is cut.
    ranked = [result("note", 1.00, source="mine"),
              result("a", 1.21), result("b", 1.27)]
    assert ids(pick_for_question(ranked)) == ["note", "a", "b"]


def test_at_most_two_notes_and_only_below_related():
    ranked = [result(n, s, source="mine") for n, s in
              [("n1", 1.0), ("n2", 1.1), ("n3", 1.2), ("n4", 1.5)]]
    assert ids(pick_for_question(ranked)) == ["n1", "n2"]


def test_only_notes_and_no_designers_does_not_crash():
    ranked = [result("note", 1.10, source="mine")]
    assert ids(pick_for_question(ranked)) == ["note"]


def test_empty_results_give_empty_list():
    assert pick_for_question([]) == []


# ---- idea_verdict ----

def test_idea_verdict_thresholds():
    assert idea_verdict([result("a", 0.89)]) == "very close"
    assert idea_verdict([result("a", 0.90)]) == "related"    # 0.90 is not < 0.90
    assert idea_verdict([result("a", 1.09)]) == "related"
    assert idea_verdict([result("a", 1.10)]) == "new"        # 1.10 is not < 1.10


def test_idea_verdict_uses_the_closest_wikipedia_result():
    assert idea_verdict([result("a", 1.30), result("b", 0.85)]) == "very close"


def test_idea_verdict_ignores_my_own_notes():
    # A note at 0.50 must not make an idea look "very close" to existing work.
    ranked = [result("note", 0.50, source="mine"), result("a", 1.30)]
    assert idea_verdict(ranked) == "new"


def test_idea_verdict_with_no_results_is_new():
    assert idea_verdict([]) == "new"
