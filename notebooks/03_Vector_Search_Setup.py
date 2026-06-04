# Databricks notebook source
# MAGIC %md
# MAGIC # 03: Databricks Vector Search Configuration
# MAGIC 
# MAGIC This notebook configures the **Databricks Vector Search** service to index document chunks from our Delta Silver table and enable real-time semantic retrieval.
# MAGIC 
# MAGIC ### Actions:
# MAGIC 1. Create a Vector Search Endpoint.
# MAGIC 2. Create a Delta Sync Vector Index.
# MAGIC 3. Synchronize embeddings and run test queries.

# COMMAND ----------

# MAGIC %pip install databricks-vectorsearch
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1: Provision Vector Search Endpoint
# MAGIC The endpoint handles query serving and index synchronization.

# COMMAND ----------

endpoint_name = "vs_knowledge_endpoint"

# Check if endpoint already exists, otherwise create it
existing_endpoints = [e["name"] for e in vsc.list_endpoints().get("endpoints", [])]

if endpoint_name not in existing_endpoints:
    print(f"Creating Vector Search Endpoint: {endpoint_name} (this can take 15-20 minutes)...")
    vsc.create_endpoint(
        name=endpoint_name,
        endpoint_type="STANDARD"
    )
    print("Endpoint creation initiated.")
else:
    print(f"Endpoint '{endpoint_name}' already exists and is active.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2: Establish Delta Sync Vector Index
# MAGIC Link the index directly to the Delta table. Unity Catalog will manage schema sync.

# COMMAND ----------

source_table = "main.knowledge_base.document_chunks"
index_name = "main.knowledge_base.document_chunks_index"

# Create a Delta Sync index mapping embedding columns
try:
    vsc.create_delta_sync_index(
        endpoint_name=endpoint_name,
        index_name=index_name,
        source_table_name=source_table,
        pipeline_type="TRIGGERED", # Can be TRIGGERED or CONTINUOUS
        primary_key="chunk_id",
        embedding_dimension=1536,  # text-embedding-3-small dimension
        embedding_vector_column="embedding"
    )
    print(f"Delta Sync Index '{index_name}' successfully created.")
except Exception as e:
    print(f"Index creation state: {e}. Checking if already exists.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 3: Trigger Vector Index Synchronization
# MAGIC Sync the index to process current Delta table rows.

# COMMAND ----------

index = vsc.get_index(endpoint_name=endpoint_name, index_name=index_name)

print("Synchronizing index content...")
index.sync()

# Wait for sync status to complete
import time
status = index.describe()
while status.get("status", {}).get("state") == "SYNCING":
    print("Syncing data... sleeping 10s")
    time.sleep(10)
    status = index.describe()

print(f"Index Sync State: {status.get('status', {}).get('state')}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 4: Run Diagnostic Semantic Search Query

# COMMAND ----------

# Test vector query with dummy vector
import random
query_vector = [random.uniform(-1.0, 1.0) for _ in range(1536)]

results = index.similarity_search(
    query_vector=query_vector,
    columns=["chunk_id", "doc_id", "section", "content"],
    num_results=2
)

print("Diagnostic Search Results:")
import json
print(json.dumps(results, indent=2))
