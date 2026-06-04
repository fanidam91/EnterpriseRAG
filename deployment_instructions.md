# Deployment & Production Setup Instructions

This document provides a step-by-step guide to deploying the **Databricks Enterprise Knowledge Assistant** into a production Azure & Databricks environment.

---

## Architecture Overview

```
                        +----------------------------+
                        |  Streamlit Chat Interface  |
                        +--------------+-------------+
                                       |
                                       | Queries & Ingestion
                                       v
                        +--------------+-------------+
                        |     Azure Web App / VM     |
                        +--------------+-------------+
                                       |
                   +-------------------+-------------------+
                   | (Files/Metadata)                      | (Vector Search & MLflow)
                   v                                       v
     +-------------+-------------+           +-------------+-------------+
     |   Databricks Volumes /    |           |   Databricks Vector Search|
     |   Azure Blob Storage      |           |   Endpoint & Delta Index  |
     +-------------+-------------+           +-------------+-------------+
                   |                                       ^
                   | Spark Auto Loader                     | Synced
                   v                                       |
     +-------------+-------------+                         |
     |  Spark Ingestion Pipeline |                         |
     +-------------+-------------+                         |
                   |                                       |
                   | Text Chunks & Vector Embeddings       |
                   v                                       |
     +-------------+-------------+-------------------------+
     |  Unity Catalog Delta Lake |
     |  `main.knowledge_base`    |
     +---------------------------+
```

---

## Prerequisites

1. **Azure Databricks Workspace**: Enabled with Unity Catalog and Serverless SQL Warehouses (or vector search capabilities).
2. **Azure OpenAI Service**: A deployed instance with:
   * **gpt-4o** (or gpt-4) chat completion deployment model.
   * **text-embedding-3-small** (or text-embedding-ada-002) embeddings deployment model.
3. **Workspace Access Permissions**: Admin/Creator access on Databricks to manage Catalogs, Vector endpoints, and Model Serving.

---

## Step-by-Step Deployment Guide

### Phase 1: Databricks Secret Scope Setup
Securely store the Azure OpenAI API credentials inside Databricks Secret Manager to prevent raw key leakages in notebooks.

1. Install the Databricks CLI locally and authenticate with your workspace.
2. Create a secret scope called `azure-openai`:
   ```bash
   databricks secrets create-scope azure-openai
   ```
3. Store your Azure OpenAI API key under the key name `api-key`:
   ```bash
   databricks secrets put-secret azure-openai api-key
   ```

---

### Phase 2: Unity Catalog & Database Schema Provisioning
Import and execute the setup notebook inside your Databricks Workspace:

1. Import [01_UC_and_Delta_Setup.py](file:///c:/Users/fanid/Desktop/Projects/EnterpriseRAGChat/notebooks/01_UC_and_Delta_Setup.py) into your workspace.
2. Run the notebook using a Single-User Cluster or Serverless compute.
3. Verify that the catalog `main`, schema `knowledge_base`, volume `raw_docs`, and Delta tables (`documents_metadata`, `document_chunks`, `query_audit_trail`) are visible inside the Databricks Catalog Explorer.

---

### Phase 3: Spark Auto Loader Ingestion Pipeline
Set up the scheduled document extraction engine:

1. Import [02_Document_Ingestion.py](file:///c:/Users/fanid/Desktop/Projects/EnterpriseRAGChat/notebooks/02_Document_Ingestion.py) into Databricks.
2. Modify the `api_endpoint` URL inside `compute_embedding_udf` to point to your specific Azure OpenAI Resource.
3. Run the notebook. Alternatively, create a **Databricks Workflows Job** executing this notebook on a scheduled cron trigger (e.g., hourly) or set to `Continuous` execution to auto-process files deposited in the volume.

---

### Phase 4: Databricks Vector Search Endpoint & Index Setup
Initiate standard semantic indices:

1. Import [03_Vector_Search_Setup.py](file:///c:/Users/fanid/Desktop/Projects/EnterpriseRAGChat/notebooks/03_Vector_Search_Setup.py) into Databricks.
2. Run the notebook. *Note: Provisioning a Standard Vector Search endpoint typically takes 10 to 15 minutes.*
3. Verify the index status by running the final search cells in the notebook.

---

### Phase 5: Bundle and Serve via MLflow Model Registry
Compile the RAG pipeline as a single served API:

1. Import [04_MLflow_RAG_Deployment.py](file:///c:/Users/fanid/Desktop/Projects/EnterpriseRAGChat/notebooks/04_MLflow_RAG_Deployment.py) into Databricks.
2. Run the notebook. It registers the RAG model inside Unity Catalog Model Registry (`main.knowledge_base.rag_assistant_model`) and initiates a Model Serving endpoint named `rag-serving-endpoint`.
3. Check the **Model Serving** tab on your Databricks sidebar to monitor deployment progress. Once active, the serving endpoint provides a REST API that runs the entire search + LLM RAG logic.

---

### Phase 6: Streamlit Frontend Deployment
Run the conversational interface locally or deploy to a web service:

1. Install dependencies listed in `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```
2. Launch the Streamlit application:
   ```bash
   streamlit run app/main.py
   ```
3. Navigate to **System Settings** in the Streamlit UI and toggle off **Simulation Mode**.
4. Input your active credentials:
   * **Azure OpenAI Endpoint** and **API Key**.
   * **Databricks Workspace Host URL** and **Personal Access Token (PAT)**.
   * Target Vector Search Endpoint name and index mapping details.
5. Click **Save System Configuration** to activate the direct production RAG channel.
