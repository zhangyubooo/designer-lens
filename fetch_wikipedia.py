"""
Step 1 of Designer Lens: download the English Wikipedia article for every
designer in designers.csv, cache it to data/raw/, and report coverage.

Run:  python fetch_wikipedia.py            (reuses anything already downloaded)
      python fetch_wikipedia.py --refresh  (downloads everything again)
Output:
  data/raw/<id>.json   cached sections for each designer that has an article
  coverage.csv         one row per designer: found / found_by_search / missing
"""

import csv
import json
import math
import os
import re
import sys
import time
import unicodedata

import wikipediaapi

CSV_PATH = "designers.csv"
RAW_DIR = os.path.join("data", "raw")
COVERAGE_PATH = "coverage.csv"

# Wikipedia asks every script to identify itself.
USER_AGENT = "DesignerLens/0.1 (CMU 15-113 student project; github.com/zhangyubooo)"

# Sections that never help answer "how does this designer think?"
SKIP_TITLES = {
    "references", "notes", "footnotes", "citations", "sources",
    "see also", "external links", "further reading", "bibliography",
    "publications", "filmography", "gallery",
}

# If the intro mentions none of these, we probably matched a different person.
DESIGN_WORDS = (
    "architect", "design", "artist", "typeface", "typograph",
    "interior", "studio", "firm", "practice", "fashion", "painter",
)

# Extra word added to a Wikipedia search so 'Huang Hai' finds the designer,
# not the Yellow Sea.
SEARCH_HINT = {
    "architecture": "architect",
    "interior": "interior designer",
    "graphic": "graphic designer",
    "product": "designer",
}

# Chroma's default model reads ~256 word pieces (~190 English words).
# We plan chunks of at most ~150 words, so this estimates the chunk count.
WORDS_PER_CHUNK = 150
MIN_WORDS = 30  # shorter sections are too thin to be worth storing


def load_designers():
    """Return (entities, aliases). An entity is a row that was not merged
    into another row; aliases maps entity id -> rows folded into it."""
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    entities = [r for r in rows if not r["merged_into"]]
    aliases = {}
    for r in rows:
        if r["merged_into"]:
            aliases.setdefault(r["merged_into"], []).append(r)
    return entities, aliases


