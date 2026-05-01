import os
import time
import csv
from datetime import datetime

import pandas as pd
import ollama

from mqtt.query.query_context_builder import build_query_context
from mqtt.query.prompt_builder import build_prompt
from mqtt.adapters.loader import get_adapter


# =====================================================
# CONFIG
# =====================================================

OUTPUT_CSV = "evaluation/model_comparison_results.csv"
SUMMARY_CSV = "evaluation/model_comparison_summary.csv"

DATASETS = [
    "f1_adapter",
    "oilgas_adapter",
]

# Keep this small for faster testing
OLLAMA_MODELS = [
    "llama3",
    "mistral",
    #"gemma:2b",
    "nemotron-3-nano:4b",  # enable later if needed
]

# Optional cloud model testing
OPENAI_CONFIG = {
    "enabled": False,
    "model": "gpt-4o-mini",
}

ANTHROPIC_CONFIG = {
    "enabled": False,
    "model": "claude-3-5-haiku-latest",
}

# Keep test queries small and meaningful
TEST_QUERIES = {
    "f1_adapter": [
        {
            "query": "speed of hamilton in silverstone",
            "expected_keywords": ["hamilton", "speed", "silverstone"],
        },
        {
            "query": "rpm of perez in bahrain",
            "expected_keywords": ["perez", "rpm", "bahrain"],
        },
        {
            "query": "who has the top speed in silverstone",
            "expected_keywords": ["speed", "silverstone"],
        },
        {
            "query": "gear of hamilton in silverstone",
            "expected_keywords": ["hamilton", "gear", "silverstone"],
        },
        {
            "query": "fuel level of perez in bahrain",
            "expected_keywords": ["perez", "fuel", "bahrain"],
        },
        {
            "query": "is there any accidents happened in Bahrain",
            "expected_keywords": ["accident", "bahrain"],
        },
        {
            "query": "summarize telemetry for silverstone",
            "expected_keywords": ["silverstone", "telemetry"],
        },
    ],

    "oilgas_adapter": [
        {
            "query": "pressure of pump1",
            "expected_keywords": ["pump1", "pressure"],
        },
        {
            "query": "flow rate of site1",
            "expected_keywords": ["flow", "site1"],
        },
        {
            "query": "status of pump2",
            "expected_keywords": ["pump2", "status"],
        },
        {
            "query": "temperature of compressor1",
            "expected_keywords": ["compressor1", "temperature"],
        },
        {
            "query": "vibration of valve1",
            "expected_keywords": ["valve1", "vibration"],
        },
        {
            "query": "which equipment has highest pressure",
            "expected_keywords": ["highest", "pressure"],
        },
        {
            "query": "summarize telemetry for site1",
            "expected_keywords": ["site1", "telemetry"],
        },
    ],
}


# =====================================================
# BASIC HELPERS
# =====================================================

def set_dataset(dataset_adapter: str):
    os.environ["DATASET_ADAPTER"] = dataset_adapter


