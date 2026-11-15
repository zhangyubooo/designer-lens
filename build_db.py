"""
Step 4 of Designer Lens: load the cached Wikipedia sections into ChromaDB.

Run:  python build_db.py --limit 50   (time the first 50 chunks, then stop)
      python build_db.py              (load everything)

Each section is cut into chunks of at most ~150 words, because Chroma's default
embedding model only reads the first ~256 word pieces and silently drops the
rest. Every chunk starts with "Designer - Section:" so a chunk like "Later
work" still says whose later work it is.
"""

import glob
import json
import os
import re
import sys
import time

import chromadb

from text_rules import MAX_WORDS, chunk_text, keep_section

RAW_DIR = os.path.join("data", "raw")
DB_PATH = "./chroma_store"
COLLECTION = "designers"
BATCH = 200  # chunks per upsert call: one big call is much faster than many small ones


def get_collection():
    client = chromadb.PersistentClient(path=DB_PATH)
    return client.get_or_create_collection(name=COLLECTION)


def chunks_for_designer(record):
    """Turn one cached designer file into (ids, documents, metadatas)."""
    ids, docs, metas = [], [], []
    for section in filter(keep_section, record["sections"]):
        for piece in chunk_text(section["text"]):
            n = len(ids)
            ids.append(f"{record['id']}-{n:03d}")  # same id every rebuild
            docs.append(f"{record['name_en']} - {section['section']}: {piece}")
            metas.append({
                "designer_id": record["id"],
                "name_en": record["name_en"],
                "name_zh": record["name_zh"],
                "discipline": record["discipline"],
                "section": section["section"],
                "source": "wikipedia",
                "url": record["url"],
            })
    return ids, docs, metas


def upsert_designer(collection, record):
    """Replace one designer's Wikipedia chunks. Old chunks are deleted first,
    so if an article got shorter, its leftover chunks don't linger."""
    collection.delete(where={"$and": [{"designer_id": record["id"]},
                                      {"source": "wikipedia"}]})
    ids, docs, metas = chunks_for_designer(record)
    for i in range(0, len(ids), BATCH):
        collection.upsert(ids=ids[i:i + BATCH], documents=docs[i:i + BATCH],
                          metadatas=metas[i:i + BATCH])
    return len(ids)


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    records = []
    for path in sorted(glob.glob(os.path.join(RAW_DIR, "*.json"))):
        with open(path, encoding="utf-8") as f:
            records.append(json.load(f))
    if not records:
        sys.exit("No files in data/raw/. Run fetch_wikipedia.py first.")

    # Build every chunk first so we know the total and can stop at --limit.
    all_ids, all_docs, all_metas = [], [], []
    for r in records:
        ids, docs, metas = chunks_for_designer(r)
        all_ids += ids
        all_docs += docs
        all_metas += metas
    total = len(all_ids) if limit is None else min(limit, len(all_ids))
    print(f"{len(records)} designers -> {len(all_ids)} chunks"
          + (f" (loading only the first {total})" if limit else ""))

    collection = get_collection()
    if limit is None:
        # Full load: clear old Wikipedia chunks so nothing stale survives.
        # Chunks the user added themselves (source="mine") are kept.
        collection.delete(where={"source": "wikipedia"})

    start = time.time()
    for i in range(0, total, BATCH):
        j = min(i + BATCH, total)
        collection.upsert(ids=all_ids[i:j], documents=all_docs[i:j],
                          metadatas=all_metas[i:j])
        elapsed = time.time() - start
        print(f"  {j:5}/{total} chunks  {elapsed:6.1f}s")

    elapsed = time.time() - start
    print(f"\nDone: {total} chunks in {elapsed:.1f}s "
          f"({elapsed / max(total, 1) * 1000:.0f} ms per chunk)")
    if limit:
        estimate = elapsed / total * len(all_ids)
        print(f"Estimated time for all {len(all_ids)} chunks: {estimate / 60:.1f} min")
    print(f"Collection '{COLLECTION}' now holds {collection.count()} items.")


if __name__ == "__main__":
    main()
