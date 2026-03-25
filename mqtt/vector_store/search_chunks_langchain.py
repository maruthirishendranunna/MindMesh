import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from mqtt.config import DATASET_ADAPTER, EMBED_MODEL

COLLECTION_NAME = f"{DATASET_ADAPTER}_telemetry_chunks"
PERSIST_DIR = os.path.join("data", f"chroma_db_{DATASET_ADAPTER}")
TOP_K = 5
FINAL_TOP_K = 3
PREVIEW_CHARS = 800


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


def classify_query(question: str):
    q = question.lower()

    if "accident" in q or "crash" in q:
        return "accident"
    if "leader" in q:
        return "leader"
    if "fastest" in q:
        return "fastest"
    if "winner" in q or "won" in q:
        return "winner"
    if "lap changed" in q or "lap change" in q:
        return "lap_changed"
    return "general"


def rerank_docs(question: str, docs):
    query_type = classify_query(question)

    keyword_map = {
        "accident": ["accident detected"],
        "leader": ["race leader changed", "race leader is", "leader is"],
        "fastest": ["fastest driver changed", "fastest driver is"],
        "winner": ["winner is", "race finished", "winner decided"],
        "lap_changed": ["lap changed"],
    }

    keywords = keyword_map.get(query_type, [])

    scored = []
    for doc in docs:
        text = doc.page_content.lower()
        score = 0

        for kw in keywords:
            if kw in text:
                score += 5

        # Small boost if preview also contains keyword
        preview = str(doc.metadata.get("preview", "")).lower()
        for kw in keywords:
            if kw in preview:
                score += 3

        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    reranked_docs = [doc for _, doc in scored]

    return reranked_docs[:FINAL_TOP_K]


def search_chunks(question: str, k: int = TOP_K):
    vectorstore = load_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    docs = retriever.invoke(question)
    return rerank_docs(question, docs)


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