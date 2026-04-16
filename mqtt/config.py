import os

DATASET_ADAPTER = "f1_adapter"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL = os.getenv("LLM_MODEL", "llama3")