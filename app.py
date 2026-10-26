"""
Designer Lens: a vector database of the designers I like.

Every time something is added, the app immediately searches the library and
tells me how the new thing connects to what is already there.

Run:  python app.py
Needs chroma_store/ (python build_db.py). The explanations use Groq if
GROQ_API_KEY is in .env; without it the app still shows the ranked matches.
"""

import csv
import json
import os
import re
import sys
import textwrap
import unicodedata
import uuid
from datetime import date, datetime

from dotenv import load_dotenv

import fetch_wikipedia as wiki_tools
from build_db import RAW_DIR, get_collection, upsert_designer

# ---------------------------------------------------------------------------
# 1. Settings
# ---------------------------------------------------------------------------

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
# Two of my own ideas: the same idea reworded scored 0.81, two unrelated
# ideas 1.05.
SAME_IDEA = 0.90

MODEL = "openai/gpt-oss-20b"
DISCIPLINES = {"a": "architecture", "i": "interior", "g": "graphic",
               "p": "product", "o": "other"}

load_dotenv()
collection = get_collection()


# ---------------------------------------------------------------------------
# 2. Small helpers
# ---------------------------------------------------------------------------

class Tee:
    """Copy everything the app prints into a log file as well, so a session
    can be reviewed later (and quoted in the README / prompt log)."""

    def __init__(self, stream, path):
        self.stream = stream
        self.file = open(path, "a", encoding="utf-8")

    def write(self, text):
        self.stream.write(text)
        self.file.write(text)
        return len(text)

    def flush(self):
        self.stream.flush()
        self.file.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def ask(prompt=""):
    """input() that also records what was typed in the session log."""
    print(prompt, end="", flush=True)  # through Tee, so the log shows it too
    answer = input()
    if isinstance(sys.stdout, Tee):
        sys.stdout.file.write(answer + "\n")
    return answer


def show(text, indent=""):
    for para in str(text).split("\n"):
        print(textwrap.fill(para, width=88, initial_indent=indent,
                            subsequent_indent=indent) if para.strip() else "")


def slug(name):
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-") or "unnamed"


def body(document):
    """Stored text is 'Designer - Section: text'. Return just the text."""
    return document.split(": ", 1)[-1]


