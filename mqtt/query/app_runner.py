from mqtt.config import LLM_MODEL
from mqtt.query.rag_query_engine import run_rag_query


def main():
    print("MindMesh Query App")
    print(f"Using model: {LLM_MODEL}")
    print("Press Enter without typing anything to exit.")

    while True:
        question = input("\nAsk a question: ").strip()

        if not question:
            print("Exiting MindMesh Query App.")
            break

        answer = run_rag_query(question, debug=False)

        print("\nFinal Answer:")
        print(answer)


if __name__ == "__main__":
    main()