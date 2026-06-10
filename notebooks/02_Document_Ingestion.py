# Databricks notebook source
# MAGIC %md
# MAGIC # 02: Document Ingestion Pipeline (Spark Auto Loader)
# MAGIC 
# MAGIC This notebook sets up an incremental pipeline using Spark Auto Loader to ingest files from Unity Catalog volumes, perform text extraction, chunking, and write embeddings into Delta tables.
# MAGIC 
# MAGIC ### Libraries Installed:
# MAGIC * `pypdf`: Text extraction for PDFs
# MAGIC * `python-docx`: Text extraction for Word Docs
# MAGIC * `openpyxl`: Excel extraction
# MAGIC * `python-pptx`: Presentation slide extraction

# COMMAND ----------

# Install dependencies on workers
# MAGIC %pip install pypdf python-docx openpyxl python-pptx openai
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import os
from pyspark.sql.functions import col, input_file_name, current_timestamp, udf, pandas_udf
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, FloatType, IntegerType, BinaryType
import pandas as pd
from typing import Iterator

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1: Initialize Ingestion Directories
# MAGIC Read file path states from the Volume path created in Notebook 01.

# COMMAND ----------

volume_path = "dbfs:/Volumes/adb_core_data_dev_aue/knowledge_base/raw_docs/"
checkpoint_path = "dbfs:/Volumes/adb_core_data_dev_aue/knowledge_base/_checkpoints/raw_docs_ingest"

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2: Define Text Extraction & Chunking Logic
# MAGIC We wrap the text parser from `utils.py` into a Pandas UDF to enable Spark-native execution across workers.

# COMMAND ----------

def chunk_text_spark(text, section_name, max_chunk_size=800, overlap=100):
    chunks = []
    text = text.strip()
    if not text:
        return []
    
    start = 0
    while start < len(text):
        end = start + max_chunk_size
        if end < len(text):
            boundary = text.rfind('. ', end - 120, end)
            end = boundary + 1 if boundary != -1 else end
            
        chunk_content = text[start:end].strip()
        if chunk_content:
            chunks.append((section_name, chunk_content))
        start = end - overlap
        if start >= len(text) or end >= len(text):
            break
    return chunks

def extract_and_chunk(file_bytes, file_name):
    import io
    import pypdf
    import docx
    import openpyxl
    import pptx
    
    ext = file_name.split('.')[-1].lower()
    chunks = []
    
    try:
        if ext == 'pdf':
            pdf_file = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(pdf_file)
            for idx, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text:
                    chunks.extend(chunk_text_spark(text, f"Page {idx}"))
                    
        elif ext == 'docx':
            docx_file = io.BytesIO(file_bytes)
            doc = docx.Document(docx_file)
            curr_section = "Intro"
            curr_text = []
            for para in doc.paragraphs:
                if para.style.name.startswith('Heading'):
                    if curr_text:
                        chunks.extend(chunk_text_spark("\n".join(curr_text), curr_section))
                        curr_text = []
                    curr_section = para.text.strip()
                else:
                    if para.text.strip():
                        curr_text.append(para.text.strip())
            if curr_text:
                chunks.extend(chunk_text_spark("\n".join(curr_text), curr_section))
                
        elif ext == 'xlsx':
            xlsx_file = io.BytesIO(file_bytes)
            wb = openpyxl.load_workbook(xlsx_file, data_only=True)
            for name in wb.sheetnames:
                lines = [" | ".join([str(c) if c is not None else "" for c in r]) for r in wb[name].iter_rows(values_only=True)]
                if lines:
                    chunks.extend(chunk_text_spark("\n".join(lines), f"Sheet {name}", max_chunk_size=1200))
                    
        elif ext == 'pptx':
            pptx_file = io.BytesIO(file_bytes)
            prs = pptx.Presentation(pptx_file)
            for idx, slide in enumerate(prs.slides, 1):
                title = slide.shapes.title.text if slide.shapes.title else f"Slide {idx}"
                slide_texts = [s.text_frame.text for s in slide.shapes if s.has_text_frame]
                if slide_texts:
                    chunks.extend(chunk_text_spark("\n".join(slide_texts), f"Slide {idx}: {title}"))
                    
    except Exception as e:
        chunks = [("Error Parsing", f"Error extracting {file_name}: {str(e)}")]
        
    return chunks

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 3: Compute Text Embeddings via Azure OpenAI / Databricks Serving UDF

