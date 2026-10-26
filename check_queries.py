"""
Step 9 helper: does each test query pass the assignment's test?

  1. The expected designer comes back first, and
  2. the query shares no important words with the chunk that was found.

Run:  python check_queries.py
Results are printed and saved to check_results.txt.
"""

import re

import chromadb

# (query, designer_id we expect to come back first)
CANDIDATES = [
    ("a place for kids, shaped from dirt by neighbours, with nothing from a factory", "anna-heringer"),
    ("dirt raised into rooms by villagers' bare hands", "anna-heringer"),
    ("a tiny drawing of an organ replacing a verb in a catchphrase for visitors", "milton-glaser"),
    ("the doodle that made a bankrupt metropolis lovable again", "milton-glaser"),
    ("somewhere for displaced people to live, built from the stuff inside a roll of kitchen towel", "shigeru-ban"),
    ("emergency rooms made from rolled-up packaging after the ground shook", "shigeru-ban"),
    ("apartments stacked like a wrung-out cloth", "santiago-calatrava"),
    ("a tower of flats that corkscrews toward the sky", "santiago-calatrava"),
]

# Grammar words don't count as "sharing a word".
STOP = set("""a an the and or but of in on at to for from by with without as is are
was were be been it its this that these those their there they them he she his her
who whom which what when where how than then so not no nothing into onto over under
after before about like up down out off again very can could would should will just
made make""".split())


def stem(word):
    """Rough stemming so 'turns' and 'turning' count as the same word."""
    for suffix in ("ings", "ing", "ies", "ied", "ed", "es", "s", "ly"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def content_stems(text):
    return {stem(w) for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP}


lines = []


def say(text=""):
    print(text)
    lines.append(text)


collection = chromadb.PersistentClient(path="./chroma_store").get_collection("designers")

for query, expected in CANDIDATES:
    res = collection.query(query_texts=[query], n_results=10)
    metas, docs, dists = res["metadatas"][0], res["documents"][0], res["distances"][0]

    rank = next((i for i, m in enumerate(metas) if m["designer_id"] == expected), None)
    say(f"=== {query}")
    for m, d in list(zip(metas, dists))[:3]:
        say(f"  {d:.3f}  {m['name_en']}  [{m['section'][:40]}]")

    if rank is None:
        say(f"  FAIL: {expected} not in the top 10\n")
        continue

    # Compare with the text after the "Designer - Section:" prefix we added.
    found_text = docs[rank].split(": ", 1)[-1]
    shared = content_stems(query) & content_stems(found_text)
    verdict = "PASS" if rank == 0 and not shared else "FAIL"
    say(f"  {verdict}: {expected} at rank {rank + 1}, distance {dists[rank]:.3f}, "
        f"shared words: {sorted(shared) if shared else 'none'}")
    say(f"  found: {found_text[:220]}")
    say()

with open("check_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("Saved to check_results.txt")
