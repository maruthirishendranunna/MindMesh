import chromadb

CHROMA_DIR = "data/chroma_db"
COLLECTION_NAME = "f1_telemetry_chunks"

client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = client.get_collection(name=COLLECTION_NAME)

print(" Collection count:", collection.count())

queries = [
    "Hamilton speed",
    "current lap of Verstappen",
    "fastest driver",
    "race leader",
    "accident happened"
]

for q in queries:
    print("\n==============================")
    print("QUERY:", q)
    results = collection.query(
        query_texts=[q],
        n_results=3
    )

    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        print("\n--- Match", i+1, "---")
        print("Source:", meta.get("source_type"), "| File:", meta.get("source_file"))
        print(doc[:1500])  # show first 400 chars only