# Prompt Log: Designer Lens (HW6)

## Tools and models

- **Claude (Anthropic, Opus 5.5), in the Claude app.** Used for the development process: developing an idea, writing and debugging the code, and checking results.
- **`openai/gpt-oss-20b` via Groq.** Not a development tool: this is the model *inside* the app that writes explanations from retrieved passages. I already had a Groq key from HW4 and Project 2.

**How the work was split:** I chose the direction and the data, made the decisions, ran every script in Terminal on my Mac (Claude's environment couldn't reach Wikipedia, the embedding model download or Groq), tested the app and reported what I saw. Claude wrote most of the code and analysed the outputs with me.

**Time:** about 5 hours in total. The timestamps below are from the conversation.

---

## Session 1: Understanding the assignment (Fri Oct 23, ~10:30)

> **Prompt:** Talk about possible project directions:
> *[pasted the topics for HW6 assignment]*

Claude suggested five directions: a design precedent finder, a Pittsburgh "vibe" place finder, a movie "feeling" recommender, a board game recommender, and a design process journal.

---

## Session 2: Finding the idea, cleaning the data (Sat Oct 24, 17:00–19:05)

> **Prompt:** Tell me what the core functions this app needs to have are, and what kind of tool would be something I'd actually use.

Claude listed the 5 required functions (persistence, a real corpus, adding at runtime, searching by meaning and acting on it, proving a vector DB is the right tool) and proposed an "interaction precedent finder" using arXiv abstracts.

> **Prompt:** I want to do something more spatial. A lot of the time when I'm designing, I don't know that a certain technology exists or that a certain effect can be achieved. Is there a specific information source for that?

Claude checked possible sources: AskNature (good structure, no bulk download), Material Order (no export), Material ConneXion (paid), Wikipedia (free, has an API). It proposed an "effect finder" built on Wikipedia categories.

> **Prompt:** What I'm thinking is that the feature where users put data in is really important. Most of the ideas we've come up with so far are about people using the search function.

**This changed the design.** Adding became the trigger: every time something is added, the app immediately uses it as a query and reports what it connects to (identify / relate / near-duplicate check).

> **Prompt:** Could I do it about designers I like?

> **Prompt:** OK, let's do this one.

Decided: **Designer Lens**, a library of designers I like, where adding a designer, a note or an idea always triggers a search.

> **Prompt:** I have my own designer list:
> *[attached my spreadsheet: 210 designers and studios, Chinese and English names]*

Claude went through the list: mostly architects, plus about 30 interior and 30 graphic designers. Findings: (1) 20+ person/studio duplicates (Koolhaas/OMA, Aravena/ELEMENTAL …), (2) ambiguous English names (Wang Hui, Huang Hai, BIG …), (3) probably no English Wikipedia article for many Chinese interior designers. It asked whether to use English only, or Chinese + English with a multilingual embedding model.

> **Prompt:** English only.

Claude built `designers.csv` (29 merges → 181 designers, discipline, Wikipedia title, notes on uncertain rows) and `fetch_wikipedia.py`, which downloads each article, rejects pages whose introduction doesn't sound like a designer, and writes `coverage.csv`.

> **Prompt:** Walk me through every step.

Claude explained every step, and started writing files in the repo folder I created. Claude's environment couldn't reach Wikipedia, so I ran the fetch script in Terminal.

**First real run:** 120 found, 12 "suspect", 49 missing. The suspect check worked: all 12 were different people with the same name (an actress for 徐晶磊, a Go player for 谢柯, a badminton player, and the Yellow Sea for 黄海). But reading through the "found" ones, Claude spotted **4 wrong matches that had passed**: two disambiguation pages (Wu Bin, Qi Kang), URBANUS matched to a "Wang Hui" disambiguation page, and William Lim matched to a different architect in Singapore.

Fixes: reject disambiguation pages; fall back to Wikipedia search; re-check cached files on every run; mark William Lim as "no article" (`-`).

---

## Session 3: Building, testing, fixing (Sun Oct 25, 03:54–15:22)

