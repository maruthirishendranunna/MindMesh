import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from mqtt.config import DATASET_ADAPTER, EMBED_MODEL


# =========================================
# CONFIG
# =========================================

TELEMETRY_COLLECTION = f"{DATASET_ADAPTER}_telemetry_chunks"
TELEMETRY_DB = os.path.join("data", f"chroma_db_{DATASET_ADAPTER}")

TOPIC_COLLECTION = f"{DATASET_ADAPTER}_topic_descriptions"
TOPIC_DB = os.path.join("data", f"chroma_topics_{DATASET_ADAPTER}")

TOP_K_TOPIC = 2
TOP_K_TELEMETRY = 3
TOP_K_FALLBACK = 6


# =========================================
# LOAD EMBEDDINGS
# =========================================

def load_embeddings():
    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cpu"}
    )


# =========================================
# LOAD VECTOR STORES
# =========================================

def load_topic_store():
    embeddings = load_embeddings()
    return Chroma(
        collection_name=TOPIC_COLLECTION,
        embedding_function=embeddings,
        persist_directory=TOPIC_DB
    )


def load_telemetry_store():
    embeddings = load_embeddings()
    return Chroma(
        collection_name=TELEMETRY_COLLECTION,
        embedding_function=embeddings,
        persist_directory=TELEMETRY_DB
    )


# =========================================
# QUERY TYPE DETECTION
# =========================================

def classify_query(question: str):
    q = question.lower()

    event_words = [
        "accident", "crash", "winner", "won",
        "leader changed", "fastest changed",
        "lap changed", "event"
    ]

    metric_words = [
        "rpm", "speed", "fuel", "gear",
        "lap", "drs", "circuit", "sector"
    ]

    if any(w in q for w in event_words):
        return "event"

    if any(w in q for w in metric_words):
        return "metric"

    return "general"


# =========================================
# SEARCH TOPICS
# =========================================

def search_topics(question: str):
    store = load_topic_store()
    retriever = store.as_retriever(search_kwargs={"k": TOP_K_TOPIC})
    return retriever.invoke(question)


# =========================================
# BUILD TELEMETRY QUERY
# =========================================

def build_telemetry_query(original_question: str, topic_docs):
    if not topic_docs:
        return original_question

    best_topic = topic_docs[0].metadata.get("topic", "")
    if not best_topic:
        return original_question

    parts = best_topic.split("/")

    # Example:
    # f1/redbull/perez/rpm -> "redbull perez rpm"
    if len(parts) >= 4:
        return " ".join(parts[1:])

    return original_question


# =========================================
# SEARCH TELEMETRY WITH FILTER
# =========================================

def search_telemetry_with_filter(refined_question: str, source_type: str, k: int):
    store = load_telemetry_store()

    retriever = store.as_retriever(
        search_kwargs={
            "k": k,
            "filter": {"source_type": source_type}
        }
    )

    return retriever.invoke(refined_question)


def search_telemetry(question: str, refined_question: str):
    query_type = classify_query(question)

    # Metric queries should prefer snapshot chunks
    if query_type == "metric":
        docs = search_telemetry_with_filter(refined_question, "snapshots", TOP_K_TELEMETRY)
        if docs:
            return docs

        # fallback
        return search_telemetry_with_filter(refined_question, "events", TOP_K_FALLBACK)

    # Event queries should prefer event chunks
    if query_type == "event":
        docs = search_telemetry_with_filter(refined_question, "events", TOP_K_TELEMETRY)
        if docs:
            return docs

        # fallback
        return search_telemetry_with_filter(refined_question, "snapshots", TOP_K_FALLBACK)

    # General queries: try snapshots first, then fallback to events
    docs = search_telemetry_with_filter(refined_question, "snapshots", TOP_K_TELEMETRY)
    if docs:
        return docs

    return search_telemetry_with_filter(refined_question, "events", TOP_K_FALLBACK)


# =========================================
# BUILD CONTEXT
# =========================================

def build_context(original_question: str, refined_question: str, topic_docs, telemetry_docs):
    lines = []

    lines.append(f"USER QUERY: {original_question}")
    lines.append(f"REFINED TELEMETRY QUERY: {refined_question}")
    lines.append("")

    lines.append("=== TOPIC MATCHES ===")
    for i, doc in enumerate(topic_docs, start=1):
        lines.append(f"[Topic Match {i}]")
        lines.append(doc.page_content)
        lines.append("")

    lines.append("=== TELEMETRY MATCHES ===")
    for i, doc in enumerate(telemetry_docs, start=1):
        lines.append(f"[Telemetry Match {i}]")
        lines.append(f"Source Type: {doc.metadata.get('source_type')}")
        lines.append(doc.page_content[:1200])
        lines.append("")

    return "\n".join(lines)


# =========================================
# RUN QUERY
# =========================================

def run_query(question: str):
    print("\n" + "=" * 80)
    print(f"QUERY: {question}")
    print("=" * 80)

    topic_docs = search_topics(question)
    refined_question = build_telemetry_query(question, topic_docs)
    telemetry_docs = search_telemetry(question, refined_question)

    context = build_context(question, refined_question, topic_docs, telemetry_docs)

    print("\nCONTEXT BUILT:\n")
    print(context)

    return context


# =========================================
# MAIN
# =========================================

if __name__ == "__main__":
    while True:
        q = input("\nEnter query (press Enter to exit): ").strip()
        if not q:
            break

        run_query(q)