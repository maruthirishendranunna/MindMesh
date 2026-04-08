import ollama

from mqtt.config import LLM_MODEL
from mqtt.adapters.loader import get_adapter
from mqtt.query.query_context_builder import build_query_context
from mqtt.query.prompt_builder import build_prompt

adapter = get_adapter()


# =========================================
# LLM CALL
# =========================================

def ask_llm(prompt: str) -> str:
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful data assistant. "
                    "Answer directly and clearly. "
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


# =========================================
# MAIN RAG PIPELINE
# =========================================

def run_rag_query(question: str):
    print("\n" + "=" * 80)
    print(f"USER QUERY: {question}")
    print("=" * 80)

    # Step 1: Build context
    context = build_query_context(question)

    print("\n" + "=" * 80)
    print("RETRIEVED CONTEXT")
    print("=" * 80)
    print(context)

    # Step 2: Direct deterministic handling from adapter
    if adapter.can_handle_directly(question):
        print("\n⚡ Using adapter-based deterministic handling...\n")
        result = adapter.get_direct_answer(question, context)

        if result:
            print("\n" + "=" * 80)
            print("FINAL ANSWER")
            print("=" * 80)
            print(result)
            return result

    # Step 3: Query type for prompt guidance
    query_type = adapter.classify_query(question)

    # Step 4: Build prompt
    prompt = build_prompt(question, context, query_type)

    print("\n" + "=" * 80)
    print("FINAL PROMPT")
    print("=" * 80)
    print(prompt)

    # Step 5: LLM fallback
    print("\n🤖 Generating answer using LLM...\n")
    answer = ask_llm(prompt)

    print("\n" + "=" * 80)
    print("FINAL ANSWER")
    print("=" * 80)
    print(answer)

    return answer


# =========================================
# MAIN
# =========================================

if __name__ == "__main__":
    print("MindMesh RAG Query Engine")
    print(f"Using Ollama model: {LLM_MODEL}")
    print("Press Enter without typing anything to exit.")

    while True:
        question = input("\nEnter query: ").strip()

        if not question:
            print("Exiting MindMesh RAG Query Engine.")
            break

        run_rag_query(question)