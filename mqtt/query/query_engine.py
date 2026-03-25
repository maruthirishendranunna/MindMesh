import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from mqtt.config import DATASET_ADAPTER, EMBED_MODEL

# =========================================
# CONFIG
# =========================================

COLLECTION_NAME = f"{DATASET_ADAPTER}_telemetry_chunks"
DB_PATH = os.path.join("data", f"chroma_db_{DATASET_ADAPTER}")
TOP_K = 3
PREVIEW_CHARS = 800


# =========================================
# LOAD EMBEDDINGS
# =========================================

def load_embeddings():
    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cpu"}
    )


# =========================================
# LOAD VECTOR STORE
# =========================================

def load_store():
    embeddings = load_embeddings()

    store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=DB_PATH
    )

    return store


# =========================================
# RUN QUERY
# =========================================

def run_query(question: str):
    store = load_store()

    retriever = store.as_retriever(search_kwargs={"k": TOP_K})
    docs = retriever.invoke(question)

    print("\n" + "=" * 80)
    print(f"QUERY: {question}")
    print("=" * 80)

    if not docs:
        print("No matching chunks found.")
        return

    for i, doc in enumerate(docs, 1):
        print(f"\n📄 MATCH {i}")
        print("-" * 80)

        print("METADATA:")
        print(doc.metadata)

        print("\nCONTENT PREVIEW:")
        print(doc.page_content[:PREVIEW_CHARS])

        if len(doc.page_content) > PREVIEW_CHARS:
            print("\n... [truncated]")

        print("-" * 80)


# =========================================
# MAIN
# =========================================

if __name__ == "__main__":
    print(f"Dataset adapter: {DATASET_ADAPTER}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"DB path: {DB_PATH}")

    while True:
        q = input("\nEnter query (press Enter to exit): ").strip()

        if not q:
            break

        run_query(q)