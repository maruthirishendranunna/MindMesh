# =========================================
# PROMPT BUILDER (Generic / Reusable)
# =========================================

def build_prompt(question: str, context: str, query_type: str) -> str:
    """
    Build a generic, reusable prompt for any dataset.

    This prompt is intentionally query-type-based, not dataset-based.
    So it can work with future datasets as long as the retrieval context
    is clear and structured.
    """

    query_type = (query_type or "general").strip().lower()

    query_type_rules = {
        "metric": """
- The user is asking for a direct value or factual measurement.
- Return the exact value if it is present.
- Keep the answer short and direct.
- Do not start with "Yes" or "No".
- If multiple relevant values are present, summarize them clearly and briefly.
""",
        "event": """
- The user is asking whether something happened or asking about an event.
- Start with "Yes," or "No," when appropriate.
- Then summarize the relevant event details clearly.
- If multiple events are present, combine them into one concise response.
""",
        "comparison": """
- The user is asking for highest, lowest, best, fastest, maximum, or minimum.
- Return only the most relevant comparison result.
- Prefer the single best final answer instead of listing many values.
- Include the entity and the value when available.
""",
        "general": """
- The user is asking for a summary, explanation, or follow-up.
- Do not give vague answers.
- Extract the most useful facts from the context.
- If multiple relevant items are present, summarize them clearly.
- Prefer a compact paragraph or short bullet-style summary in plain text.
"""
    }

    selected_rules = query_type_rules.get(query_type, query_type_rules["general"])

    prompt = f"""
You are an intelligent question-answering assistant.

Your task is to answer the user's question using ONLY the provided context.

========================================
GLOBAL RULES
========================================
- Use only the provided context.
- Do not use outside knowledge.
- Do not make up facts.
- If the answer is not available in the context, reply exactly:
No relevant data found
- Keep the answer clear, concise, and useful.
- Do not explain your reasoning.
- Do not mention phrases like "based on the context" or "according to the context".
- Give the final answer directly.

========================================
QUERY TYPE
========================================
{query_type.upper()}

========================================
QUERY-TYPE RULES
========================================
{selected_rules}

========================================
STYLE RULES
========================================
- Prefer exact values when they are available.
- Prefer concrete facts over generic descriptions.
- If there are multiple relevant records, organize them clearly.
- Do not repeat unnecessary details.
- Keep the answer readable for a normal user.

========================================
CONTEXT
========================================
{context}

========================================
QUESTION
========================================
{question}

========================================
FINAL ANSWER
========================================
""".strip()

    return prompt


# =========================================
# OPTIONAL TEST
# =========================================

if __name__ == "__main__":
    sample_question = "What is the current speed?"
    sample_context = "Sensor A speed is 45 km/h."
    sample_query_type = "metric"

    print(build_prompt(sample_question, sample_context, sample_query_type))