def looks_like_a_list(text):
    """Sections like 'Works' are often just one building name per line.
    Those give the embedding model almost nothing to work with."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 4:
        return False
    avg_words = sum(len(ln.split()) for ln in lines) / len(lines)
    return avg_words < 8


def collect_sections(sections, path=""):
    """Walk the nested section tree and keep sections with real prose."""
    kept = []
    for s in sections:
        title = f"{path} > {s.title}" if path else s.title
        if s.title.strip().lower() in SKIP_TITLES:
            continue
        text = s.text.strip()
        if len(text.split()) >= MIN_WORDS and not looks_like_a_list(text):
            kept.append({"section": title, "text": text})
        kept.extend(collect_sections(s.sections, title))
    return kept


def is_designer(intro):
    """Does this intro describe a designer? Disambiguation pages ('Wu Bin may
    refer to: ... a painter ...') mention design words too, so reject them."""
    text = intro.lower()
    if "may refer to" in text or "is the name of" in text:
        return False
    return any(word in text for word in DESIGN_WORDS)


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


def search_for_designer(wiki, name, discipline):
    """When the exact title is missing or belongs to someone else, ask
    Wikipedia's own search, e.g. 'Li Xiaodong architect'. A result only counts
    if its title is the same name and its intro reads like a designer's."""
    query = f"{name} {SEARCH_HINT.get(discipline, '')}".strip()
    for title in wiki.search(query, limit=5).pages:
        if not title_matches(title, name):
            continue
        page = wiki.page(title)
        if page.exists() and is_designer(page.summary):
            return page
    return None


def fetch_one(wiki, entity, alias_rows):
    """Returns (status, page, intro, rejected_title).
    1. the entity's own wiki_title
    2. titles of rows merged into it (a person with no article whose firm has one)
    3. Wikipedia search, for the entity and then its aliases
    A page whose intro doesn't read like a designer is rejected (wrong person)."""
    # wiki_title "-" in designers.csv means "no article; don't guess".
    rows = [r for r in [entity] + alias_rows if r["wiki_title"] != "-"]
    rejected = ""
    for r in rows:
        if not r["wiki_title"]:
            continue
        page = wiki.page(r["wiki_title"])
        if not page.exists():
            continue
        if is_designer(page.summary):
            return "found", page, page.summary.strip(), ""
        rejected = rejected or page.title
    for r in rows:
        page = search_for_designer(wiki, r["name_en"], entity["discipline"])
        if page:
            return "found_by_search", page, page.summary.strip(), rejected
    return "missing", None, "", rejected


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    entities, aliases = load_designers()
    wiki = wikipediaapi.Wikipedia(
        user_agent=USER_AGENT,
        language="en",
        extract_format=wikipediaapi.ExtractFormat.WIKI,  # plain text, no HTML
    )

    refresh = "--refresh" in sys.argv
    report = []
    for i, e in enumerate(entities, 1):
        cache_path = os.path.join(RAW_DIR, e["id"] + ".json")

        cached = None
        if os.path.exists(cache_path) and not refresh:
            with open(cache_path, encoding="utf-8") as f:
                cached = json.load(f)
            first = cached["sections"][0]["text"] if cached["sections"] else ""
            # Re-check old downloads, so a wrong match is fixed on the next run.
            if e["wiki_title"] == "-" or not is_designer(first):
                cached = None
            elif cached.get("status") == "found_by_search":
                names = [e["name_en"]] + [a["name_en"] for a in aliases.get(e["id"], [])]
                if not any(title_matches(cached["wiki_title"], n) for n in names):
                    cached = None

        if cached:
            # Already downloaded on an earlier run: reuse it.
            status, rejected = cached.get("status", "found"), ""
            title, sections = cached["wiki_title"], cached["sections"]
            intro = sections[0]["text"] if sections else ""
        else:
            status, page, intro, rejected = fetch_one(
                wiki, e, aliases.get(e["id"], []))
            title, sections = (page.title if page else ""), []
            if page:
                sections = [{"section": "Summary", "text": intro}] if intro else []
                sections += collect_sections(page.sections)
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "id": e["id"],
                        "name_en": e["name_en"],
                        "name_zh": e["name_zh"],
                        "discipline": e["discipline"],
                        "status": status,
                        "wiki_title": page.title,
                        "url": page.fullurl,
                        "sections": sections,
                    }, f, ensure_ascii=False, indent=1)
            elif os.path.exists(cache_path):
                os.remove(cache_path)  # an earlier run cached the wrong person
            time.sleep(0.1)  # be polite to Wikipedia

        words = sum(len(s["text"].split()) for s in sections)
        chunks = sum(math.ceil(len(s["text"].split()) / WORDS_PER_CHUNK)
                     for s in sections)
        report.append({
            "id": e["id"],
            "name_zh": e["name_zh"],
            "name_en": e["name_en"],
            "discipline": e["discipline"],
            "status": status,
            "matched_title": title,
            "rejected_title": rejected,
            "sections": len(sections),
            "words": words,
            "est_chunks": chunks,
            "intro": intro[:160].replace("\n", " "),
        })
        print(f"[{i:3}/{len(entities)}] {status:15} {e['name_en']}"
              + (f"  -> {title}" if status == "found_by_search" else "")
              + (f"  (~{chunks} chunks)" if chunks else ""))

    with open(COVERAGE_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(report[0].keys()))
        w.writeheader()
        w.writerows(report)

    # ----- summary -----
    has_article = ("found", "found_by_search")
    print("\n===== Coverage =====")
    for status in ("found", "found_by_search", "missing"):
        n = sum(1 for r in report if r["status"] == status)
        print(f"{status:15} {n}")
    print("\nBy discipline (has article / total):")
    for d in sorted({r["discipline"] for r in report}):
        group = [r for r in report if r["discipline"] == d]
        found = sum(1 for r in group if r["status"] in has_article)
        print(f"  {d:13} {found:3} / {len(group)}")
    print(f"\nEstimated chunks in total: {sum(r['est_chunks'] for r in report)}")
    print("\nFound by search (check these are the right people):")
    for r in report:
        if r["status"] == "found_by_search":
            print(f"  {r['name_zh']} / {r['name_en']} -> {r['matched_title']}")
    print(f"\nFull table written to {COVERAGE_PATH}")


if __name__ == "__main__":
    main()