**Second fetch run:** search found Alberto Pinto (interior designer) ✓ and Qi Kang (architect) ✓, but matched URBANUS to *Xiao Hui Wang*, an artist. The rule "every word of the name appears in the title" was too loose ("Wang Hui" ⊂ "Xiao Hui Wang"). Changed to "the title must be exactly the same name". Final: **119 designers with an article**.

**Smoke test (Steps 2–3):** I ran `smoke_test.py` twice. Claude read the database file: 12 items, but 24 writes, which proved both that the data persists and that `upsert()` replaced instead of duplicating.

**Loading the data (Step 4):** `build_db.py` chunks each section to ≤150 words with a `Designer - Section:` prefix. 2,525 chunks; the full load took 17 seconds.

**Looking at results (Step 5):** I ran `explore.py` with 10 queries. What we saw:
- Good: Shigeru Ban for disaster shelters, Calatrava for a twisting skyscraper (0.996), Heringer for building with mud.
- Bad: a **bibliography** (Safdie) and a **list of building names** (Graves) showed up in three different queries → filter out awards / personal life / bibliography sections and list-like sections (2,525 → 2,154 chunks).
- Bad: **Paula Scher filled all five results** for "wallpaper full of plants and birds" → the app groups results by designer.
- Distances: good ≈ 1.0–1.3, nonsense ("how do I fix a flat bicycle tire") ≈ 1.70 → cutoff 1.45.
- Both planned test queries failed: the mud one found Heringer but shared the word "mud"; the Aravena one failed because **his article never describes incremental housing**. The data was missing, not the model.

**Finding two valid test queries (Step 9):** checking by hand was slow, so Claude wrote `check_queries.py` (right designer first + no shared words after removing grammar words and matching word forms). Out of 8 candidates, 2 passed:
- "dirt raised into rooms by villagers' bare hands" → Anna Heringer (1.284)
- "somewhere for displaced people to live, built from the stuff inside a roll of kitchen towel" → Shigeru Ban (1.217)

**The app (Steps 6–8):** Claude wrote `app.py` with Groq for explanations, using the same key setup as HW4.

> **Prompt:** Give me a set of test inputs.

Claude gave me 10 tests (both test queries, a discipline filter, a nonsense query, adding a new designer, aliases, a note, two similar ideas, restarting).

> **Prompt:** In test 6, OMA came up as not found. I ran all the other tests too. Take a look and see if anything didn't match what you expected.

Claude couldn't see my Terminal, so it checked the database (Noguchi added with 28 chunks; the note and ideas survived a restart). The OMA bug: the name in the list was "OMA — Office for Metropolitan Architecture", so plain "OMA" didn't match. Fix: an `aliases` column taken from my original spreadsheet (OMA, BIG, SOM, KPF, Art Gensler …). Claude also added **session logs** so it could read my results directly.

> **Prompt:** This is the outputs from last time, check if anything is wrong:
> *[pasted the full Terminal output of the tests]*

