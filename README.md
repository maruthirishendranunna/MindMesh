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

Week 4: 

# MindMesh – Real-Time Telemetry System

## Project Overview
This project implements a real-time telemetry monitoring system using MQTT and a future RAG-based AI pipeline.

## Project Structure
- mqtt/publisher → Telemetry generation
- mqtt/subscriber → Telemetry reception
- data → Topic descriptions for vector DB
- docs → Documentation

## How to Run Publisher
python mqtt/publisher/f1_mqtt_publisher.py

## How to Run Subscriber
python mqtt/subscriber/f1_mqtt_subscriber.py


## Week 2 – Real-Time Analytics, Query Engine & Vector Database
## Overview

In Week-2, the project moved beyond basic telemetry streaming and introduced real-time analytics, a structured query engine for live data access, and semantic topic retrieval using a vector database. This week established the core foundation required for integrating the RAG pipeline and LLM in the upcoming phases.

## Components Implemented
🔹 Telemetry Processor – Live Race Analytics

The telemetry processor consumes real-time driver data from MQTT and generates derived race insights.
These analytics are published back to MQTT as new topics.

Generated analytics:

Fastest driver

Race leader (based on lap progression)

Team average speed

Published topics:

race/fastest_driver
race/leader_driver
race/leader_lap
race/team_avg_speed/<team>

🔹 Query Engine – Real-Time Data Access Layer

The query engine acts as the retrieval interface for the future RAG + LLM pipeline.

It:

Subscribes to both telemetry and analytics topics

Maintains a real-time topic cache

Provides structured lookup functions for:

Driver metrics

Race leader

Fastest driver

Team performance

This layer allows the LLM to fetch live values instead of static database data.

🔹 Vector Database – Semantic Topic Retrieval

Topic descriptions were embedded using Sentence Transformers and stored in ChromaDB.

This enables:

Natural language → Relevant MQTT topic mapping

Example:

Query:

Hamilton speed

Top match:

f1/mercedes/hamilton/speed

The vector database stores only topic metadata, not live telemetry values, ensuring efficiency and scalability.

## How to Run Week-2 Demo:
1.Start Mosquitto MQTT broker

2.Run telemetry publisher
python -m mqtt.publisher.f1_mqtt_publisher

3.Run Subscriber
python mqtt/subscriber/f1_mqtt_subscriber.py

4.Run telemetry processor
python -m mqtt.processor.telemetry_processor

5.Run query engine
python -m mqtt.query.query_engine

6.If you have python version 3.13 or 3.14 chroma DB wont work in this version. You need have at least 3.12 version. Here are the steps to install python 3.12 and run ingest_topics code:
Install winget install Python.Python.3.12(Using CMD)

py -0p using this you can verify if the version is in your path variables or not.

Create virtual environment for your project
Create venv(locally):
py -3.12 -m venv .venv
Activate the venv:
.\.venv\Scripts\activate

You will now see (.venv) at the beginning of the terminal.

Install required libraries inside venv
python -m pip install --upgrade pip
pip install pandas openpyxl chromadb sentence-transformers

7.Run vector ingestion (one-time setup)
python -m mqtt.vector_store.ingest_topics

8.Run semantic retrieval test
python -m mqtt.vector_store.search_test
