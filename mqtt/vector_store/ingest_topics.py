import os
import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer

EXCEL_PATH = os.path.join("data", "f1_topic_descriptions.xlsx")
COLLECTION_NAME = "f1_topics"
PERSIST_DIR = os.path.join("data", "chroma_db")  # saved locally

def main():
    # 1) Load Excel
    if not os.path.exists(EXCEL_PATH):
        raise FileNotFoundError(f"Excel not found at: {EXCEL_PATH}")

    df = pd.read_excel(EXCEL_PATH)

    required_cols = {"Topic", "Description", "Unit", "Purpose"}
    if not required_cols.issubset(set(df.columns)):
        raise ValueError(f"Excel must contain columns: {required_cols}. Found: {set(df.columns)}")

    # 2) Load embedding model
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # 3) Create persistent Chroma client
    client = chromadb.PersistentClient(path=PERSIST_DIR)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    # 4) Insert rows
    added = 0
    for idx, row in df.iterrows():
        topic = str(row["Topic"]).strip()
        desc = str(row["Description"]).strip()
        unit = str(row["Unit"]).strip()
        purpose = str(row["Purpose"]).strip()

        # document text stored in vector DB
        doc = f"Topic: {topic}\nDescription: {desc}\nUnit: {unit}\nPurpose: {purpose}"
        embedding = model.encode(doc).tolist()

        collection.add(
            ids=[str(idx)],
            documents=[doc],
            embeddings=[embedding],
            metadatas=[{"topic": topic, "unit": unit}]
        )
        added += 1

    print(f"✅ Stored {added} topic descriptions in ChromaDB")
    print(f"📁 Persisted at: {PERSIST_DIR}")
    print(f"📦 Collection: {COLLECTION_NAME}")

if __name__ == "__main__":
    main()
