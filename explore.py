"""
Step 5: run some queries and actually look at what comes back.

Run:  python explore.py                      (the built-in list below)
      python explore.py "query one" "query two"  (your own queries)
Prints to the screen and also saves everything to explore_results.txt.
"""

import sys

import chromadb

QUERIES = [
    # The two test queries planned for the README (no shared key words).
    "using mud and the hands of local villagers instead of concrete",
    "a home that poor families finish and enlarge themselves over the years",
    # More probes across disciplines.
    "temporary shelters for people who lost everything in a disaster",
    "a church where sunlight itself becomes the main material",
    "a building that wears its pipes and machinery on the outside",
    "a roof that looks like a tent made of cables",
    "posters made only from big bold letters",
    "wallpaper full of plants and birds",
    "a skyscraper that twists as it rises",
    # Should match nothing: shows what a "bad" distance looks like.
    "how do I fix a flat bicycle tire",
]

if len(sys.argv) > 1:
    QUERIES = sys.argv[1:]

lines = []


def say(text=""):
    print(text)
    lines.append(text)


client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_collection("designers")
say(f"Collection holds {collection.count()} chunks\n")

# Look at the raw shape once (lists of lists, one inner list per query).
raw = collection.query(query_texts=[QUERIES[0]], n_results=2)
say("Raw result object for the first query, n_results=2:")
say(str({k: v for k, v in raw.items() if k in ("ids", "distances", "metadatas")}))
say()

for q in QUERIES:
    res = collection.query(query_texts=[q], n_results=5)
    say(f"=== {q}")
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0],
                               res["distances"][0]):
        say(f"  {dist:.3f}  {meta['name_en']:<26} [{meta['section'][:28]}]")
        say(f"         {doc.split(': ', 1)[-1][:150]}")
    say()

with open("explore_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("Saved to explore_results.txt")
