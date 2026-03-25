import os
import shutil
import pandas as pd
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from mqtt.config import DATASET_ADAPTER, EMBED_MODEL

# =========================================
# CONFIG
# =========================================

TOPIC_XLSX_FILE = os.path.join("data", "f1_topic_descriptions.xlsx")
COLLECTION_NAME = f"{DATASET_ADAPTER}_topic_descriptions"
PERSIST_DIR = os.path.join("data", f"chroma_topics_{DATASET_ADAPTER}")

RESET_DB_EACH_RUN = True


# =========================================
# HELPERS
# =========================================

def reset_vector_db():
    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)
        print(f"🗑️ Deleted old topic DB: {PERSIST_DIR}")


def normalize_colnames(df: pd.DataFrame) -> pd.DataFrame:
    """
    Lowercase + trim column names so small Excel variations don't break code.
    """
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def load_topic_documents():
    documents = []

    if not os.path.exists(TOPIC_XLSX_FILE):
        print(f"⚠️ Topic description file not found: {TOPIC_XLSX_FILE}")
        return documents

    df = pd.read_excel(TOPIC_XLSX_FILE)
    df = normalize_colnames(df)

    required_cols = ["topic", "description"]
    for col in required_cols:
        if col not in df.columns:
            print(f"⚠️ Missing required column in Excel file: {col}")
            print(f"Available columns: {list(df.columns)}")
            return documents

    for i, row in df.iterrows():
        topic = str(row.get("topic", "")).strip()
        description = str(row.get("description", "")).strip()

        unit = str(row.get("unit", "")).strip() if "unit" in df.columns else ""
        purpose = str(row.get("purpose", "")).strip() if "purpose" in df.columns else ""

        # Clean NaN string cases
        if topic.lower() == "nan":
            topic = ""
        if description.lower() == "nan":
            description = ""
        if unit.lower() == "nan":
            unit = ""
        if purpose.lower() == "nan":
            purpose = ""

        if not topic or not description:
            continue

        text = f"Topic: {topic}. Description: {description}."
        if unit:
            text += f" Unit: {unit}."
        if purpose:
            text += f" Purpose: {purpose}."

        metadata = {
            "topic": topic,
            "unit": unit,
            "purpose": purpose,
            "adapter": DATASET_ADAPTER,
            "row_id": f"topic_{i:04d}",
            "source_file": os.path.basename(TOPIC_XLSX_FILE)
        }

        documents.append(
            Document(
                page_content=text,
                metadata=metadata
            )
        )

    return documents


# =========================================
# MAIN
# =========================================

def main():
    if RESET_DB_EACH_RUN:
        reset_vector_db()

    docs = load_topic_documents()

    print(f"Topic documents found: {len(docs)}")
    if not docs:
        return

    print("Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cpu"}
    )

    print("Creating topic description vector DB...")
    _vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=PERSIST_DIR
    )

    print("\n✅ Topic ingestion complete")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Persist directory: {PERSIST_DIR}")
    print(f"Total topics stored: {len(docs)}")


if __name__ == "__main__":
    main()