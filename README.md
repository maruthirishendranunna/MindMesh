# MindMesh – Real-Time Telemetry Query System using MQTT and RAG

MindMesh is a real-time telemetry query system that allows users to ask natural language questions over telemetry data. The system uses MQTT for real-time data streaming, ChromaDB for semantic retrieval, and Large Language Models through Ollama for response generation.

The project supports multiple datasets such as Formula 1 telemetry and Oil & Gas telemetry using an adapter-based design.

---

## Features

- Real-time telemetry publishing using MQTT
- MQTT-based telemetry processing
- Snapshot and event storage
- Text chunk generation from telemetry data
- Embedding generation using Sentence Transformers
- ChromaDB vector database for semantic retrieval
- Retrieval-Augmented Generation pipeline
- Streamlit-based user interface
- Dynamic dataset switching
- Dynamic LLM model switching
- Direct structured answers for simple queries
- LLM-based answers for complex queries
- Model comparison and evaluation support

---

## Supported Datasets

Currently supported datasets:

- Formula 1 telemetry
- Oil & Gas telemetry

Each dataset has its own adapter, publisher, topic descriptions, chunks, and vector database.

---

## Supported Models

The system supports local LLMs through Ollama:

- llama3
- mistral
- gemma:2b
- nemotron-3-nano:4b

Cloud models such as GPT or Gemini can be added later by extending the model call logic in `rag_query_engine.py`.

---

## Project Structure

```text
MindMesh/
│
├── ui_app.py
│
├── mqtt/
│   ├── config.py
│   │
│   ├── adapters/
│   │   ├── loader.py
│   │   ├── generic_adapter_template.py
│   │   ├── f1_adapter.py
│   │   └── oilgas_adapter.py
│   │
│   ├── publisher/
│   │   ├── f1_mqtt_publisher.py
│   │   └── oilgas_publisher.py
│   │
│   ├── processor/
│   │   ├── telemetry_processor.py
│   │   └── telemetry_snapshotter.py
│   │
│   ├── chunking/
│   │   └── chunk_builder.py
│   │
│   ├── vector_store/
│   │   ├── embed_chunks_langchain.py
│   │   └── ingest_topics.py
│   │
│   └── query/
│       ├── query_context_builder.py
│       ├── rag_query_engine.py
│       └── prompt_builder.py
│
├── data/
│   ├── f1_topic_descriptions.xlsx
│   ├── oilgas_topic_descriptions.xlsx
│   │
│   ├── chunks/
│   │   ├── f1_adapter/
│   │   └── oilgas_adapter/
│   │
│   ├── chroma_db_f1_adapter/
│   ├── chroma_topics_f1_adapter/
│   ├── chroma_db_oilgas_adapter/
│   └── chroma_topics_oilgas_adapter/
│
├── evaluation/
│   ├── model_comparison.py
│   ├── plot_model_comparison.py
│   ├── model_comparison_results.csv
│   ├── model_comparison_summary.csv
│   ├── model_comparison_summary_by_dataset.csv
│   │
│   └── plots_by_dataset/
│       ├── f1_accuracy_comparison.png
│       ├── f1_response_time_comparison.png
│       ├── f1_output_length_comparison.png
│       ├── f1_combined_comparison.png
│       ├── oilgas_accuracy_comparison.png
│       ├── oilgas_response_time_comparison.png
│       ├── oilgas_output_length_comparison.png
│       └── oilgas_combined_comparison.png
│
├── requirements.txt
└── README.md
```

---

## Installation

### 1. Clone the Repository

```bash
git clone <your-github-repository-url>
cd MindMesh
```

---

### 2. Create Virtual Environment

```bash
python -m venv venv
```

Activate it:

#### Windows CMD

```bash
venv\Scripts\activate
```

#### PowerShell

```powershell
.\venv\Scripts\Activate.ps1
```

#### macOS/Linux

```bash
source venv/bin/activate
```

