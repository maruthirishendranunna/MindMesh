import os
import chromadb
from sentence_transformers import SentenceTransformer

PERSIST_DIR = os.path.join("data", "chroma_db")
COLLECTION_NAME = "f1_topics"

def main():
    model = SentenceTransformer("all-MiniLM-L6-v2")

    client = chromadb.PersistentClient(path=PERSIST_DIR)
    collection = client.get_collection(name=COLLECTION_NAME)

    query = "Hamilton speed"
    q_emb = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[q_emb],
        n_results=3
    )

    print("Query:", query)
    print("Top matches:")
    for doc in results["documents"][0]:
        print("-" * 30)
        print(doc)

if __name__ == "__main__":
    main()
