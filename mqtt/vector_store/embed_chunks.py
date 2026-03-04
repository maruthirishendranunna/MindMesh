import os
import glob
import chromadb
from sentence_transformers import SentenceTransformer

# ==========================
# CONFIG
# ==========================
CHUNK_DIRS = [
    os.path.join("data", "chunks", "snapshots"),
    os.path.join("data", "chunks", "events")
]

CHROMA_DIR = os.path.join("data", "chroma_db")
COLLECTION_NAME = "f1_telemetry_chunks"

# ==========================
# LOAD MODEL
# ==========================
print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

# ==========================
# INIT CHROMA (Persistent)
# ==========================
client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = client.get_or_create_collection(name=COLLECTION_NAME)

# ==========================
# PROCESS CHUNKS
# ==========================
documents = []
embeddings = []
metadatas = []
ids = []

chunk_counter = 0

for chunk_dir in CHUNK_DIRS:
    if not os.path.exists(chunk_dir):
        print(f" Missing folder: {chunk_dir}")
        continue

    files = sorted(glob.glob(os.path.join(chunk_dir, "*.txt")))
    print(f" Found {len(files)} files in {chunk_dir}")

    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read().strip()

        if not text:
            continue

        chunk_id = f"chunk_{chunk_counter:06d}"
        chunk_counter += 1

        embedding = model.encode(text).tolist()

        documents.append(text)
        embeddings.append(embedding)
        metadatas.append({
            "source_file": os.path.basename(file_path),
            "source_type": os.path.basename(chunk_dir)
        })
        ids.append(chunk_id)

print(f"\n Total chunks processed: {len(documents)}")

if documents:
    collection.add(
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )

    # No client.persist() needed with PersistentClient
    print(f" Stored embeddings in ChromaDB at: {CHROMA_DIR}")
    print(f" Collection: {COLLECTION_NAME}")
else:
    print(" No chunks found. Check your chunk folders and .txt files.")