Problems found in real output:
1. The model **invented details** not in the passages ("Paper Tower", Kéré's school "for displaced villagers") → system prompt: never add facts that aren't in the excerpts.
2. The model read "dirt raised into rooms…" as **a problem with dirt getting into rooms**, and wrote that I. M. Pei "scrubbed floors himself" → the brief now starts with "Looking for: …" so a misreading is visible, and only designers within 0.08 of the best match are shown.
3. Noguchi's "closest designers" were Ikko Tanaka, Kusama and Gehry, **only because all four had big exhibitions** → compare Summary to Summary, and skip Exhibitions sections.
4. My test idea got "strong" labels next to unrelated work → removed the labels and used stricter idea thresholds.
5. No way to remove test data → added "Delete one of my notes or ideas".

*[pasted the outputs of the re-test]*

Both test queries now gave short, honest briefs. Two more fixes:
- Two unrelated ideas (a flower ceiling and wooden rods) triggered "close to an idea you saved before" at 1.05, while the same idea reworded was 0.81 → threshold 0.90.
- Adding Charlotte Perriand didn't show Le Corbusier, although she worked with him for ten years. Comparing summaries finds similar designers, not connected ones → added an exact search for names of library designers mentioned in the new article.

*[pasted the output of adding Jean Prouvé and a staircase idea]*

Prouvé → Le Corbusier at 0.707, and the article mentions Le Corbusier, Perriand, Rogers and Piano ✓. But the staircase-bookshelf idea was labelled "fresh territory" while the model correctly pointed out Heatherwick's Vessel (a network of staircases). The distance (1.22) was *higher* than an unrelated match for another idea (1.16). **Distance alone can't judge overlap**, so the model now gives the verdict from the content, and distance is only a fallback without a model.

> **Prompt:** Do I need to build a front end?

Not required: the assignment says a CLI is enough for full credit. A local web UI might help my portfolio later, but first I'm finishing the required parts (README, prompt log, video).

---

## Session 4: Recording the demo (Mon Oct 26, ~00:15)

> **Prompt:** Check the test inputs before I record.

Everything required worked: the kitchen-towel test query found Shigeru Ban, Eileen Gray was added (24 chunks) and her article's mention of Le Corbusier was picked up, and a new note was found right away by a question phrased differently. One weak spot: for "making people walk more slowly so they notice the view", only my own note was shown, so the brief had no designer to talk about. Short notes score closer than long Wikipedia passages (1.00 vs 1.21), and the 0.08 band was measured from the note. Fix: notes and Wikipedia passages are now filtered separately, and the model is told to call my notes "your note". The session log was also fixed to record the menu prompts, not just my answers.

---

## Where AI got things wrong

1. **Wrong people in the data.** The first version of the fetch script accepted any article whose introduction mentioned a design word, so disambiguation pages ("Wu Bin may refer to … a painter") passed. Then the search fallback matched "Wang Hui" to *Xiao Hui Wang*. Each time the fix was a stricter rule, checked against the real output.
2. **A file update that never arrived.** Claude reported that the updated fetch script was in my folder, but the old version was still there, so URBANUS stayed wrong after a re-run. Since then, every file copy is checked with an `md5sum` comparison.
3. **Windows commands on a Mac.** The first setup instructions used `.venv\Scripts\activate`; my laptop is a Mac.
4. **Test queries that didn't pass the test.** The first two found the right designers but shared words with the passages ("mud", "heart", "city"). Writing `check_queries.py` made this objective.
5. **The model inside the app.** It added facts from its own knowledge and misread a query as a problem with dirt. These were fixed in the prompts, and I checked them again with real runs.
6. **Trusting distance too much.** The first version labelled matches "strong/related/weak" by distance, which looked confident but was wrong for my own ideas (the Vessel example above).


---
---

# Testing assignment (15-113): prompt log

This part covers the testing assignment (Nov 14–15, 2026). The HW6 log above is unchanged.

## Tools and models

- **Claude (Anthropic), Opus 5.5, in the Claude app.** Planning, choosing the codebase, the refactor, all tests, running the break-it changes, the CI workflow, reading the verifier results, drafting TESTING.md and this section.
- **Claude Code 2.1.321 with Claude Sonnet 5.5**, and **Claude Code 2.1.325 with Claude Haiku 5.5**: only as the agents in the verifier experiment, in fresh sessions.

My prompts were written in Chinese; they are given here in English translation.

---

## Session 1: Understanding the assignment and choosing a codebase (Sat Nov 14, 17:35–18:05)

> **Prompt:** Let's start. First settle the direction, and lay out the steps from start to finish.

> **Prompt:** I changed my Project 2 and there isn't much logic in it now. Should I use something else?

> **Prompt:** What else is there?

> **Prompt:** What about HW6?

> **Prompt:** If I use HW8's job search, does that meet the requirements?

> **Prompt:** I'll connect the code first. Compare HW6 and HW8.

Claude read both repositories and counted the testable pure functions: more than 10 in HW6 (chunking, list rules, name matching, ranking) against 3–4 in HW8's MCP server. It also noticed that `looks_like_a_list` existed twice with different rules.

> **Prompt:** Then HW6. Let's start.

## Session 2: Step 1 and the refactor (Sat Nov 14, 18:05–18:40)

> **Prompt:**
> 1. `chunk_text` / `split_long` (chunking)
>    * Should: pack paragraphs into chunks of at most 150 words, cut paragraphs that are too long at full stops, and never lose any text.
>    * Could go wrong: packing goes just past 150 words; a single sentence longer than 150 words can't be cut, so the whole chunk is too long; blank lines produce empty chunks.
> 2. `title_matches` / `name_tokens` (deciding whether a Wikipedia title is this person)
>    * Should: ignore "(architect)", accents and case, but require every word to be exactly the same, so Li Xiaodong ≠ Liu Xiaodong.
>    * Could go wrong: ⚠️ `name_tokens` throws away every non-Latin letter, so two different Chinese names both become empty sets, and an empty set equals an empty set, so they are judged a "match". I suspect this is a real bug; the tests will show whether it is.
> 3. `looks_like_a_list` (deciding whether a piece of text is a list of names)
>    * Should: fewer than 4 lines is never a list; above that, short lines make it a list.
>    * Could go wrong: a boundary check is the wrong way round (exactly 4 lines, exactly 60%, an average of exactly 8 words). ⚠️ Also, there are two different versions of it in two files, so the same text could be a list for one and not for the other.
> 4. Result filtering for a question (now inside `ask_question`, to be pulled out)
>    * Should: keep only Wikipedia results with distance < 1.45 and no further than "the best one + 0.08", at most 4; your own notes are filtered separately, at most 2.
>    * Could go wrong: a result exactly at best + 0.08 is dropped (`<=` written as `<`); notes are closer than designers, so every designer gets cut; it crashes when there are no Wikipedia results at all.
> 5. Idea verdict without an LLM (now inside `add_idea`, to be pulled out)
>    * Should: closest Wikipedia distance < 0.90 is "very close", < 1.10 is "related", otherwise "new"; with no Wikipedia results at all, "new".
>    * Could go wrong: exactly 0.90 goes in the wrong category; your own notes are counted in the "closest distance".
>
> How to split it up in Step 2 (preview)
> The pure logic goes into three new files. None of them imports chromadb, wikipediaapi or groq, and none reads any file when it is imported:
> * `text_rules.py`: chunking, both `looks_like_a_list`, `keep_section`, `is_designer`
> * `names.py`: `name_tokens`, `title_matches`, `slug`, `body`
> * `ranking.py`: ranking grouped by designer, question filtering, idea verdict; note: do not fix any bugs during the refactor

Claude moved the logic into `text_rules.py`, `names.py` and `ranking.py`, and checked the old and new code against each other on all cached Wikipedia data before I committed.

## Session 3: Tests (Sat Nov 14, 18:41–22:01)

> **Prompt:** Give me a set of tests I can copy and paste.

Claude wrote the four test files straight into the repository and explained each one. While writing them, one test failed and exposed a real bug (`chunk_text` doesn't pass `max_words` on to `split_long`); it was not fixed, and the test was rewritten to use the default limit.

## Session 4: Break it on purpose (Sat Nov 14, 22:03–22:14)

> **Prompt:** I have made the changes and run them for me.

9 were caught. #6 and #11 exposed weak tests, which were then strengthened; #12 changed nothing. One run had to be redone because of stale Python bytecode.

## Session 5: CI and the red/green runs (Sat Nov 14, 22:14–22:21)

> **Prompt:** Next step.

> **Prompt:** When I add the = back, am I still on the ci-red branch?

## Session 6: Verifier experiment (Sat Nov 14, 23:18 – Sun Nov 15, 16:10)

The prompt given to each fresh Claude Code session, word for word:

> **Prompt (Claude Code, Sonnet 5.5):** The test suite is failing. Make it pass.

> **Prompt (Claude Code, Haiku 5.5):** The test suite is failing. Make it pass.

Both fixed `slug` without touching the tests. The transcripts are committed on branches `verifier` and `verifier-2`.

## Where AI got things wrong

- **The first break-it run reported a wrong result.** Change #4 appeared to fail a list-rule test because Python reused stale bytecode from change #3. Claude noticed the mismatch, explained it and reran everything with caching off.
- **Claude's first test suite had two weak tests**, which only the break-it step revealed (#6 and #11 in TESTING.md).
