"""
Assignment Steps 2-3: prove ChromaDB installs, writes to disk, and survives
a restart. Uses a dozen hand-written items, not the real data.

Run it twice:
  1st run: count goes 0 -> 12 (and Chroma downloads its embedding model once)
  2nd run: count is already 12 before anything is added -> persistence works
"""

import chromadb

print("chromadb version:", chromadb.__version__)

# PersistentClient writes to ./chroma_store on disk.
# chromadb.Client() would keep everything in memory and lose it on exit.
client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_or_create_collection(name="smoke_test")

print("count BEFORE adding:", collection.count())

items = [
    ("rammed-earth", "A school built from clay walls packed by hand with the help of the whole village."),
    ("light-slit", "A concrete chapel where a single cut in the wall lets daylight form a cross."),
    ("paper-tubes", "Emergency shelters made from cardboard tubes after an earthquake."),
    ("half-house", "Social housing where families receive half a home and finish the rest themselves."),
    ("glass-house", "A transparent box of steel and glass sitting lightly on a meadow."),
    ("bilbao", "A museum wrapped in curving sheets of titanium beside a river."),
    ("poster-type", "A poster made only from large, tightly kerned black letters on white."),
    ("i-love-ny", "A logo that replaces a word with a red heart and became a city's symbol."),
    ("pompidou", "A building that shows its pipes, ducts and escalators on the outside, painted in bright colors."),
    ("tatami", "A small room whose proportions come from the size of woven floor mats."),
    ("tensile-roof", "A stadium roof of cables and translucent panels that looks like a spider's web."),
    ("wallpaper", "Hand-printed wallpaper with dense patterns of leaves, vines and birds."),
]

# upsert() = insert, or overwrite if the id already exists.
# With add(), a second run would reuse the same ids and Chroma would silently
# ignore them, which is exactly the trap the assignment warns about.
collection.upsert(
    ids=[item_id for item_id, _ in items],
    documents=[text for _, text in items],
    metadatas=[{"source": "smoke_test"} for _ in items],
)

print("count AFTER adding: ", collection.count())

# A query that shares no important words with the item it should find.
query = "temporary homes for people who lost everything in a disaster"
results = collection.query(query_texts=[query], n_results=3)

print("\nRaw result object (note: lists of lists, one inner list per query):")
print(results)

print(f"\nTop 3 for: {query!r}")
for doc_id, doc, dist in zip(results["ids"][0], results["documents"][0],
                             results["distances"][0]):
    print(f"  {dist:.3f}  {doc_id:13} {doc}")
print("(lower distance = more similar)")