def safe_word_count(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


def keyword_score(answer: str, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 0.0

    answer_l = (answer or "").lower()
    hits = 0

    for kw in expected_keywords:
        if kw.lower() in answer_l:
            hits += 1

    return round(hits / len(expected_keywords), 2)


def build_prompt_once(dataset: str, question: str):
    """
    Build RAG context and prompt only once per query.
    Then reuse the same prompt for every model.
    """
    set_dataset(dataset)

    adapter = get_adapter()
    context = build_query_context(question)
    query_type = adapter.classify_query(question)
    prompt = build_prompt(question, context, query_type)

    return context, prompt, query_type


# =====================================================
# MODEL CALLS
# =====================================================

def call_ollama_model(model_name: str, prompt: str) -> str:
    response = ollama.chat(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a telemetry assistant. "
                    "Answer only using the provided context. "
                    "Do not invent values. "
                    "Keep the answer concise."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return response["message"]["content"].strip()


def call_openai_model(model_name: str, prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a telemetry assistant. "
                    "Answer only using the provided context. "
                    "Do not invent values. "
                    "Keep the answer concise."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return response.choices[0].message.content.strip()


def call_anthropic_model(model_name: str, prompt: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model=model_name,
        max_tokens=500,
        system=(
            "You are a telemetry assistant. "
            "Answer only using the provided context. "
            "Do not invent values. "
            "Keep the answer concise."
        ),
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    return response.content[0].text.strip()


# =====================================================
# EVALUATION
# =====================================================

def evaluate_model(
    dataset: str,
    provider: str,
    model_name: str,
    query: str,
    expected_keywords: list[str],
    prompt: str,
    query_type: str,
):
    start = time.time()

    try:
        if provider == "ollama":
            answer = call_ollama_model(model_name, prompt)
        elif provider == "openai":
            answer = call_openai_model(model_name, prompt)
        elif provider == "anthropic":
            answer = call_anthropic_model(model_name, prompt)
        else:
            raise ValueError(f"Unknown provider: {provider}")

        error = ""

    except Exception as e:
        answer = ""
        error = str(e)

    end = time.time()

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": dataset,
        "provider": provider,
        "model": model_name,
        "query_type": query_type,
        "query": query,
        "expected_keywords": ", ".join(expected_keywords),
        "keyword_accuracy_score": keyword_score(answer, expected_keywords),
        "response_time_seconds": round(end - start, 3),
        "answer_word_count": safe_word_count(answer),
        "answer": answer,
        "error": error,
    }


def run_evaluation():
    rows = []

    model_jobs = []

    for model in OLLAMA_MODELS:
        model_jobs.append(("ollama", model))

    if OPENAI_CONFIG["enabled"]:
        model_jobs.append(("openai", OPENAI_CONFIG["model"]))

    if ANTHROPIC_CONFIG["enabled"]:
        model_jobs.append(("anthropic", ANTHROPIC_CONFIG["model"]))

    total_tests = sum(len(v) for v in TEST_QUERIES.values()) * len(model_jobs)
    completed = 0

    print("\nStarting MindMesh model comparison...")
    print(f"Datasets: {DATASETS}")
    print(f"Models: {model_jobs}")
    print(f"Total model calls: {total_tests}")

    for dataset in DATASETS:
        print("\n" + "=" * 80)
        print(f"DATASET: {dataset}")
        print("=" * 80)

        query_items = TEST_QUERIES.get(dataset, [])

        for item in query_items:
            query = item["query"]
            expected_keywords = item["expected_keywords"]

            print(f"\nBuilding context once for query: {query}")

            try:
                context, prompt, query_type = build_prompt_once(dataset, query)
            except Exception as e:
                print(f"Context build failed for query: {query}")
                print(f"Error: {e}")

                for provider, model_name in model_jobs:
                    rows.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "dataset": dataset,
                        "provider": provider,
                        "model": model_name,
                        "query_type": "unknown",
                        "query": query,
                        "expected_keywords": ", ".join(expected_keywords),
                        "keyword_accuracy_score": 0,
                        "response_time_seconds": 0,
                        "answer_word_count": 0,
                        "answer": "",
                        "error": f"context_build_error: {e}",
                    })
                continue

            for provider, model_name in model_jobs:
                completed += 1
                print(
                    f"[{completed}/{total_tests}] "
                    f"Testing | Dataset={dataset} | Provider={provider} | "
                    f"Model={model_name} | Query={query}"
                )

                row = evaluate_model(
                    dataset=dataset,
                    provider=provider,
                    model_name=model_name,
                    query=query,
                    expected_keywords=expected_keywords,
                    prompt=prompt,
                    query_type=query_type,
                )

                rows.append(row)

                if row["error"]:
                    print(f"  ERROR: {row['error']}")
                else:
                    print(
                        f"  Score={row['keyword_accuracy_score']} | "
                        f"Time={row['response_time_seconds']}s | "
                        f"Words={row['answer_word_count']}"
                    )

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_ALL)

    summary = (
        df.groupby(["provider", "model"])
        .agg(
            avg_keyword_accuracy=("keyword_accuracy_score", "mean"),
            avg_response_time=("response_time_seconds", "mean"),
            avg_word_count=("answer_word_count", "mean"),
            total_errors=("error", lambda x: sum(1 for v in x if str(v).strip())),
        )
        .reset_index()
    )

    summary.to_csv(SUMMARY_CSV, index=False)

    print("\n✅ Evaluation complete")
    print(f"Saved full results to: {OUTPUT_CSV}")
    print(f"Saved summary to: {SUMMARY_CSV}")

    print("\n===== MODEL SUMMARY =====")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    run_evaluation()