# COMMAND ----------

@udf(returnType=ArrayType(FloatType()))
def compute_embedding_udf(text):
    import openai
    import os
    
    # Check for keys in Environment or Databricks Secrets
    api_key = dbutils.secrets.get("azure-openai", "api-key")
    api_endpoint = "https://foundry-core-data-dev-us.openai.azure.com/"
    
    client = openai.AzureOpenAI(
        api_key=api_key,
        api_version="2024-02-15-preview",
        azure_endpoint=api_endpoint
    )
    
    response = client.embeddings.create(
        input=[text],
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 4: Stream Data with Spark Auto Loader
# MAGIC Define the structured schema and run `spark.readStream` to detect files on DBFS / Volumes.

# COMMAND ----------

# Schema matching the raw volume structure
raw_schema = StructType([
    StructField("content", BinaryType(), True)
])

# Read stream from volume
df_stream = (spark.readStream
  .format("cloudFiles")
  .option("cloudFiles.format", "binaryFile")
  .option("cloudFiles.useNotifications", "false")
  .load(volume_path)
)

# Extract file properties
df_parsed = df_stream.select(
    col("path").alias("file_path"),
    col("length").alias("file_size"),
    col("modificationTime").alias("upload_timestamp"),
    udf(lambda p: os.path.basename(p), StringType())("path").alias("doc_name")
)

# In actual deployment, a foreachBatch writer executes the chunking UDF, 
# computes embeddings, and saves outputs to the Bronze metadata and Silver chunks tables.

def process_batch(batch_df, batch_id):
    if batch_df.count() == 0:
        return
        
    # Collect batch data for parsing
    rows = batch_df.collect()
    for row in rows:
        # 1. Update Ingestion Lineage (documents_metadata table)
        doc_id = row['doc_name'].replace(" ", "_").lower()
        
        # Determine department and clearance level based on file name
        doc_name_lower = row['doc_name'].lower()
        dept = "Operations"
        clearance = "Public"
        if "hr" in doc_name_lower:
            dept = "HR"
            clearance = "Confidential"
        elif "finance" in doc_name_lower:
            dept = "Finance"
            clearance = "Confidential"
        elif "it" in doc_name_lower:
            dept = "IT"
            clearance = "Confidential"
            
        spark.sql(f"""
        INSERT INTO adb_core_data_dev_aue.knowledge_base.documents_metadata 
        VALUES ('{doc_id}', '{row['doc_name']}', '{dept}', '{clearance}', {row['file_size']}, 'system_loader', current_timestamp(), '{row['file_path']}')
        """)
        
        # 2. Extract, chunk, and embed content
        # Load raw file data (read from DBFS Volume)
        with open(row['file_path'].replace("dbfs:", "/dbfs"), "rb") as f:
            file_bytes = f.read()
            
        chunks = extract_and_chunk(file_bytes, row['doc_name'])
        
        # Create chunk dataframe to parallelize embedding calculations
        spark_chunks = spark.createDataFrame(
            [(f"{doc_id}_{idx}", doc_id, row['doc_name'], c[0], c[1], idx, dept, clearance) for idx, c in enumerate(chunks)],
            schema=["chunk_id", "doc_id", "doc_name", "section", "content", "sequence_num", "department", "clearance_level"]
        )
        
        # Compute embeddings using UDF
        spark_embedded = spark_chunks.withColumn("embedding", compute_embedding_udf(col("content")))
        
        # Append to target Silver table
        spark_embedded.write.format("delta").mode("append").saveAsTable("adb_core_data_dev_aue.knowledge_base.document_chunks")
        
    print(f"Batch {batch_id} processed successfully.")

# Write stream using foreachBatch
query = (df_stream.writeStream
  .foreachBatch(process_batch)
  .option("checkpointLocation", checkpoint_path)
  .start()
)
