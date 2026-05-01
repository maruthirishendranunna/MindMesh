import os
import sys
import streamlit as st


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


# =========================================
# DATASET + MODEL HELPERS
# =========================================

def get_available_adapters():
    adapter_dir = os.path.join("mqtt", "adapters")

    if not os.path.isdir(adapter_dir):
        return ["f1_adapter"]

    adapters = []
    for fname in os.listdir(adapter_dir):
        if not fname.endswith("_adapter.py"):
            continue
        if fname.startswith("__"):
            continue
        if fname == "loader.py":
            continue

        adapters.append(fname[:-3])

    adapters.sort()
    return adapters if adapters else ["f1_adapter"]


def clear_dataset_runtime_modules():
    modules_to_clear = [
        "mqtt.config",
        "mqtt.adapters.loader",
        "mqtt.query.query_context_builder",
        "mqtt.query.rag_query_engine",
        "mqtt.query.prompt_builder",
        "mqtt.vector_store.search_chunks_langchain",
    ]

    for mod in list(sys.modules.keys()):
        if mod in modules_to_clear:
            sys.modules.pop(mod, None)
        elif mod.startswith("mqtt.adapters."):
            sys.modules.pop(mod, None)


def set_runtime_dataset(dataset_adapter: str):
    os.environ["DATASET_ADAPTER"] = dataset_adapter
    clear_dataset_runtime_modules()


def set_runtime_model(model_name: str):
    os.environ["LLM_MODEL"] = model_name


# =========================================
# SESSION STATE
# =========================================

def init_session():
    available_datasets = get_available_adapters()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "selected_dataset" not in st.session_state:
        st.session_state.selected_dataset = (
            "f1_adapter" if "f1_adapter" in available_datasets else available_datasets[0]
        )

    if "active_dataset" not in st.session_state:
        st.session_state.active_dataset = st.session_state.selected_dataset

    if "selected_model" not in st.session_state:
        st.session_state.selected_model = AVAILABLE_MODELS[0]

    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False

    if "last_dataset_used" not in st.session_state:
        st.session_state.last_dataset_used = st.session_state.selected_dataset


# =========================================
# MEMORY HELPERS
# =========================================

def get_last_user_message():
    for msg in reversed(st.session_state.messages):
        if msg["role"] == "user":
            return msg["content"]
    return None


def get_last_assistant_message():
    for msg in reversed(st.session_state.messages):
        if msg["role"] == "assistant":
            return msg["content"]
    return None


def build_augmented_question(current_question: str) -> str:
    previous_user = get_last_user_message()
    previous_assistant = get_last_assistant_message()

    if not previous_user and not previous_assistant:
        return current_question.strip()

    parts = []

    if previous_user:
        parts.append(f"Previous user question: {previous_user}")

    if previous_assistant:
        parts.append(f"Previous assistant answer: {previous_assistant}")

    parts.append(f"Current user question: {current_question.strip()}")

    return "\n".join(parts)


def run_query_with_memory(question: str, debug_mode: bool, dataset_adapter: str):
    set_runtime_dataset(dataset_adapter)

    from mqtt.query.rag_query_engine import run_rag_query

    # Prevent cross-dataset memory contamination.
    # On the first query after switching datasets, do not inject previous memory.
    if dataset_adapter != st.session_state.get("last_dataset_used"):
        final_question = question.strip()
    else:
        final_question = build_augmented_question(question)

    st.session_state.last_dataset_used = dataset_adapter

    return run_rag_query(final_question, debug=debug_mode)


# =========================================
# INIT
# =========================================

init_session()
available_datasets = get_available_adapters()

set_runtime_dataset(st.session_state.active_dataset)
set_runtime_model(st.session_state.selected_model)


# =========================================
# SIDEBAR
# =========================================

st.sidebar.title("MindMesh Settings")

selected_dataset = st.sidebar.selectbox(
    "Select Dataset",
    available_datasets,
    index=available_datasets.index(st.session_state.selected_dataset)
    if st.session_state.selected_dataset in available_datasets else 0
)

selected_model = st.sidebar.selectbox(
    "Select LLM Model",
    AVAILABLE_MODELS,
    index=AVAILABLE_MODELS.index(st.session_state.selected_model)
    if st.session_state.selected_model in AVAILABLE_MODELS else 0
)

debug_mode = st.sidebar.checkbox(
    "Show debug output in terminal",
    value=st.session_state.debug_mode
)

# Clean dataset switch
if selected_dataset != st.session_state.selected_dataset:
    st.session_state.selected_dataset = selected_dataset
    st.session_state.active_dataset = selected_dataset
    st.session_state.messages = []
    set_runtime_dataset(selected_dataset)
    st.rerun()

# Model switch
if selected_model != st.session_state.selected_model:
    st.session_state.selected_model = selected_model
    set_runtime_model(selected_model)
    st.rerun()

st.session_state.debug_mode = debug_mode

# Always enforce runtime values
set_runtime_dataset(st.session_state.active_dataset)
set_runtime_model(st.session_state.selected_model)

if st.sidebar.button("Clear Chat History"):
    st.session_state.messages = []
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.write(f"**Current dataset:** {st.session_state.active_dataset}")
st.sidebar.write(f"**Current model:** {st.session_state.selected_model}")
st.sidebar.write(f"**Debug mode:** {st.session_state.debug_mode}")

st.sidebar.markdown("---")
st.sidebar.subheader("Example Queries")

dataset_examples = {
    "f1_adapter": [
        "speed of hamilton in silverstone",
        "rpm of perez in bahrain",
        "who has the top speed in silverstone",
        "what about other drivers",
        "is there any accidents happened in Bahrain",
    ],
    "oilgas_adapter": [
        "pressure of pump1",
        "flow rate of site1",
        "status of pump2",
        "which equipment has highest pressure",
        "any high temperature alerts",
    ],
}

example_queries = dataset_examples.get(
    st.session_state.active_dataset,
    ["show latest telemetry", "highest value", "what about others"]
)

for example in example_queries:
    if st.sidebar.button(example, key=f"example_{st.session_state.active_dataset}_{example}"):
        st.session_state.messages.append({
            "role": "user",
            "content": example
        })

        with st.spinner(
            f"Generating answer using {st.session_state.selected_model} on {st.session_state.active_dataset}..."
        ):
            result = run_query_with_memory(
                example,
                st.session_state.debug_mode,
                st.session_state.active_dataset
            )

        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "source": result["source"],
            "model": result["model"],
            "dataset": st.session_state.active_dataset
        })

        st.rerun()


# =========================================
# MAIN HEADER
# =========================================

st.title("MindMesh Telemetry Query Chat")
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
                st.caption(" Answer from structured telemetry")
            else:
                st.caption("🤖 Answer generated using LLM")

            st.caption(
                f"Model: {message.get('model', st.session_state.selected_model)} | "
                f"Dataset: {message.get('dataset', st.session_state.active_dataset)}"
            )


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
        with st.spinner(
            f"Generating answer using {st.session_state.selected_model} on {st.session_state.active_dataset}..."
        ):
            result = run_query_with_memory(
                user_question,
                st.session_state.debug_mode,
                st.session_state.active_dataset
            )

        st.success(result["answer"])

        if result["source"] == "adapter":
            st.caption("⚡ Answer from structured telemetry")
        else:
            st.caption("🤖 Answer generated using LLM")

        st.caption(
            f"Model: {result['model']} | Dataset: {st.session_state.active_dataset}"
        )

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "source": result["source"],
        "model": result["model"],
        "dataset": st.session_state.active_dataset
    })