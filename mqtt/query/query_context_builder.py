import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from mqtt.config import DATASET_ADAPTER, EMBED_MODEL
from mqtt.adapters.loader import get_adapter


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

adapter = get_adapter()


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
    return adapter.classify_query(question)


# =========================================
# SEARCH TOPICS
# =========================================

def search_topics(question: str):
    normalized_question = adapter.normalize_question_text(question)
    store = load_topic_store()
    retriever = store.as_retriever(search_kwargs={"k": TOP_K_TOPIC})
    return retriever.invoke(normalized_question)


# =========================================
# BUILD TELEMETRY QUERY
# =========================================

def build_telemetry_query(original_question: str, topic_docs):
    return adapter.build_telemetry_query_from_topics(original_question, topic_docs)


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

    if query_type in ("metric", "comparison"):
        docs = search_telemetry_with_filter(refined_question, "snapshots", TOP_K_TELEMETRY)
        if docs:
            return docs
        return search_telemetry_with_filter(refined_question, "events", TOP_K_FALLBACK)

    if query_type == "event":
        docs = search_telemetry_with_filter(refined_question, "events", TOP_K_TELEMETRY)
        if docs:
            return docs
        return search_telemetry_with_filter(refined_question, "snapshots", TOP_K_FALLBACK)

    docs = search_telemetry_with_filter(refined_question, "snapshots", TOP_K_TELEMETRY)
    if docs:
        return docs

    return search_telemetry_with_filter(refined_question, "events", TOP_K_FALLBACK)


# =========================================
# CLEAN HELPERS
# =========================================

def clean_text(text: str) -> str:
    if not text:
        return ""

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def unique_preserve_order(items):
    seen = set()
    result = []

    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result


# =========================================
# BUILD CLEAN RAG CONTEXT
# =========================================

def build_context(original_question: str, refined_question: str, topic_docs, telemetry_docs):
    topic_texts = []
    telemetry_texts = []

    for doc in topic_docs:
        text = clean_text(doc.page_content)
        if text:
            topic_texts.append(text)

    for doc in telemetry_docs:
        text = clean_text(doc.page_content[:1200])

        if not text:
            continue

        filtered_lines = adapter.filter_telemetry_lines(
            original_question=original_question,
            refined_question=refined_question,
            text=text
        )

        if filtered_lines:
            telemetry_texts.append("\n".join(filtered_lines))

    topic_texts = unique_preserve_order(topic_texts)
    telemetry_texts = unique_preserve_order(telemetry_texts)

    lines = []
    lines.append(f"User question: {original_question}")
    lines.append("")

    if refined_question and refined_question != original_question:
        lines.append(f"Telemetry search focus: {refined_question}")
        lines.append("")

    if topic_texts:
        lines.append("Relevant topic information:")
        for text in topic_texts:
            lines.append(text)
            lines.append("")

    if telemetry_texts:
        lines.append("Relevant telemetry information:")
        for text in telemetry_texts:
            lines.append(text)
            lines.append("")

    if not topic_texts and not telemetry_texts:
        lines.append("No relevant topic or telemetry information was retrieved.")

    return "\n".join(lines).strip()


# =========================================
# MAIN FUNCTION FOR RAG
# =========================================

def build_query_context(question: str) -> str:
    topic_docs = search_topics(question)
    refined_question = build_telemetry_query(question, topic_docs)
    telemetry_docs = search_telemetry(question, refined_question)

    context = build_context(question, refined_question, topic_docs, telemetry_docs)
    return context


# =========================================
# OPTIONAL DEBUG RUN
# =========================================

def run_query(question: str):
    print("\n" + "=" * 80)
    print(f"QUERY: {question}")
    print("=" * 80)

    topic_docs = search_topics(question)
    refined_question = build_telemetry_query(question, topic_docs)
    telemetry_docs = search_telemetry(question, refined_question)

    print(f"\nQUERY TYPE: {classify_query(question)}")
    print(f"EXTRACTED ENTITIES: {adapter.extract_entities(question)}")
    print(f"REFINED TELEMETRY QUERY: {refined_question}")
    print(f"TOPIC MATCH COUNT: {len(topic_docs)}")
    print(f"TELEMETRY MATCH COUNT: {len(telemetry_docs)}")

    context = build_context(question, refined_question, topic_docs, telemetry_docs)

    print("\nCLEAN CONTEXT BUILT:\n")
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