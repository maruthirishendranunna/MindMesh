import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from mqtt.config import EMBED_MODEL
from mqtt.adapters.loader import get_adapter


# =========================================
# RUNTIME HELPERS
# =========================================

def get_runtime_dataset():
    return os.getenv("DATASET_ADAPTER", "f1_adapter")


def get_runtime_adapter():
    return get_adapter()


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
    dataset = get_runtime_dataset()
    embeddings = load_embeddings()

    return Chroma(
        collection_name=f"{dataset}_topic_descriptions",
        embedding_function=embeddings,
        persist_directory=os.path.join("data", f"chroma_topics_{dataset}")
    )


def load_telemetry_store():
    dataset = get_runtime_dataset()
    embeddings = load_embeddings()

    return Chroma(
        collection_name=f"{dataset}_telemetry_chunks",
        embedding_function=embeddings,
        persist_directory=os.path.join("data", f"chroma_db_{dataset}")
    )


# =========================================
# CONFIG FROM ADAPTER
# =========================================

def get_top_k_topic():
    adapter = get_runtime_adapter()
    return getattr(adapter, "TOP_K_TOPIC", 2)


def get_top_k_telemetry():
    adapter = get_runtime_adapter()
    return getattr(adapter, "TOP_K_TELEMETRY", 8)


def get_top_k_fallback():
    adapter = get_runtime_adapter()
    return getattr(adapter, "TOP_K_FALLBACK", 10)


# =========================================
# QUERY TYPE DETECTION
# =========================================

def classify_query(question: str):
    adapter = get_runtime_adapter()
    return adapter.classify_query(question)


# =========================================
# SEARCH TOPICS
# =========================================

def search_topics(question: str):
    adapter = get_runtime_adapter()
    normalized_question = adapter.normalize_question_text(question)

    store = load_topic_store()
    retriever = store.as_retriever(search_kwargs={"k": get_top_k_topic()})
    return retriever.invoke(normalized_question)


# =========================================
# BUILD TELEMETRY QUERY
# =========================================

def build_telemetry_query(original_question: str, topic_docs):
    adapter = get_runtime_adapter()
    query = adapter.build_telemetry_query_from_topics(original_question, topic_docs)
    return query if query else original_question


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
        docs = search_telemetry_with_filter(
            refined_question,
            "snapshots",
            get_top_k_telemetry()
        )
        if docs:
            return docs
        return search_telemetry_with_filter(
            refined_question,
            "events",
            get_top_k_fallback()
        )

    if query_type == "event":
        docs = search_telemetry_with_filter(
            refined_question,
            "events",
            get_top_k_telemetry()
        )
        if docs:
            return docs
        return search_telemetry_with_filter(
            refined_question,
            "snapshots",
            get_top_k_fallback()
        )

    docs = search_telemetry_with_filter(
        refined_question,
        "snapshots",
        get_top_k_telemetry()
    )
    if docs:
        return docs

    return search_telemetry_with_filter(
        refined_question,
        "events",
        get_top_k_fallback()
    )


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
    adapter = get_runtime_adapter()

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
    adapter = get_runtime_adapter()
    normalized_question = adapter.normalize_question_text(question)

    topic_docs = search_topics(normalized_question)
    refined_question = build_telemetry_query(normalized_question, topic_docs)
    telemetry_docs = search_telemetry(normalized_question, refined_question)

    context = build_context(normalized_question, refined_question, topic_docs, telemetry_docs)
    return context


# =========================================
# OPTIONAL DEBUG RUN
# =========================================

def run_query(question: str):
    adapter = get_runtime_adapter()
    normalized_question = adapter.normalize_question_text(question)

    print("\n" + "=" * 80)
    print(f"QUERY: {question}")
    print("=" * 80)
    print(f"RUNTIME DATASET: {get_runtime_dataset()}")

    topic_docs = search_topics(normalized_question)
    refined_question = build_telemetry_query(normalized_question, topic_docs)
    telemetry_docs = search_telemetry(normalized_question, refined_question)

    print(f"\nNORMALIZED QUESTION: {normalized_question}")
    print(f"QUERY TYPE: {classify_query(normalized_question)}")
    print(f"EXTRACTED ENTITIES: {adapter.extract_entities(normalized_question)}")
    print(f"REFINED TELEMETRY QUERY: {refined_question}")
    print(f"TOPIC MATCH COUNT: {len(topic_docs)}")
    print(f"TELEMETRY MATCH COUNT: {len(telemetry_docs)}")

    context = build_context(normalized_question, refined_question, topic_docs, telemetry_docs)

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