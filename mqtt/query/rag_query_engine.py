import os
import ollama

from mqtt.adapters.loader import get_adapter
from mqtt.query.query_context_builder import build_query_context
from mqtt.query.prompt_builder import build_prompt


# =========================================
# RUNTIME HELPERS
# =========================================

def get_runtime_adapter():
    return get_adapter()


def get_current_model() -> str:
    return os.getenv("LLM_MODEL", "llama3")


# =========================================
# MEMORY HELPERS
# =========================================

def extract_current_question(question: str) -> str:
    marker = "Current user question:"
    if marker in question:
        return question.split(marker, 1)[1].strip()
    return question.strip()


def extract_previous_user_question(question: str) -> str | None:
    marker = "Previous user question:"
    if marker not in question:
        return None

    text = question.split(marker, 1)[1]

    stop_markers = ["Previous assistant answer:", "Current user question:"]
    stop_positions = []

    for stop in stop_markers:
        if stop in text:
            stop_positions.append(text.index(stop))

    if stop_positions:
        end_idx = min(stop_positions)
        return text[:end_idx].strip()

    return text.strip()


def is_followup_other_query(question: str) -> bool:
    q = question.lower().strip()
    patterns = [
        "what about other",
        "what about others",
        "what about the rest",
        "other entities",
        "other equipment",
        "other items",
        "other players",
        "other patients",
        "other drivers",
        "show others",
        "show the rest",
        "and the rest",
    ]
    return any(p in q for p in patterns)


# =========================================
# LLM CALL
# =========================================

def ask_llm(prompt: str) -> str:
    current_model = get_current_model()

    try:
        response = ollama.chat(
            model=current_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful telemetry and monitoring data assistant. "
                        "Answer directly and clearly using only the provided context. "
                        "For metric questions, do not start with 'Yes' or 'No'. "
                        "For yes/no event questions, start with 'Yes' or 'No' when appropriate. "
                        "Do not invent information."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        return response["message"]["content"].strip()

    except Exception as e:
        return f"LLM error: {e}"


# =========================================
# MAIN RAG QUERY
# =========================================

def run_rag_query(question: str, debug: bool = True):
    adapter = get_runtime_adapter()
    current_model = get_current_model()

    effective_question = extract_current_question(question)
    previous_user_question = extract_previous_user_question(question)

    if is_followup_other_query(effective_question) and previous_user_question:
        retrieval_question = previous_user_question
    else:
        retrieval_question = question

    if debug:
        print("\n" + "=" * 80)
        print(f"RUNTIME DATASET ADAPTER: {os.getenv('DATASET_ADAPTER', 'f1_adapter')}")
        print(f"RETRIEVAL QUESTION: {retrieval_question}")
        print("=" * 80)
        print(f"EFFECTIVE QUESTION: {effective_question}")
        print(f"PREVIOUS USER QUESTION: {previous_user_question}")

    context = build_query_context(retrieval_question)

    if debug:
        print("\n" + "=" * 80)
        print("RETRIEVED CONTEXT")
        print("=" * 80)
        print(context)

    # Direct deterministic handling
    if adapter.can_handle_directly(effective_question):
        if debug:
            print("\n⚡ Using adapter-based deterministic handling...\n")

        result = adapter.get_direct_answer(effective_question, context)

        if result:
            if debug:
                print("\n" + "=" * 80)
                print("FINAL ANSWER")
                print("=" * 80)
                print(result)

            return {
                "answer": result,
                "source": "adapter",
                "model": current_model
            }

    # LLM fallback
    query_type = adapter.classify_query(effective_question)
    prompt = build_prompt(effective_question, context, query_type)

    if debug:
        print("\n" + "=" * 80)
        print("FINAL PROMPT")
        print("=" * 80)
        print(prompt)

        print("\n" + "=" * 80)
        print(f"GENERATING ANSWER USING OLLAMA MODEL: {current_model}")
        print("=" * 80)

    answer = ask_llm(prompt)

    if debug:
        print("\n" + "=" * 80)
        print("FINAL ANSWER")
        print("=" * 80)
        print(answer)

    return {
        "answer": answer,
        "source": "llm",
        "model": current_model
    }


# =========================================
# CLI DEBUG MODE
# =========================================

if __name__ == "__main__":
    print("MindMesh RAG Query Engine")
    print(f"Using Ollama model: {get_current_model()}")
    print(f"Runtime dataset: {os.getenv('DATASET_ADAPTER', 'f1_adapter')}")
    print("Press Enter without typing anything to exit.")

    while True:
        question = input("\nEnter query: ").strip()

        if not question:
            print("Exiting MindMesh RAG Query Engine.")
            break

        result = run_rag_query(question, debug=True)

        print("\nReturned Result Object:")
        print(result)