---

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` is incomplete, install manually:

```bash
pip install streamlit paho-mqtt pandas openpyxl langchain langchain-chroma langchain-huggingface chromadb sentence-transformers ollama matplotlib
```

---

## External Software Setup

### Install Mosquitto MQTT Broker

Download:

```text
https://mosquitto.org/download/
```

Start broker:

```bash
mosquitto
```

Keep this terminal running.

---

### Install Ollama

Download:

```text
https://ollama.com
```

Pull models:

```bash
ollama pull llama3
ollama pull mistral
ollama pull gemma:2b
ollama pull nemotron-3-nano:4b
```

Verify:

```bash
ollama list
```

---

## Dataset Selection for Build Scripts

### Windows CMD

For F1:

```bash
set DATASET_ADAPTER=f1_adapter
```

For OilGas:

```bash
set DATASET_ADAPTER=oilgas_adapter
```

### PowerShell

For F1:

```powershell
$env:DATASET_ADAPTER="f1_adapter"
```

For OilGas:

```powershell
$env:DATASET_ADAPTER="oilgas_adapter"
```

The Streamlit UI supports dynamic dataset switching, but build scripts still require the adapter variable to be set.

---

# Running the Full Pipeline

Use separate terminals for:
- broker
- publisher
- processor
- snapshotter

---

## Step 1 – Start MQTT Broker

```bash
mosquitto
```

---

## Step 2 – Set Dataset Adapter

Example for F1:

```bash
set DATASET_ADAPTER=f1_adapter
```

Example for OilGas:

```bash
set DATASET_ADAPTER=oilgas_adapter
```

---

## Step 3 – Run Publisher

### Formula 1

```bash
python -m mqtt.publisher.f1_mqtt_publisher
```

### OilGas

```bash
python -m mqtt.publisher.oilgas_publisher
```

---

## Step 4 – Run Processor

```bash
python -m mqtt.processor.telemetry_processor
```

---

## Step 5 – Run Snapshotter

```bash
python -m mqtt.processor.telemetry_snapshotter
```

Allow telemetry to run for 1–3 minutes.

---

## Step 6 – Build Chunks

```bash
python -m mqtt.chunking.chunk_builder
```

---

## Step 7 – Generate Embeddings

```bash
python -m mqtt.vector_store.embed_chunks_langchain
```

---

## Step 8 – Ingest Topic Descriptions

```bash
python -m mqtt.vector_store.ingest_topics
```

---

## Step 9 – Launch Streamlit UI

```bash
streamlit run ui_app.py
```

---

# Using the UI

1. Select dataset:
   - `f1_adapter`
   - `oilgas_adapter`

2. Select model:
   - `llama3`
   - `mistral`
   - `gemma:2b`
   - `nemotron-3-nano:4b`

3. Enter query

4. View generated response

---

# Example Queries

## Formula 1

```text
speed of hamilton in silverstone
rpm of perez in bahrain
who has the top speed in silverstone
is there any accidents happened in Bahrain
```

## OilGas

```text
pressure of pump1
flow rate of site1
status of pump2
which equipment has highest pressure
```

---

# Model Evaluation

Run evaluation:

```bash
python -m evaluation.model_comparison
```

Generated files:

```text
evaluation/model_comparison_results.csv
evaluation/model_comparison_summary.csv
evaluation/model_comparison_summary_by_dataset.csv
```

Generate graphs:

```bash
python evaluation/plot_model_comparison.py
```

Graphs will be stored in:

```text
evaluation/plots_by_dataset/
```

---

# Expected Generated Files

After running the pipeline:

```text
data/chunks/f1_adapter/
data/chroma_db_f1_adapter/
data/chroma_topics_f1_adapter/

data/chunks/oilgas_adapter/
data/chroma_db_oilgas_adapter/
data/chroma_topics_oilgas_adapter/
```

Each dataset uses separate chunks and vector databases.

---

# Adding a New Dataset

## Step 1 – Create Adapter

```text
mqtt/adapters/<dataset>_adapter.py
```

---

## Step 2 – Create Publisher

```text
mqtt/publisher/<dataset>_publisher.py
```

---

## Step 3 – Add Topic Description Excel

```text
data/<dataset>_topic_descriptions.xlsx
```

---

## Step 4 – Set Adapter

```bash
set DATASET_ADAPTER=<dataset>_adapter
```

---

## Step 5 – Rebuild Pipeline

```bash
python -m mqtt.chunking.chunk_builder
python -m mqtt.vector_store.embed_chunks_langchain
python -m mqtt.vector_store.ingest_topics
```

The UI automatically detects adapters following:

```text
<dataset>_adapter.py
```

---

# Common Issues and Fixes

## Wrong Dataset Answers

Restart Streamlit:

```bash
streamlit run ui_app.py
```

Also clear chat history.

---

## No Relevant Data Found

Check folders:

```text
data/chunks/<dataset>_adapter/
data/chroma_db_<dataset>_adapter/
data/chroma_topics_<dataset>_adapter/
```

If missing:

```bash
python -m mqtt.chunking.chunk_builder
python -m mqtt.vector_store.embed_chunks_langchain
python -m mqtt.vector_store.ingest_topics
```

---

## Model Not Found

Check installed models:

```bash
ollama list
```

Pull model if missing:

```bash
ollama pull llama3
```

---

## CSV Permission Error During Evaluation

Close CSV files in Excel before rerunning evaluation.

---

# Team Members

Team MindMesh:

- Maruthi Rishendra Nunna
- Leela Bhavana Chennupati
- Chaitanya Upputuri
- Pranith Bhukya

---

# References

- MQTT: https://mqtt.org/
- Mosquitto: https://mosquitto.org/
- Paho MQTT: https://www.eclipse.org/paho/
- Ollama: https://ollama.com/
- ChromaDB: https://www.trychroma.com/
- Sentence Transformers: https://www.sbert.net/
- LangChain: https://www.langchain.com/
- Streamlit: https://streamlit.io/