"""text_rules: deciding which Wikipedia sections are worth storing.

A 'list' is a section like 'Works' with one building per line. It gives the
embedding model names but no ideas, so it is dropped.

There are two different list rules, from two files:
  looks_like_a_list      (build_db.py)        short lines (< 25 words) make up >= 60%
  looks_like_a_list_avg  (fetch_wikipedia.py) average line is < 8 words
Both say: fewer than 4 lines is never a list.
"""

from text_rules import (is_designer, keep_section, looks_like_a_list,
                        looks_like_a_list_avg)

PROSE_LINE = " ".join(["word"] * 40)   # one long line, like a Wikipedia paragraph


def lines(*word_counts):
    return "\n".join(" ".join(["w"] * n) for n in word_counts)


# ---- both rules: the 4-line minimum ----

def test_three_short_lines_are_not_a_list():
    assert looks_like_a_list(lines(2, 2, 2)) is False
    assert looks_like_a_list_avg(lines(2, 2, 2)) is False


def test_four_short_lines_are_a_list():
    assert looks_like_a_list(lines(2, 2, 2, 2)) is True
    assert looks_like_a_list_avg(lines(2, 2, 2, 2)) is True


def test_blank_lines_do_not_count_as_lines():
    # 3 real lines + blanks is still only 3 lines.
    assert looks_like_a_list(lines(2, 2) + "\n\n\n" + lines(2)) is False


def test_prose_paragraphs_are_not_a_list():
    text = "\n".join([PROSE_LINE] * 5)
    assert looks_like_a_list(text) is False
    assert looks_like_a_list_avg(text) is False


# ---- build_db rule: share of short lines ----

def test_exactly_60_percent_short_lines_is_a_list():
    # 3 short of 5 = 60%: the rule is >= 0.6, so this counts.
    assert looks_like_a_list(lines(3, 3, 3, 40, 40)) is True


def test_40_percent_short_lines_is_not_a_list():
    assert looks_like_a_list(lines(3, 3, 40, 40, 40)) is False


def test_a_25_word_line_is_not_short():
    # "short" means fewer than 25 words; 24 is short, 25 is not.
    assert looks_like_a_list(lines(24, 24, 24, 24)) is True
    assert looks_like_a_list(lines(25, 25, 25, 25)) is False


# ---- fetch_wikipedia rule: average words per line ----

def test_average_of_exactly_8_words_is_not_a_list():
    # The rule is avg < 8, so 8.0 is not a list.
    assert looks_like_a_list_avg(lines(8, 8, 8, 8)) is False


def test_average_just_under_8_words_is_a_list():
    assert looks_like_a_list_avg(lines(8, 8, 8, 7)) is True   # 7.75


# ---- keep_section ----

def section(title, text):
    return {"section": title, "text": text}


def test_awards_and_life_sections_are_dropped():
    for title in ["Awards", "Honours", "Personal life", "Bibliography", "Exhibitions"]:
        assert keep_section(section(title, PROSE_LINE)) is False, title


def test_only_the_last_part_of_a_nested_title_is_checked():
    # 'publications' is a skip word, but here it is only the parent.
    assert keep_section(section("Works and publications > Fashion", PROSE_LINE)) is True
    assert keep_section(section("Career > Awards", PROSE_LINE)) is False


def test_quotes_are_kept_even_when_they_look_like_a_list():
    short_lines = lines(6, 6, 6, 6, 6)
    assert keep_section(section("Works", short_lines)) is False
    assert keep_section(section("Quotations", short_lines)) is True


def test_design_prose_is_kept():
    assert keep_section(section("Design approach", PROSE_LINE)) is True


# ---- is_designer ----

def test_designer_intro_is_recognised():
    assert is_designer("Tadao Ando is a Japanese self-taught architect.") is True
    assert is_designer("Paula Scher is an American Graphic Designer.") is True   # any case


def test_disambiguation_page_is_rejected_even_with_design_words():
    assert is_designer("Wu Bin may refer to: Wu Bin (painter), Wu Bin (architect)") is False


def test_intro_about_someone_else_is_rejected():
    assert is_designer("Huang Hai is a Chinese professional footballer.") is False