def load_name_list():
    """designers.csv maps English and Chinese names to one designer id, so
    '安藤忠雄', 'Tadao Ando' and 'tadao ando' all mean the same person, and a
    firm like 'OMA' (an alias from the original spreadsheet) resolves to
    Rem Koolhaas."""
    with open("designers.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    by_id = {r["id"]: r for r in rows}
    lookup = {}
    for r in rows:
        target = by_id.get(r["merged_into"]) or r
        aliases = [a for a in r.get("aliases", "").split(";") if a.strip()]
        for name in [r["name_en"], r["name_zh"]] + aliases:
            if name.strip():
                lookup[name.strip().lower()] = target
    return lookup


NAMES = load_name_list()


def find_designer(name):
    """Return {id, name_en, name_zh, discipline, wiki_title} for a typed name."""
    row = NAMES.get(name.strip().lower())
    if row:
        return dict(row)
    return {"id": slug(name), "name_en": name.strip(), "name_zh": "",
            "discipline": "", "wiki_title": name.strip()}


def in_library(designer_id):
    return bool(collection.get(where={"designer_id": designer_id}, limit=1)["ids"])


def names_mentioned(record, exclude=""):
    """Designers in the library whose names appear in this designer's text."""
    metas = collection.get(where={"source": "wikipedia"}, include=["metadatas"])["metadatas"]
    names = {m["name_en"] for m in metas} - {exclude}
    text = " ".join(s["text"] for s in record["sections"])
    found = [n for n in names if re.search(r"\b" + re.escape(n) + r"\b", text)]
    return sorted(found, key=text.find)


def ask_discipline():
    choice = ask("Discipline? [a]rchitecture [i]nterior [g]raphic [p]roduct "
                   "[o]ther: ").strip().lower()[:1]
    return DISCIPLINES.get(choice, "other")


# ---------------------------------------------------------------------------
# 3. Retrieval: rank DESIGNERS, not chunks
# ---------------------------------------------------------------------------
# Step 5 showed one designer with many chunks (Paula Scher) can fill the whole
# top 5. So we pull more chunks, group them by designer, and keep each
# designer's best match.

def similar_designers(texts, exclude=(), discipline=None, section=None,
                      per_text=10, top=4):
    filters = [{"designer_id": {"$nin": list(exclude) + ["me"]}}]
    if discipline:
        filters.append({"discipline": discipline})
    if section:
        filters.append({"section": section})
    where = filters[0] if len(filters) == 1 else {"$and": filters}
    res = collection.query(query_texts=texts, n_results=per_text, where=where)

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


def print_ranking(ranked):
    for r in ranked:
        d, doc, meta, _ = r["hits"][0]
        print(f"  {r['score']:.3f}  {r['name']}"
              f"  ({r['discipline'] or 'note'}) [{meta['section'][:40]}]")
        show(body(doc)[:220] + "...", indent="           ")


# ---------------------------------------------------------------------------
# 4. Language model (optional)
# ---------------------------------------------------------------------------

SYSTEM = (
    "You are a design research assistant for a design student. You only use "
    "the excerpts you are given, which come from Wikipedia or from the "
    "student's own notes. Name the designer and the project the excerpt "
    "mentions. Never add facts that are not in the excerpts, even if you know "
    "them. If an excerpt is only loosely related, say so in one short sentence "
    "instead of inventing a connection. Be concrete and brief. Plain text, no "
    "markdown headings."
)


def ask_llm(prompt):
    """Returns the model's answer, or None if there is no key or the call
    fails, so the app keeps working offline."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    try:
        from groq import Groq
        reply = Groq(api_key=key).chat.completions.create(
            model=MODEL, temperature=0.4,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": prompt}])
        return reply.choices[0].message.content.strip()
    except Exception as err:  # network, quota, bad key...
        print(f"  (language model unavailable: {err.__class__.__name__})")
        return None


def excerpts(ranked, per_designer=2):
    """Format the retrieved chunks for the prompt."""
    out = []
    for r in ranked:
        for dist, doc, meta, query in r["hits"][:per_designer]:
            out.append(f"[{r['name']} | {meta['section']} | distance {dist:.2f}]\n"
                       f"{body(doc)}")
    return "\n\n".join(out)


# ---------------------------------------------------------------------------
# 5. The four actions
# ---------------------------------------------------------------------------

def add_designer():
    name = ask("Designer name (English or Chinese): ").strip()
    if not name:
        return
    who = find_designer(name)
    if in_library(who["id"]):
        print(f"{who['name_en']} is already in the library.")
        return
    if who["wiki_title"] == "-":
        print("This designer is marked as having no English Wikipedia article.")
        print("Use option 2 to add your own note about them instead.")
        return
    if not who["discipline"]:
        who["discipline"] = ask_discipline()

    print("Looking on Wikipedia...")
    wiki = wiki_tools.wikipediaapi.Wikipedia(
        user_agent=wiki_tools.USER_AGENT, language="en",
        extract_format=wiki_tools.wikipediaapi.ExtractFormat.WIKI)
    status, page, intro, _ = wiki_tools.fetch_one(wiki, who, [])
    if not page:
        print("No English Wikipedia article found. Use option 2 to add a note instead.")
        return

    # A person checks the match: names collide (we met an actress, a Go player
    # and the Yellow Sea while building the starting library).
    show(f"Found: {page.title}\n{intro[:300]}...", indent="  ")
    if ask("Is this the right person? (y/n): ").strip().lower() != "y":
        print("Not added.")
        return

    sections = [{"section": "Summary", "text": intro}]
    sections += wiki_tools.collect_sections(page.sections)
    record = {"id": who["id"], "name_en": who["name_en"], "name_zh": who["name_zh"],
              "discipline": who["discipline"], "status": status,
              "wiki_title": page.title, "url": page.fullurl, "sections": sections}
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(os.path.join(RAW_DIR, who["id"] + ".json"), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=1)  # survives a rebuild

    n = upsert_designer(collection, record)
    print(f"Added {n} chunks. Library now holds {collection.count()} chunks.\n")

    # Compare Summary to Summary. Using every chunk made Noguchi "closest" to
    # Ikko Tanaka, Kusama and Gehry only because all four had big museum
    # exhibitions. The Summary says what kind of designer someone is.
    summary = collection.get(where={"$and": [{"designer_id": who["id"]},
                                             {"section": "Summary"}]})["documents"]
    ranked = similar_designers(summary, exclude=[who["id"]], section="Summary",
                               per_text=8, top=3)
    print(f"Closest designers to {who['name_en']} (comparing their summaries):")
    print_ranking(ranked)

    # Similar is not the same as connected. Perriand worked with Le Corbusier
    # for ten years, but their summaries aren't alike. An exact name search
    # finds that kind of link.
    mentioned = names_mentioned(record, exclude=who["name_en"])
    if mentioned:
        print(f"\nTheir article mentions designers already in your library: "
              f"{', '.join(mentioned)}")
    links = ""
    if mentioned:
        links = (f"\n{who['name_en']}'s Wikipedia article mentions these designers "
                 f"by name: {', '.join(mentioned)}. If one of the designers below "
                 f"is among them, use that real connection (look for it in "
                 f"{who['name_en']}'s summary).\n")

    answer = ask_llm(
        f"{who['name_en']} was just added to the library. Here is their summary:"
        f"\n{body(summary[0])}\n{links}\nThese are the closest designers already in the "
        f"library. For each, write 1-2 sentences on what they really share with "
        f"{who['name_en']} as designers (materials, approach, scale, ideas), "
        f"using only the text. If it is only a surface similarity such as "
        f"nationality or fame, say so.\n\n{excerpts(ranked, per_designer=1)}")
    if answer:
        print("\nWhat they share:")
        show(answer, indent="  ")


def add_note():
    print("Describe something you saw or learned: a building, a poster, a detail.")
    text = ask("> ").strip()
    if not text:
        return
    name = ask("Which designer is it about? (Enter to skip): ").strip()
    who = find_designer(name) if name else None
    if who and not who["discipline"] and not in_library(who["id"]):
        who["discipline"] = ask_discipline()

    # Search first, then save, so the note doesn't find itself.
    ranked = similar_designers([text], top=3)
    meta = {"designer_id": who["id"] if who else "unassigned",
            "name_en": who["name_en"] if who else "Your note",
            "name_zh": (who or {}).get("name_zh", ""),
            "discipline": (who or {}).get("discipline", ""),
            "section": "My note", "source": "mine", "kind": "note",
            "url": "", "added": date.today().isoformat()}
    document = f"{who['name_en']} - My note: {text}" if who else f"My note: {text}"
    note_id = f"note-{uuid.uuid4().hex[:8]}"  # unique, so add() never collides
    collection.add(ids=[note_id], documents=[document],
                   metadatas=[meta])
    print(f"Saved ({note_id}). It is searchable right away.\n")

    print("This connects to:")
    print_ranking(ranked)
    answer = ask_llm(
        f"The student just wrote this note: \"{text}\"\n"
        + (f"(It is about {who['name_en']}.)\n" if who else "")
        + "Here are the closest passages already in their library. In 2-4 "
          "sentences, tell them which connection is most worth following up "
          "and why. Mention any that are only loosely related.\n\n"
        + excerpts(ranked))
    if answer:
        print()
        show(answer, indent="  ")


def add_idea():
    print("Describe your own design idea in a few sentences.")
    text = ask("> ").strip()
    if not text:
        return
    ranked = similar_designers([text], top=3)
    idea_id = f"idea-{uuid.uuid4().hex[:8]}"
    collection.add(ids=[idea_id], documents=[f"My idea: {text}"],
                   metadatas=[{"designer_id": "me", "name_en": "Me", "name_zh": "",
                               "discipline": "", "section": "My idea",
                               "source": "mine", "kind": "idea", "url": "",
                               "added": date.today().isoformat()}])
    print(f"Saved to your ideas ({idea_id}).\n")

    # Your earlier ideas: a separate search, only among your ideas.
    earlier = collection.query(query_texts=[text], n_results=2,
                               where={"$and": [{"designer_id": "me"},
                                               {"kind": "idea"}]})
    for i, d in zip(earlier["ids"][0], earlier["distances"][0]):
        if i != idea_id and d < SAME_IDEA:
            print(f"Heads up: close to an idea you saved before ({i}, distance {d:.2f}).")

    print("Closest existing work:")
    print_ranking(ranked)
    # Retrieval finds the candidates; reading decides the overlap. Distance
    # alone can't: Heatherwick's Vessel (really related to a staircase idea)
    # scored 1.22, while an unrelated Sagmeister show scored 1.16 against
    # another idea. So the model gives the verdict, and the distance rule is
    # only a fallback when there is no model.
    answer = ask_llm(
        f"The student's design idea: \"{text}\"\n\nBelow is the closest "
        f"existing work in their library, one passage per designer. Start with "
        f"one line: 'Verdict: very close' or 'Verdict: related' or 'Verdict: "
        f"new', judged from what the passages describe, not from the distances. "
        f"Then, for each passage, one sentence on what (if anything) it has in "
        f"common with the idea. Only where the overlap is real, suggest one way "
        f"the idea could differ more. If nothing overlaps much, name the passage "
        f"that is the most useful reference anyway.\n\n"
        f"{excerpts(ranked, per_designer=1)}")
    if answer:
        print()
        show(answer, indent="  ")
        return
    published = [r["score"] for r in ranked if r["hits"][0][2]["source"] == "wikipedia"]
    best = min(published) if published else 9
    print("\n  (No language model: rough verdict from distance only.)")
    if best < IDEA_VERY_CLOSE:
        print("  -> Very close to existing work. Look at it before you go further.")
    elif best < IDEA_RELATED:
        print("  -> Related work exists; worth knowing how yours differs.")
    else:
        print("  -> Nothing obviously close in your library.")


def ask_question():
    print("Describe a design problem, in your own words.")
    question = ask("> ").strip()
    if not question:
        return
    d = ask("Only one discipline? [a/i/g/p/o, Enter for all]: ").strip().lower()[:1]
    ranked = similar_designers([question], discipline=DISCIPLINES.get(d), top=6)
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
    if not ranked:
        print(f"Nothing in the library is closer than {RELATED}. "
              "Try describing it differently, or add notes on designers you know.")
        return

    print("\nDesigners who dealt with something similar:")
    print_ranking(ranked)
    answer = ask_llm(
        f"The student typed: \"{question}\"\nIt may be a problem, an effect "
        f"they want, or a way of making things they want examples of.\n\n"
        f"Format:\nLooking for: <one line, in your own plain words, saying what "
        f"kind of examples would help them>\n"
        f"Then ONE short paragraph per designer, in the order given: the "
        f"designer's name, then 2 sentences on how their work relates, naming "
        f"the project. Passages from the section 'My note' are the student's "
        f"own notes: call them 'your note' and don't treat them as a "
        f"designer's project.\n"
        f"Then, once at the very end: 'What you could borrow:' and two short "
        f"bullet points.\n\n{excerpts(ranked)}")
    if answer:
        print("\nBrief:")
        show(answer, indent="  ")


def show_library():
    data = collection.get(include=["metadatas"])
    designers, notes, ideas = {}, [], []
    for i, m in zip(data["ids"], data["metadatas"]):
        if m.get("kind") == "idea":
            ideas.append(i)
        elif m.get("source") == "mine":
            notes.append((i, m))
        else:
            designers.setdefault(m.get("discipline", "other"), set()).add(m["name_en"])
    print(f"{collection.count()} chunks in total")
    for disc, names in sorted(designers.items()):
        print(f"  {disc:13} {len(names):3} designers")
    print(f"  your notes:   {len(notes):3}")
    print(f"  your ideas:   {len(ideas):3}")
    for i, m in notes[-5:]:
        print(f"    {m.get('added', '')} {m['name_en']} ({i})")


def delete_mine():
    """Only your own notes and ideas can be deleted; Wikipedia chunks are
    rebuilt from data/raw by build_db.py."""
    data = collection.get(where={"source": "mine"})
    items = sorted(zip(data["ids"], data["documents"], data["metadatas"]),
                   key=lambda x: x[2].get("added", ""))
    if not items:
        print("You haven't added any notes or ideas yet.")
        return
    for n, (i, doc, meta) in enumerate(items, 1):
        print(f"  {n:2}. [{meta.get('kind')}] {meta.get('added', '')}  {body(doc)[:60]}")
    choice = ask("Number to delete (Enter to cancel): ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(items):
        return
    item_id = items[int(choice) - 1][0]
    if ask(f"Delete {item_id}? (y/n): ").strip().lower() == "y":
        collection.delete(ids=[item_id])
        print(f"Deleted. Library now holds {collection.count()} chunks.")


# ---------------------------------------------------------------------------
# 6. Menu
# ---------------------------------------------------------------------------

MENU = """
--- Designer Lens ---
1. Add a designer (from Wikipedia)
2. Add a note (something you saw or learned)
3. Add my own idea (and check it against existing work)
4. Ask: who has dealt with a problem like mine?
5. Show the library
6. Delete one of my notes or ideas
7. Quit
"""


def main():
    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", datetime.now().strftime("session-%Y%m%d-%H%M%S.txt"))
    sys.stdout = Tee(sys.stdout, log_path)
    print(f"(This session is being saved to {log_path})")
    if collection.count() == 0:
        print("The library is empty. Run: python fetch_wikipedia.py && python build_db.py")
        return
    if not os.getenv("GROQ_API_KEY"):
        print("(No GROQ_API_KEY in .env: showing matches without explanations.)")
    actions = {"1": add_designer, "2": add_note, "3": add_idea,
               "4": ask_question, "5": show_library, "6": delete_mine}
    while True:
        print(MENU)
        choice = ask("Choose an option: ").strip()
        if choice == "7":
            break
        if choice in actions:
            print()
            actions[choice]()
        else:
            print("Please type a number from 1 to 7.")


if __name__ == "__main__":
    main()
