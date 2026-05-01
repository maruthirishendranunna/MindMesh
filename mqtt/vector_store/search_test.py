import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from mqtt.config import DATASET_ADAPTER, EMBED_MODEL

# =========================================
# CONFIG
# =========================================

COLLECTION_NAME = f"{DATASET_ADAPTER}_topic_descriptions"
PERSIST_DIR = os.path.join("data", f"chroma_topics_{DATASET_ADAPTER}")
TOP_K = 3


# =========================================
# LOAD VECTORSTORE
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


def search_topics(question: str, k: int = TOP_K):
    vectorstore = load_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    return retriever.invoke(question)


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

        results = search_topics(q)

        print("\n" + "=" * 80)
        print(f"QUERY: {q}")
        print("=" * 80)

        if not results:
            print("No matching topic descriptions found.")
            continue

        for i, doc in enumerate(results, start=1):
            print(f"\n MATCH {i}")
            print("-" * 80)
            print("METADATA:")
            print(doc.metadata)
            print("\nCONTENT:")
            print(doc.page_content)
            print("-" * 80)