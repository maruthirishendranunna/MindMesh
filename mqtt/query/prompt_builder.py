# =========================================
# PROMPT BUILDER (Bhavana Week-7 Task)
# =========================================

def build_prompt(question: str, context: str, query_type: str) -> str:
    """
    Build a structured prompt for the LLM.
    This prompt is generic and works across datasets because
    it is based on query types, not F1-specific values.
    """

    return f"""
You are an intelligent data question-answering assistant.

Answer the user's question using ONLY the provided context.

-----------------------------
STRICT RULES
-----------------------------
- Do not make up information
- Do not use outside knowledge
- If the answer is not present in the context, reply exactly:
  No relevant data found
- Keep the answer short, clear, and natural
- Do not explain your reasoning
- Do not mention the word "context"
- Give the final answer directly

-----------------------------
QUERY TYPE
-----------------------------
{query_type}

-----------------------------
ANSWER STYLE RULES
-----------------------------
1. If query type is EVENT:
- Start with "Yes," or "No," when appropriate
- Summarize the event clearly
- Mention important details if present

2. If query type is METRIC:
- Return the exact value if present
- Do not start with "Yes" or "No"
- Keep the answer short

3. If query type is COMPARISON:
- Return only the best/highest/lowest value
- Do not list unnecessary extra values
- Keep the answer direct and concise

4. If query type is GENERAL:
- Answer briefly using only the provided information

-----------------------------
QUESTION
-----------------------------
{question}

-----------------------------
CONTEXT
-----------------------------
{context}

-----------------------------
FINAL ANSWER
-----------------------------
""".strip()