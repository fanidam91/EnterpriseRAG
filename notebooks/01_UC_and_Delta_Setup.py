# Databricks notebook source
# MAGIC %md
# MAGIC # 01: Unity Catalog and Delta Lake Setup
# MAGIC 
# MAGIC This notebook initializes the Unity Catalog schemas, External Volumes, Delta Tables, and security access policies required for the **Enterprise RAG Knowledge Assistant**.
# MAGIC 
# MAGIC ### Architecture:
# MAGIC 1. **Catalog**: `main` (or custom corporate catalog)
# MAGIC 2. **Schema**: `knowledge_base`
# MAGIC 3. **Volume**: `raw_docs` (Staging directory for PDF, DOCX, XLSX, PPTX)
# MAGIC 4. **Delta Tables**:
# MAGIC    * `documents_metadata`: Tracking ingestion lineage, uploader details, file sizes.
# MAGIC    * `document_chunks`: Decomposed text sections and corresponding vector embeddings.
# MAGIC    * `query_audit_trail`: Query audit logs tracking RBAC/ABAC clearance verdicts.

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1: Create Catalogs, Schemas and Volumes
# MAGIC Establish namespaces under Unity Catalog to store data structures and files securely.

# COMMAND ----------

# Create Catalog if not exists
spark.sql("CREATE CATALOG IF NOT EXISTS adb_core_data_dev_aue")

# Use catalog
spark.sql("USE CATALOG adb_core_data_dev_aue")

# Create Database Schema
spark.sql("CREATE SCHEMA IF NOT EXISTS knowledge_base")
spark.sql("USE SCHEMA knowledge_base")

# Create Staging Volume for raw files
spark.sql("CREATE VOLUME IF NOT EXISTS raw_docs")

# Create Volume for streaming checkpoints
spark.sql("CREATE VOLUME IF NOT EXISTS checkpoints")

print("Unity Catalog Namespace and Staging Volumes successfully initialized.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2: Establish Delta Tables for Ingestion Lineage & Document Chunks

# COMMAND ----------

# 1. Bronze Table: Document Metadata Ingestion Lineage
spark.sql("""
CREATE TABLE IF NOT EXISTS documents_metadata (
  doc_id STRING NOT NULL,
  doc_name STRING NOT NULL,
  department STRING NOT NULL,
  clearance_level STRING NOT NULL,
  file_size LONG NOT NULL,
  uploader STRING NOT NULL,
  upload_timestamp TIMESTAMP NOT NULL,
  file_path STRING NOT NULL
)
USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'comment' = 'Bronze lineage table containing metadata of raw document files uploaded to UC Volumes'
);
""")

# 2. Silver Table: Chunked document content and Vector Index source
spark.sql("""
CREATE TABLE IF NOT EXISTS document_chunks (
  chunk_id STRING NOT NULL,
  doc_id STRING NOT NULL,
  doc_name STRING NOT NULL,
  section STRING NOT NULL,
  content STRING NOT NULL,
  embedding ARRAY<FLOAT> NOT NULL,
  sequence_num INT NOT NULL,
  department STRING NOT NULL,
  clearance_level STRING NOT NULL
)
USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'comment' = 'Silver table containing chunked segments of documents and calculated embedding vectors'
);
""")

# 3. System Auditing Table: Query logs and access outcomes
spark.sql("""
CREATE TABLE IF NOT EXISTS query_audit_trail (
  audit_id STRING NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  user_id STRING NOT NULL,
  user_role STRING NOT NULL,
  query_text STRING NOT NULL,
  status STRING NOT NULL,
  evaluated_docs_count INT NOT NULL,
  allowed_docs_count INT NOT NULL,
  denied_docs_count INT NOT NULL,
  details STRING NOT NULL,
  latency_ms DOUBLE NOT NULL,
  tokens_used INT NOT NULL
)
USING DELTA
TBLPROPERTIES (
  'comment' = 'Security audit table logging user queries and attribute verification logs'
);
""")

print("Delta tables initialized successfully in catalog adb_core_data_dev_aue.knowledge_base.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 3: Implement Security Policies (RBAC/ABAC Row-Level Security)
# MAGIC Establish row-level filters matching active user session attributes.

# COMMAND ----------

# MAGIC %sql
# MAGIC USE CATALOG adb_core_data_dev_aue;
# MAGIC USE SCHEMA knowledge_base;
# MAGIC 
# MAGIC -- Create Row Filter Function mapping user session properties to document attributes
# MAGIC CREATE OR REPLACE FUNCTION abac_department_filter(doc_dept STRING, doc_clearance STRING)
# MAGIC RETURN 
# MAGIC   -- Super users see all documents
# MAGIC   IS_MEMBER('executive_vp') OR
# MAGIC   (
# MAGIC     -- Match user domain grouping
# MAGIC     (doc_dept = 'HR' AND IS_MEMBER('hr_manager')) OR
# MAGIC     (doc_dept = 'Finance' AND IS_MEMBER('finance_analyst')) OR
# MAGIC     (doc_dept = 'IT' AND IS_MEMBER('it_administrator')) OR
# MAGIC     (doc_dept = 'Operations') -- Operations (Public) is visible to all
# MAGIC   ) AND (
# MAGIC     -- Enforce Clearance Levels
# MAGIC     doc_clearance = 'Public' OR
# MAGIC     (doc_clearance = 'Confidential' AND NOT IS_MEMBER('guest_employee'))
# MAGIC   );
# MAGIC 
# MAGIC -- Bind Row Filter Function to the document_chunks table to restrict reads
# MAGIC ALTER TABLE document_chunks SET ROW FILTER abac_department_filter ON (department, clearance_level);
