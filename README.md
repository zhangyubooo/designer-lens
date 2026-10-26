# Designer Lens

A command-line app that keeps a searchable library of the designers I follow (mostly architects, plus graphic, interior and product designers) and connects anything new I add to what is already there.

When I design, I often don't know that someone has already solved a similar problem, or what a technique is called. I also wanted adding things to be the core of the app, not just searching, so every time I add a designer, a note or one of my own ideas, the app immediately searches the library and tells me what it connects to.

---

## What it does

```
--- Designer Lens ---
1. Add a designer (from Wikipedia)
2. Add a note (something you saw or learned)
3. Add my own idea (and check it against existing work)
4. Ask: who has dealt with a problem like mine?
5. Show the library
6. Delete one of my notes or ideas
7. Quit
```

| Action | What happens after retrieval |
|---|---|
| **1. Add a designer** | Finds their English Wikipedia article (you confirm it's the right person), chunks and stores it, then compares their **Summary** with every other designer's Summary and explains what they really share. It also lists designers in the library that their article **mentions by name** (e.g. Jean Prouvé → Le Corbusier, Charlotte Perriand). |
| **2. Add a note** | Stores something I saw or learned, optionally tied to a designer. This is how designers with no Wikipedia article get into the library. The app shows which designers the note connects to and which connection is worth following up. |
| **3. Add my own idea** | Checks the idea against existing work. The language model gives a verdict (*very close / related / new*) from what the passages actually describe, and for real overlaps suggests how the idea could differ. It also warns me if I saved almost the same idea before. |
| **4. Ask** | Takes a problem in my own words, keeps only the designers whose best passage is about as close as the top one, and writes a brief: what I'm looking for, how each designer's project relates, and what I could borrow. Optional filter by discipline. |

Every session is also saved to `logs/` (not committed), which made it easy to review real results while tuning the app.

---

## What is in the database

**Where the data comes from.** I started from my own list of 210 designers and studios, compiled from 18 screenshots into a spreadsheet with Chinese and English names. That list is `designers.csv` (it is only names, so it is committed). For each designer the app downloads their English Wikipedia article with the `wikipedia-api` package.

**Cleaning the list.**
- 29 person/studio pairs were merged (OMA → Rem Koolhaas, MAD → Ma Yansong, Atelier Deshaus → Liu Yichun …), leaving **181 designers**. Studio names and abbreviations still work as input through an `aliases` column (`OMA`, `BIG`, `SOM`, `KPF` …).
- Name collisions were a real problem. The first lookup returned an actress, a Go player, a badminton player and the Yellow Sea (黄海, Huang Hai). `fetch_wikipedia.py` therefore rejects any article whose introduction doesn't read like a designer's, rejects disambiguation pages, and when the exact title fails it uses Wikipedia search, accepting only a title with exactly the same name (so *Liu Xiaodong* can't stand in for *Li Xiaodong*).
- Result: **119 of 181** designers have an English article. Coverage is very uneven: architecture 91/108, graphic 17/31, **interior 7/33**, product 1/6, other 3/3. English Wikipedia mostly covers Western and Japanese architects, and most of the Chinese interior designers on my list have no article. That is exactly what option 2 (notes) is for.

**What one item is.** One item is a chunk of **at most ~150 words** from one section of an article. Chroma's default embedding model only reads about 256 word pieces and silently ignores the rest, so whole articles would be useless. Chunks are cut at paragraph ends where possible, and long paragraphs at sentence ends. Each chunk starts with `Designer - Section:` (for example `Tadao Ando - Early life: ...`), so a section called "Later work" still says whose work it is.

**What I left out** (decided after looking at real search results):
- Sections about life and fame rather than design: awards, honours, recognition, personal life, death, bibliography, publications, exhibitions. A Moshe Safdie bibliography was showing up for "temporary shelters", and Noguchi "matched" Gehry only because both had big museum exhibitions.
- List-like sections such as `Hanselmann House, Fort Wayne, Indiana, 1968` one per line (a section counts as a list when 60% or more of its lines are under 25 words). Quotations are kept, because a designer's own words are useful even when the lines are short.
- This took the library from 2,525 to about 2,150 chunks.

**Size now:** **2,196 chunks from 122 designers** (the 119 above plus Noguchi, Perriand and Prouvé, which I added in the app).

**Metadata on each chunk:** `designer_id`, `name_en`, `name_zh`, `discipline` (architecture / interior / graphic / product / other), `section`, `source` (`wikipedia` or `mine`), `url`. My notes and ideas also have `kind` (`note` / `idea`) and `added` (date).

**IDs.** Wikipedia chunks get deterministic ids (`tadao-ando-003`) and are written with `upsert()`, so rebuilding never creates duplicates. My notes and ideas get random ids (`note-1a2b3c4d`) and are written with `add()`, so two notes can never collide. (Chroma silently ignores `add()` with an id that already exists.)

---

## Adding and searching

- **Add:** options 1–3. Anything added is searchable right away. Notes are searched *before* they are saved, so a new note doesn't just find itself.
- **Search:** option 4. Option 1 and option 3 also search, using the new item as the query.
- **Delete:** option 6 removes one of my notes or ideas. Wikipedia chunks are rebuilt from the downloaded cache.

Some design choices behind the search:
- **Rank designers, not chunks.** At first, "wallpaper full of plants and birds" returned five chunks of Paula Scher and no William Morris. Now the app pulls more chunks, groups them by designer, and keeps each designer's best match.
- **Distance.** Chroma's default distance: lower is more similar. In my data, good matches were 1.0–1.3 and a nonsense query ("how do I fix a flat bicycle tire") was about 1.7, so nothing above **1.45** is shown, and the app says there is no good match instead. But unrelated architecture also lands around 1.15–1.35, so a distance alone can't say "strong match". In Ask, the app only keeps designers within **0.08** of the best result.
- **My notes are ranked separately.** Short notes sit closer to a question than long Wikipedia passages (my staircase note scored 1.00, the best designer 1.21), so if the 0.08 band were measured from the note, every designer would be cut. Notes and Wikipedia passages are filtered separately and then shown together.
- **Retrieval finds candidates; reading decides.** For my own ideas, distance couldn't tell overlap apart: Heatherwick's Vessel (really related to a staircase idea) scored 1.22, while an unrelated Sagmeister exhibition scored 1.16 against a different idea. So the language model gives the verdict, and distance thresholds are only a fallback when there is no model.
- **Similar is not the same as connected.** Comparing summaries didn't put Le Corbusier near Charlotte Perriand, even though she worked with him for ten years. An exact name search over the new designer's article catches that kind of link, so the app shows both.

---

## The two test queries

Both were checked with `check_queries.py`: the expected designer must come first, and the query must share no important word with the passage it finds. Grammar words are ignored, and simple word forms are matched, so *turns* and *turning* count as the same word.

| Query | Retrieved (rank 1) | Distance |
|---|---|---|
| `dirt raised into rooms by villagers' bare hands` | **Anna Heringer**, *Projects*: "DESI … the first **mud-built** structure in Bangladesh … called on the services of local students and **craftsmen** …" | 1.284 |
| `somewhere for displaced people to live, built from the stuff inside a roll of kitchen towel` | **Shigeru Ban**, *Design approach*: "Ban is most famous now for his innovative work with **paper and cardboard tubing** as a building material …" | 1.217 |

**Why keyword search would fail:** my queries describe things the way I'd say them (dirt, bare hands, the inside of a kitchen-towel roll), while Wikipedia names them technically (*mud-built*, *craftsmen*, *cardboard tubing*), so there are no shared words to match.

What didn't work, and why:
- The first versions found the right designers but shared words with the passage ("mud", "construction", "heart", "city"), so they failed the test.
- "A home that poor families finish and enlarge themselves" never found Alejandro Aravena. His article doesn't describe incremental housing in its text at all; it only appears in a book title. That was a gap in the data, not a fault of the model.
- Very indirect phrasings ("a tiny drawing of an organ replacing a verb in a catchphrase", for Milton Glaser's I ❤ NY) found nothing useful.

---

## How to get the data and build the database

The raw Wikipedia text (`data/`) and the database (`chroma_store/`) are not in the repo. They are rebuilt like this:

```bash
python fetch_wikipedia.py      # downloads ~119 articles to data/raw/, writes coverage.csv (a few minutes)
python build_db.py --limit 50  # optional: time the first 50 chunks
python build_db.py             # chunks everything and loads it into ChromaDB (~20 s on my laptop)
```

`fetch_wikipedia.py` reuses what it already downloaded and re-checks it on every run. `python fetch_wikipedia.py --refresh` downloads everything again. A full rebuild only replaces Wikipedia chunks; notes and ideas (`source = mine`) are kept.

---

## Tools

- **Vector database:** [ChromaDB](https://docs.trychroma.com/) 1.5.9, `PersistentClient(path="./chroma_store")`, collection `designers`.
- **Embedding model:** Chroma's default, **all-MiniLM-L6-v2** (English only, so the app uses English Wikipedia). **It downloads automatically the first time anything is embedded** (a few tens of MB, once).
- **Language model (optional):** `openai/gpt-oss-20b` through [Groq](https://console.groq.com/), temperature 0.4. It is only given the retrieved passages and is told not to add facts that aren't in them. Without a key, the app still works and shows the ranked matches.
- **Wikipedia:** [`wikipedia-api`](https://pypi.org/project/Wikipedia-API/) 0.16.

---

## How to run

Python 3.10 or newer (I used 3.13 on macOS).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python fetch_wikipedia.py
python build_db.py

# optional, for the explanations:
echo "GROQ_API_KEY=your_key_here" > .env

python app.py
```

`.env` is in `.gitignore` and never committed.

## Files

| File | Purpose |
|---|---|
| `app.py` | The app (CLI menu) |
| `fetch_wikipedia.py` | Finds and downloads each designer's article, checks it's the right person, writes `coverage.csv` |
| `build_db.py` | Filters sections, chunks them, loads them into ChromaDB |
| `designers.csv` | My designer list: Chinese/English names, discipline, Wikipedia title, merges, aliases |
| `coverage.csv` | Which designers have an article, and how many chunks |
| `smoke_test.py` | Assignment Steps 2–3: proves the database persists between runs |
| `explore.py` | Step 5: runs queries and prints raw results and distances |
| `check_queries.py` | Step 9: checks the test queries (right designer first, no shared words) |
| `prompt_log.md` | How I built this with AI, step by step |

---

## How I used AI

I built this with **Claude** (Anthropic) in the Claude app. I chose the idea, the direction (spatial design, adding as the core feature, designers I like) and the designer list, and made the decisions along the way. Claude wrote most of the code. I ran every script on my Mac, tested the app with real inputs, and sent the results back. Several design changes came from problems we saw in real output (wrong people with the same name, bibliographies in the results, one designer filling the top 5, the model misreading a query). The full process, with my prompts, is in [`prompt_log.md`](prompt_log.md).

Inside the app, `openai/gpt-oss-20b` (via Groq) writes the explanations from the retrieved passages.

## Citations

- Text in the database comes from **English Wikipedia** articles, used under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Each chunk stores the URL of its article.
- ChromaDB documentation: https://docs.trychroma.com/
- Wikipedia-API (Python package): https://github.com/martin-majlis/Wikipedia-API
- Sentence Transformers model all-MiniLM-L6-v2: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
