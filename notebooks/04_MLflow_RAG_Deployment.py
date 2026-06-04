# Databricks notebook source
# MAGIC %md
# MAGIC # 04: MLflow RAG Chain Registration and Model Serving
# MAGIC 
# MAGIC This notebook bundles our semantic retrieval and Azure OpenAI prompt orchestration into a unified **MLflow pyfunc Model**, registers it in the Unity Catalog Model Registry, and deploys it to a production Databricks Model Serving Endpoint.

# COMMAND ----------

# MAGIC %pip install mlflow openai databricks-vectorsearch databricks-sdk
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import os
import json
import mlflow
from openai import AzureOpenAI
from databricks.vector_search.client import VectorSearchClient

# Configure MLflow to register models directly to Unity Catalog
mlflow.set_registry_uri("databricks-uc")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1: Define the custom MLflow PythonModel subclass
# MAGIC Bundling retrieval, ABAC filtering, and prompt completion into a single deployable object.

# COMMAND ----------

class EnterpriseRAGModel(mlflow.pyfunc.PythonModel):
    
    def load_context(self, context):
        """Loads credentials and configs from artifacts or environment variables."""
        # Initialize clients
        self.vsc = VectorSearchClient()
        self.endpoint_name = "vs_knowledge_endpoint"
        self.index_name = "main.knowledge_base.document_chunks_index"
        self.index = self.vsc.get_index(endpoint_name=self.endpoint_name, index_name=self.index_name)
        
        # Initialize LLM credentials
        self.client = AzureOpenAI(
            api_key=dbutils.secrets.get("azure-openai", "api-key"),
            api_version="2024-02-15-preview",
            azure_endpoint="https://your-resource.openai.azure.com/"
        )
        self.llm_deployment = "gpt-4o"
        self.embeddings_deployment = "text-embedding-3-small"

    def predict(self, context, model_input):
        """
        Calculates inference.
        Input format expected: pd.DataFrame with columns ['query', 'user_id', 'user_role', 'allowed_departments', 'clearance_level']
        """
        results = []
        for index, row in model_input.iterrows():
            query = row["query"]
            user_depts = json.loads(row.get("allowed_departments", "['Operations']"))
            user_clearance = row.get("clearance_level", "Public")
            
            # A. Generate Query Vector Embedding
            embed_res = self.client.embeddings.create(
                input=[query],
                model=self.embeddings_deployment
            )
            query_vector = embed_res.data[0].embedding
            
            # B. Execute Vector Search with ABAC filters mapping department attributes
            search_filters = {"department": user_depts}
            search_res = self.index.similarity_search(
                query_vector=query_vector,
                columns=["chunk_id", "doc_name", "department", "clearance_level", "section", "content"],
                filters=search_filters,
                num_results=3
            )
            
            # Process search context
            chunks = search_res.get("result", {}).get("data_array", [])
            context_str = ""
            citations = []
            
            for c in chunks:
                # columns mapping: chunk_id, doc_name, department, clearance_level, section, content
                c_name, c_sec, c_text = c[1], c[4], c[5]
                context_str += f"\n\nSource: {c_name} (Section: {c_sec})\nContent: {c_text}"
                citations.append({"doc_name": c_name, "section": c_sec})
                
            # C. Execute Chat Completion with grounding context
            messages = [
                {"role": "system", "content": "You are a secure corporate assistant. Base your answers solely on the provided contexts. Cite sources.\n\nContext:" + context_str},
                {"role": "user", "content": query}
            ]
            
            llm_res = self.client.chat.completions.create(
                model=self.llm_deployment,
                messages=messages,
                temperature=0.0
            )
            
            response_text = llm_res.choices[0].message.content
            results.append({
                "answer": response_text,
                "citations": citations
            })
            
        return results

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2: Track Experiment and Register Model in Unity Catalog

# COMMAND ----------

# Set active experiment path in workspace
mlflow.set_experiment("/Shared/EnterpriseRAGExperiment")

with mlflow.start_run(run_name="deploy_rag_chain") as run:
    # Set model requirements
    conda_env = mlflow.pyfunc.get_default_conda_env()
    conda_env['dependencies'][2]['pip'] = [
        "mlflow",
        "openai",
        "databricks-vectorsearch",
        "databricks-sdk",
        "pandas"
    ]
    
    # Save parameters
    mlflow.log_param("retrieval_endpoint", "vs_knowledge_endpoint")
    mlflow.log_param("retrieval_index", "main.knowledge_base.document_chunks_index")
    mlflow.log_param("openai_llm", "gpt-4o")
    
    # Log model artifacts
    model_info = mlflow.pyfunc.log_model(
        artifact_path="rag_chain",
        python_model=EnterpriseRAGModel(),
        conda_env=conda_env,
        registered_model_name="main.knowledge_base.rag_assistant_model"
    )
    print("Model registered in Unity Catalog Registry successfully.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 3: Deploy registered Model to Serving Endpoint
# MAGIC Configure real-time model serving container endpoints in Databricks.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedModelInput

w = WorkspaceClient()

endpoint_name = "rag-serving-endpoint"
registered_model = "main.knowledge_base.rag_assistant_model"
model_version = "1" # Deploy version 1

# Define model instance config
config = EndpointCoreConfigInput(
    served_models=[
        ServedModelInput(
            model_name=registered_model,
            model_version=model_version,
            workload_size="Small",
            scale_to_zero_enabled=True # Enable scale down to zero to manage cloud expenses
        )
    ]
)

# Upsert endpoint serving configuration
existing = [e.name for e in w.serving_endpoints.list()]
if endpoint_name in existing:
    print(f"Updating configuration for serving endpoint: {endpoint_name}...")
    w.serving_endpoints.update_config(name=endpoint_name, served_models=config.served_models)
else:
    print(f"Creating serving endpoint: {endpoint_name}...")
    w.serving_endpoints.create(name=endpoint_name, config=config)

print(f"Serving endpoint '{endpoint_name}' is provisioning. Scale-to-zero is active.")
