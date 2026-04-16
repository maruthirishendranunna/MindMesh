import os
import streamlit as st

from mqtt.query.rag_query_engine import run_rag_query


# =========================================
# PAGE CONFIG
# =========================================

st.set_page_config(
    page_title="MindMesh Chat UI",
    page_icon="🏎️",
    layout="wide"
)


# =========================================
# SETTINGS
# =========================================

AVAILABLE_MODELS = [
    "llama3",
    "mistral",
    "gemma:2b",
    "nemotron-3-nano:4b",
]


def set_model_env(selected_model: str):
    os.environ["LLM_MODEL"] = selected_model


def init_session():
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "selected_model" not in st.session_state:
        st.session_state.selected_model = AVAILABLE_MODELS[0]

    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False


def get_last_user_message():
    """
    Return the most recent user message from chat history.
    """
    for msg in reversed(st.session_state.messages):
        if msg["role"] == "user":
            return msg["content"]
    return None


def get_last_assistant_message():
    """
    Return the most recent assistant message from chat history.
    """
    for msg in reversed(st.session_state.messages):
        if msg["role"] == "assistant":
            return msg["content"]
    return None


def build_augmented_question(current_question: str) -> str:
    """
    Build a lightweight conversational query so the backend can understand follow-ups.
    We pass previous user question + previous assistant answer + current question.
    """
    previous_user = get_last_user_message()
    previous_assistant = get_last_assistant_message()

    # If no history exists, just return current question
    if not previous_user and not previous_assistant:
        return current_question.strip()

    parts = []

    if previous_user:
        parts.append(f"Previous user question: {previous_user}")

    if previous_assistant:
        parts.append(f"Previous assistant answer: {previous_assistant}")

    parts.append(f"Current user question: {current_question.strip()}")

    return "\n".join(parts)


def run_query_with_memory(question: str, debug_mode: bool):
    """
    Run query through RAG with lightweight multi-turn memory.
    """
    augmented_question = build_augmented_question(question)
    return run_rag_query(augmented_question, debug=debug_mode)


init_session()


# =========================================
# SIDEBAR
# =========================================

st.sidebar.title("MindMesh Settings")

selected_model = st.sidebar.selectbox(
    "Select LLM Model",
    AVAILABLE_MODELS,
    index=AVAILABLE_MODELS.index(st.session_state.selected_model)
)

debug_mode = st.sidebar.checkbox(
    "Show debug output in terminal",
    value=st.session_state.debug_mode
)

if st.sidebar.button("Clear Chat History"):
    st.session_state.messages = []
    st.rerun()

st.session_state.selected_model = selected_model
st.session_state.debug_mode = debug_mode

set_model_env(selected_model)

st.sidebar.markdown("---")
st.sidebar.write(f"**Current model:** {selected_model}")
st.sidebar.write(f"**Debug mode:** {debug_mode}")

st.sidebar.markdown("---")
st.sidebar.subheader("Example Queries")

example_queries = [
    "speed of hamilton in silverstone",
    "rpm of perez in bahrain",
    "is there any accidents happened in Bahrain",
    "top speed of verstappen in silverstone",
    "summarize telemetry for silverstone",
]

for example in example_queries:
    if st.sidebar.button(example, key=f"example_{example}"):
        st.session_state.messages.append({
            "role": "user",
            "content": example
        })

        with st.spinner(f"Generating answer using {selected_model}..."):
            result = run_query_with_memory(example, debug_mode)

        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "source": result["source"],
            "model": result["model"]
        })

        st.rerun()


# =========================================
# MAIN HEADER
# =========================================

st.title("🏎️ MindMesh Telemetry Query Chat")
st.caption("Real-Time Telemetry Query System using MQTT + RAG")


# =========================================
# DISPLAY CHAT HISTORY
# =========================================

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
        else:
            st.success(message["content"])

            if message.get("source") == "adapter":
                st.caption("⚡ Answer from structured telemetry (fast & accurate)")
            else:
                st.caption("🤖 Answer generated using LLM")

            st.caption(f"Model used: {message.get('model', selected_model)}")


# =========================================
# CHAT INPUT
# =========================================

user_question = st.chat_input("Ask a telemetry question...")

if user_question:
    st.session_state.messages.append({
        "role": "user",
        "content": user_question
    })

    with st.chat_message("user"):
        st.markdown(user_question)

    with st.chat_message("assistant"):
        with st.spinner(f"Generating answer using {selected_model}..."):
            result = run_query_with_memory(user_question, debug_mode)

        st.success(result["answer"])

        if result["source"] == "adapter":
            st.caption("⚡ Answer from structured telemetry (fast & accurate)")
        else:
            st.caption("🤖 Answer generated using LLM")

        st.caption(f"Model used: {result['model']}")

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "source": result["source"],
        "model": result["model"]
    })