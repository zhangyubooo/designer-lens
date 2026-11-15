"""text_rules.chunk_text / split_long: cutting Wikipedia text into chunks.

Why it matters: Chroma's embedding model silently ignores everything past
~256 word pieces, so a chunk that is too long loses its ending without any
error. A chunk that drops words loses them for good.

Most tests use a small max_words (10) so the numbers are easy to count.
"""

from text_rules import MAX_WORDS, chunk_text, split_long


def words(n, word="w"):
    """A sentence of exactly n words, ending in a full stop."""
    return " ".join([word] * (n - 1) + [word + "."])


def test_short_paragraphs_are_packed_into_one_chunk():
    text = words(3) + "\n" + words(4)
    assert chunk_text(text, max_words=10) == [words(3) + " " + words(4)]


def test_exactly_at_the_limit_stays_together():
    # 5 + 5 = 10 words, limit 10: allowed, so one chunk, not two.
    text = words(5) + "\n" + words(5)
    assert len(chunk_text(text, max_words=10)) == 1


def test_one_word_over_the_limit_starts_a_new_chunk():
    # 5 + 6 = 11 words, limit 10: must split.
    text = words(5) + "\n" + words(6)
    assert chunk_text(text, max_words=10) == [words(5), words(6)]


def test_long_paragraph_is_cut_at_sentence_ends():
    # One paragraph, three sentences of 60 words, default limit 150:
    # 60 + 60 fit, the third goes to a new chunk. No sentence is cut in half.
    # (Uses the default limit on purpose: chunk_text does not pass a custom
    # max_words on to split_long. Found while writing tests; see TESTING.md.)
    paragraph = " ".join([words(60, "a"), words(60, "b"), words(60, "c")])
    chunks = chunk_text(paragraph)
    assert chunks == [words(60, "a") + " " + words(60, "b"), words(60, "c")]
    assert all(c.endswith(".") for c in chunks)


def test_no_words_are_lost_or_added():
    paragraphs = [words(n, f"p{n}") for n in (3, 12, 7, 1, 9, 15, 2)]
    text = "\n".join(paragraphs)
    chunks = chunk_text(text, max_words=10)
    assert " ".join(chunks).split() == text.split()


def test_no_chunk_goes_over_the_limit_when_sentences_are_short():
    text = "\n".join(words(n) for n in (3, 8, 2, 9, 4, 4, 7, 1, 6))
    for chunk in chunk_text(text, max_words=10):
        assert len(chunk.split()) <= 10


def test_blank_lines_do_not_make_empty_chunks():
    text = "\n\n" + words(3) + "\n   \n\n" + words(2) + "\n"
    chunks = chunk_text(text, max_words=10)
    assert chunks == [words(3) + " " + words(2)]


def test_empty_text_gives_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("\n \n") == []


def test_split_long_keeps_every_sentence_whole():
    paragraph = " ".join(words(4, x) for x in "abcde")
    pieces = split_long(paragraph, max_words=10)
    assert " ".join(pieces) == paragraph
    assert [len(p.split()) for p in pieces] == [8, 8, 4]


def test_default_limit_is_150_words():
    # build_db.py relies on this number; the README and docstrings say 150.
    assert MAX_WORDS == 150
    text = "\n".join(words(50) for _ in range(4))   # 200 words in 4 paragraphs
    assert [len(c.split()) for c in chunk_text(text)] == [150, 50]
