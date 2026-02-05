# MindMesh – Intelligent IoT Query System using RAG and LLM

## Project Overview
MindMesh is an intelligent IoT query system that allows users to ask natural language questions about real-time sensor data.
The system uses a Large Language Model (LLM) with Retrieval-Augmented Generation (RAG) to interpret queries, identify relevant MQTT topics, and fetch live telemetry values.

## Architecture Highlights
* LLM-driven query understanding
* Vector database storing MQTT topic descriptions
* Real-time telemetry retrieval via MQTT
* Lightweight user interface
* Local LLM deployment using Ollama

## Tech Stack
* Python
* Mosquitto (MQTT Broker)
* Paho-MQTT
* ChromaDB
* Sentence Transformers
* Ollama / Llama3
* LangChain
* Streamlit

## Project Status
🔧 Currently in development – building the real-time telemetry pipeline.

## Goal
To design a scalable architecture that separates semantic retrieval from real-time data processing while enabling natural language interaction with IoT systems.

To design a scalable architecture that separates semantic retrieval from real-time data processing while enabling natural language interaction with IoT systems.
