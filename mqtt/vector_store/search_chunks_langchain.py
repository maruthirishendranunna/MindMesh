import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from mqtt.config import DATASET_ADAPTER, EMBED_MODEL
from mqtt.adapters.loader import get_adapter

adapter = get_adapter()

COLLECTION_NAME = f"{DATASET_ADAPTER}_telemetry_chunks"
PERSIST_DIR = os.path.join("data", f"chroma_db_{DATASET_ADAPTER}")

TOP_K = getattr(adapter, "SEARCH_TOP_K", 5)
FINAL_TOP_K = getattr(adapter, "SEARCH_FINAL_TOP_K", 3)
PREVIEW_CHARS = 800


# =========================================
# LOAD VECTOR STORE
# =========================================

def load_vectorstore():
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cpu"}
    )

    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=PERSIST_DIR
    )
    return vectorstore


# =========================================
# QUERY TYPE
# =========================================

def classify_query(question: str):
    return adapter.classify_query(question)


# =========================================
# RERANK
# =========================================

def rerank_docs(question: str, docs):
    query_type = classify_query(question)

    keyword_map = {
        "event": [
            "accident detected",
            "race leader changed",
            "fastest driver changed",
            "winner is",
            "race finished",
            "lap changed",
            "event",
            "alert",
            "fault",
            "abnormal"
        ],
        "comparison": [
            "speed is",
            "rpm is",
            "gear is",
            "fuel level is",
            "pressure is",
            "temperature is",
            "flow rate is",
            "vibration is"
        ],
        "metric": [
            "speed is",
            "rpm is",
            "gear is",
            "fuel level is",
            "pressure is",
            "temperature is",
            "flow rate is",
            "vibration is",
            "status is"
        ],
        "general": []
    }

    keywords = keyword_map.get(query_type, [])

    scored = []
    for doc in docs:
        text = doc.page_content.lower()
        score = 0

        for kw in keywords:
            if kw in text:
                score += 5

        preview = str(doc.metadata.get("preview", "")).lower()
        for kw in keywords:
            if kw in preview:
                score += 3

        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    reranked_docs = [doc for _, doc in scored]

    return reranked_docs[:FINAL_TOP_K]


# =========================================
# SEARCH
# =========================================

def search_chunks(question: str, k: int = TOP_K):
    normalized_question = adapter.normalize_question_text(question)

    vectorstore = load_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    docs = retriever.invoke(normalized_question)

    return rerank_docs(normalized_question, docs)


# =========================================
# PRINT RESULTS
# =========================================

def print_results(question: str, docs):
    print("\n" + "=" * 80)
    print(f"QUERY: {question}")
    print("=" * 80)

    if not docs:
        print("No matching chunks found.")
        return

    for i, doc in enumerate(docs, start=1):
        print(f"\n📄 MATCH {i}")
        print("-" * 80)
        print("METADATA:")
        print(doc.metadata)

        print("\nCHUNK PREVIEW:")
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
    print(f"DB path: {PERSIST_DIR}")

    while True:
        q = input("\nEnter query (press Enter to exit): ").strip()
        if not q:
            break

        results = search_chunks(q)
        print_results(q, results)