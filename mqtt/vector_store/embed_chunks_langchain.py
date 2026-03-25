import os
import glob
import shutil
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from mqtt.config import DATASET_ADAPTER, EMBED_MODEL

CHUNK_BASE_DIR = os.path.join("data", "chunks")
SNAPSHOT_CHUNK_DIR = os.path.join(CHUNK_BASE_DIR, "snapshots")
EVENT_CHUNK_DIR = os.path.join(CHUNK_BASE_DIR, "events")

COLLECTION_NAME = f"{DATASET_ADAPTER}_telemetry_chunks"
PERSIST_DIR = os.path.join("data", f"chroma_db_{DATASET_ADAPTER}")

RESET_DB_EACH_RUN = True


def reset_vector_db():
    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)
        print(f"🗑️ Deleted old vector DB: {PERSIST_DIR}")


def load_chunk_files(folder_path: str):
    documents = []
    source_type = os.path.basename(folder_path)

    files = sorted(glob.glob(os.path.join(folder_path, "*.txt")))

    for i, file_path in enumerate(files):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read().strip()

        if not text:
            continue

        metadata = {
            "chunk_id": f"{source_type}_{i:04d}",
            "source_file": os.path.basename(file_path),
            "source_type": source_type,
            "adapter": DATASET_ADAPTER
        }

        first_line = text.splitlines()[0].strip() if text.splitlines() else ""
        if first_line:
            metadata["preview"] = first_line

        documents.append(
            Document(
                page_content=text,
                metadata=metadata
            )
        )

    return documents


def main():
    if RESET_DB_EACH_RUN:
        reset_vector_db()

    print(f"Dataset adapter: {DATASET_ADAPTER}")
    print("Loading chunk files...")

    snapshot_docs = load_chunk_files(SNAPSHOT_CHUNK_DIR) if os.path.exists(SNAPSHOT_CHUNK_DIR) else []
    event_docs = load_chunk_files(EVENT_CHUNK_DIR) if os.path.exists(EVENT_CHUNK_DIR) else []

    all_docs = snapshot_docs + event_docs

    print(f"Snapshot chunks found: {len(snapshot_docs)}")
    print(f"Event chunks found: {len(event_docs)}")
    print(f"Total chunks to ingest: {len(all_docs)}")

    if not all_docs:
        print("⚠️ No chunk files found. Run chunk_builder first.")
        return

    print("Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cpu"}
    )

    print("Creating fresh ChromaDB collection...")
    _vectorstore = Chroma.from_documents(
        documents=all_docs,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=PERSIST_DIR
    )

    print("\n✅ Clean ingestion complete")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Persist directory: {PERSIST_DIR}")
    print(f"Total documents stored: {len(all_docs)}")


if __name__ == "__main__":
    main()