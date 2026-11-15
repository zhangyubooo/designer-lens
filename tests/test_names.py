"""names: matching Wikipedia titles to designers, and making ids.

title_matches decides whether a Wikipedia page is about the designer we
asked for. A false 'yes' stores the wrong person's text under a designer's
name; a false 'no' drops a designer.
slug turns a name into the id used for files and the database.
"""

import csv
from pathlib import Path

from names import body, slug, title_matches

REPO = Path(__file__).resolve().parent.parent


# ---- title_matches ----

def test_same_name_matches():
    assert title_matches("Tadao Ando", "Tadao Ando") is True


def test_bracketed_note_in_the_title_is_ignored():
    assert title_matches("Qi Kang (architect)", "Qi Kang") is True


def test_accents_and_case_are_ignored():
    assert title_matches("Álvaro Siza", "alvaro siza") is True


def test_one_letter_different_does_not_match():
    assert title_matches("Liu Xiaodong", "Li Xiaodong") is False


def test_extra_word_does_not_match():
    # 'Xiao Hui Wang' contains 'Wang' and 'Hui' but is someone else.
    assert title_matches("Xiao Hui Wang", "Wang Hui") is False


def test_the_bracket_is_only_removed_at_the_end():
    assert title_matches("Kengo Kuma (architect) Associates", "Kengo Kuma") is False


# ---- slug ----

def test_slug_examples():
    assert slug("Tadao Ando") == "tadao-ando"
    assert slug("I. M. Pei") == "i-m-pei"
    assert slug("Álvaro Siza") == "alvaro-siza"
    assert slug("  BIG (Bjarke Ingels Group)  ") == "big-bjarke-ingels-group"


def test_slug_of_nothing_usable_is_unnamed():
    assert slug("") == "unnamed"
    assert slug("!!!") == "unnamed"


def test_different_chinese_names_get_different_ids():
    # A designer can be added by typing a Chinese name that is not in
    # designers.csv. The slug becomes their id in the database, so two
    # different people must not end up with the same id.
    assert slug("王澍") != slug("刘家琨")


def test_slug_reproduces_every_id_in_designers_csv():
    # The ids in designers.csv were made from the English names. If slug
    # changed, a re-added designer would get a new id and be stored twice.
    with open(REPO / "designers.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) > 200
    for row in rows:
        assert slug(row["name_en"]) == row["id"], row["name_en"]


# ---- body ----

def test_body_drops_the_designer_and_section_prefix():
    assert body("Tadao Ando - Design approach: Light and concrete.") == "Light and concrete."


def test_body_keeps_later_colons_in_the_text():
    assert body("Paula Scher - Quotes: She said: less is more.") == "She said: less is more."
