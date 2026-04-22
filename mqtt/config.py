import os

# =========================================
# DATASET SELECTION
# =========================================
# Used by:
# - UI runtime switching via environment variable
# - CLI/manual scripts via fallback default
DATASET_ADAPTER = os.getenv("DATASET_ADAPTER", "f1_adapter")


# =========================================
# EMBEDDING MODEL
# =========================================
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


# =========================================
# LLM MODEL
# =========================================
# UI can override this at runtime using environment variable
LLM_MODEL = os.getenv("LLM_MODEL", "llama3")