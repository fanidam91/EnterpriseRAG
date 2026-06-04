import os
import sqlite3
import time
import json
from datetime import datetime
import pandas as pd
from app.auth import evaluate_abac_policy
from app.openai_client import generate_embeddings

# Define SQLite simulation file path
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "databricks_simulation.db")

def get_db_connection():
    """Returns a SQLite connection for the simulated Databricks environment."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    """Initializes simulated Delta tables and Unity Catalog structures in SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Delta Table: Document Metadata (Unity Catalog Catalog: `knowledge_base.catalog.documents`)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS delta_documents (
            doc_id TEXT PRIMARY KEY,
            doc_name TEXT NOT NULL,
            department TEXT NOT NULL,
            clearance_level TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            uploader TEXT NOT NULL,
            upload_timestamp TIMESTAMP NOT NULL,
            file_path TEXT NOT NULL
        )
    """)
    
    # 2. Delta Table: Document Chunks & Vector Store (Unity Catalog Catalog: `knowledge_base.catalog.vector_index`)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS delta_document_chunks (
            chunk_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            section TEXT NOT NULL,
            content TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            sequence_num INTEGER NOT NULL,
            FOREIGN KEY (doc_id) REFERENCES delta_documents(doc_id) ON DELETE CASCADE
        )
    """)
    
    # 3. Delta Table: Query Audit Trail (Unity Catalog Catalog: `system.audit.query_logs`)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_query_logs (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL,
            user_id TEXT NOT NULL,
            user_role TEXT NOT NULL,
            query_text TEXT NOT NULL,
            status TEXT NOT NULL,
            evaluated_docs_count INTEGER NOT NULL,
            allowed_docs_count INTEGER NOT NULL,
            denied_docs_count INTEGER NOT NULL,
            details_json TEXT NOT NULL,
            latency_ms REAL NOT NULL,
            tokens_used INTEGER NOT NULL
        )
    """)

    conn.commit()
    conn.close()

# Initialize the db during module import
initialize_db()

def upload_document_to_volume(doc_name, file_content_bytes, department, clearance_level, uploader_profile, config=None):
    """
    Simulates writing a file to Unity Catalog Volume and running the ingestion pipeline.
    Extracts text, chunks it, creates embeddings, and writes to Delta Tables.
    """
    start_time = time.time()
    doc_id = doc_name.replace(" ", "_").lower()
    
    # Check simulation mode
    if not config or config.get("simulation_mode", True):
        # 1. Extract text and chunk (simulated or using standard utils if available)
        # For simulation, we'll write metadata first
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Upsert document record
        cursor.execute("""
            INSERT OR REPLACE INTO delta_documents (doc_id, doc_name, department, clearance_level, file_size, uploader, upload_timestamp, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id, 
            doc_name, 
            department, 
            clearance_level, 
            len(file_content_bytes), 
            uploader_profile.get("user_id"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"dbfs:/Volumes/main/knowledge_store/raw_docs/{doc_name}"
        ))
        
        # 2. Ingestion pipeline chunking (using basic text parsing fallback)
        from app.utils import parse_file_bytes_to_chunks
        chunks = parse_file_bytes_to_chunks(doc_name, file_content_bytes)
        
        # Clear existing chunks for this document
        cursor.execute("DELETE FROM delta_document_chunks WHERE doc_id = ?", (doc_id,))
        
        total_tokens = 0
        for idx, chunk in enumerate(chunks):
            # Compute chunk embedding vector
            vector, embed_meta = generate_embeddings(chunk["content"], config)
            total_tokens += embed_meta.get("tokens", 0)
            
            chunk_id = f"{doc_id}_{idx}"
            cursor.execute("""
                INSERT INTO delta_document_chunks (chunk_id, doc_id, section, content, embedding_json, sequence_num)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                chunk_id,
                doc_id,
                chunk["section"],
                chunk["content"],
                json.dumps(vector),
                idx
            ))
            
        conn.commit()
        conn.close()
        
        latency = (time.time() - start_time) * 1000
        return {
            "status": "success",
            "doc_id": doc_id,
            "chunks_count": len(chunks),
            "latency_ms": latency,
            "tokens_embedded": total_tokens,
            "volume_path": f"dbfs:/Volumes/main/knowledge_store/raw_docs/{doc_name}"
        }
    
    # --- DIRECT PRODUCTION MODE ---
    else:
        # Databricks SDK integration
        from databricks.sdk import WorkspaceClient
        try:
            w = WorkspaceClient(
                host=config.get("databricks_host"),
                token=config.get("databricks_token")
            )
            # 1. Upload to Volume
            volume_path = f"/Volumes/{config.get('uc_catalog')}/{config.get('uc_schema')}/{config.get('uc_volume')}/{doc_name}"
            # Write stream to volume
            with w.files.upload(volume_path, file_content_bytes, overwrite=True) as f:
                pass
                
            # 2. Invoke local PySpark engine or API to append metadata to Delta
            # Under production, this triggers the Auto Loader pipeline notebooks.
            # For local UI connection, we mirror the local DB catalog updates so governance dashboard runs.
            res = upload_document_to_volume(doc_name, file_content_bytes, department, clearance_level, uploader_profile, {"simulation_mode": True})
            res["volume_path"] = f"dbfs:{volume_path}"
            return res
        except Exception as e:
            # Fallback and return error
            return {"status": "error", "message": f"Databricks upload failed: {e}"}

def cosine_similarity(v1, v2):
    """Calculates cosine similarity between two numeric vectors."""
    dot_product = sum(x*y for x,y in zip(v1, v2))
    mag1 = sum(x**2 for x in v1)**0.5
    mag2 = sum(x**2 for x in v2)**0.5
    if not mag1 or not mag2:
        return 0.0
    return dot_product / (mag1 * mag2)

def vector_search_query(query_text, user_profile, config=None, top_k=4):
    """
    Runs semantic similarity query against Vector Search Index.
    Applies security policies (RBAC & ABAC) dynamically to filter retrieved sources.
    Logs operations to the query audit trail Delta Table.
    """
    start_time = time.time()
    
    # 1. Generate Query Embeddings
    query_vector, embed_meta = generate_embeddings(query_text, config)
    tokens_used = embed_meta.get("tokens", 0)
    
    # 2. Check Simulation Mode
    if not config or config.get("simulation_mode", True):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Load all documents to check access rights first
        cursor.execute("SELECT * FROM delta_documents")
        all_docs = [dict(row) for row in cursor.fetchall()]
        
        # Security Policy Evaluator (ABAC/RBAC filters)
        allowed_doc_ids = []
        denied_doc_ids = []
        security_verdicts = {}
        
        for doc in all_docs:
            allowed, reason = evaluate_abac_policy(
                user_profile, 
                doc["department"], 
                doc["clearance_level"]
            )
            security_verdicts[doc["doc_id"]] = {
                "doc_name": doc["doc_name"],
                "allowed": allowed,
                "reason": reason,
                "department": doc["department"],
                "clearance_level": doc["clearance_level"]
            }
            if allowed:
                allowed_doc_ids.append(doc["doc_id"])
            else:
                denied_doc_ids.append(doc["doc_id"])
                
        # Retrieve chunks only for allowed documents
        retrieved_chunks = []
        if allowed_doc_ids:
            # Generate placeholder params
            placeholders = ",".join("?" for _ in allowed_doc_ids)
            query = f"SELECT * FROM delta_document_chunks WHERE doc_id IN ({placeholders})"
            cursor.execute(query, allowed_doc_ids)
            chunks = [dict(row) for row in cursor.fetchall()]
            
            # Compute similarity
            for c in chunks:
                c_vector = json.loads(c["embedding_json"])
                similarity = cosine_similarity(query_vector, c_vector)
                
                # Fetch matching document details
                doc_meta = next(d for d in all_docs if d["doc_id"] == c["doc_id"])
                retrieved_chunks.append({
                    "chunk_id": c["chunk_id"],
                    "doc_name": doc_meta["doc_name"],
                    "department": doc_meta["department"],
                    "clearance_level": doc_meta["clearance_level"],
                    "section": c["section"],
                    "content": c["content"],
                    "similarity": similarity
                })
                
            # Sort by similarity descending
            retrieved_chunks = sorted(retrieved_chunks, key=lambda x: x["similarity"], reverse=True)[:top_k]
            
        # Log to Audit table
        latency = (time.time() - start_time) * 1000
        
        # Compile Audit Summary Details
        audit_details = {
            "security_evaluations": security_verdicts,
            "retrieved_results": [
                {
                    "chunk_id": rc["chunk_id"],
                    "doc_name": rc["doc_name"],
                    "similarity": round(rc["similarity"], 4),
                    "section": rc["section"]
                } for rc in retrieved_chunks
            ]
        }
        
        status = "ACCESS_GRANTED" if retrieved_chunks else "NO_RESULTS_OR_ACCESS_DENIED"
        if denied_doc_ids and not retrieved_chunks:
            status = "ACCESS_DENIED_VIOLATION"
            
        cursor.execute("""
            INSERT INTO audit_query_logs (
                timestamp, user_id, user_role, query_text, status, 
                evaluated_docs_count, allowed_docs_count, denied_docs_count, 
                details_json, latency_ms, tokens_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_profile.get("user_id"),
            user_profile.get("role"),
            query_text,
            status,
            len(all_docs),
            len(allowed_doc_ids),
            len(denied_doc_ids),
            json.dumps(audit_details),
            latency,
            tokens_used
        ))
        
        conn.commit()
        conn.close()
        
        return retrieved_chunks, {
            "status": status,
            "evaluated_docs": len(all_docs),
            "allowed_docs": len(allowed_doc_ids),
            "denied_docs": len(denied_doc_ids),
            "latency_ms": latency
        }
        
    # --- DIRECT PRODUCTION MODE ---
    else:
        # Connect to Databricks Vector Search SDK
        from databricks.vector_search.client import VectorSearchClient
        try:
            # We assume user profile filters are applied as ABAC filters in vector search filter metadata
            # e.g., filter = {"department": user_profile["allowed_departments"]}
            vsc = VectorSearchClient(
                hosts=config.get("databricks_host"),
                token=config.get("databricks_token")
            )
            index_name = f"{config.get('uc_catalog')}.{config.get('uc_schema')}.{config.get('uc_index')}"
            index = vsc.get_index(endpoint_name=config.get("vector_search_endpoint"), index_name=index_name)
            
            # Format row-filter matching ABAC department attributes
            allowed_depts = user_profile.get("allowed_departments", [])
            filter_json = {"department": allowed_depts}
            
            # Execute search
            results = index.similarity_search(
                query_vector=query_vector,
                columns=["chunk_id", "doc_name", "department", "clearance_level", "section", "content"],
                filters=filter_json,
                num_results=top_k
            )
            
            # Parse result output formats
            parsed_chunks = []
            columns = results.get("manifest", {}).get("columns", [])
            for row in results.get("result", {}).get("data_array", []):
                item = dict(zip([c["name"] for c in columns], row))
                parsed_chunks.append({
                    "chunk_id": item.get("chunk_id"),
                    "doc_name": item.get("doc_name"),
                    "department": item.get("department"),
                    "clearance_level": item.get("clearance_level"),
                    "section": item.get("section"),
                    "content": item.get("content"),
                    "similarity": item.get("score", 0.85) # Databricks VS provides score
                })
                
            # Log audit trail locally too so the UI dashboard is populated
            sim_res, meta = vector_search_query(query_text, user_profile, {"simulation_mode": True}, top_k)
            meta["latency_ms"] = (time.time() - start_time) * 1000
            return parsed_chunks, meta
            
        except Exception as e:
            # Fallback to simulation
            sim_res, meta = vector_search_query(query_text, user_profile, {"simulation_mode": True}, top_k)
            meta["error"] = str(e)
            return sim_res, meta

def get_audit_trail():
    """Fetches full query audit logs from SQLite Delta Table."""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM audit_query_logs ORDER BY timestamp DESC", conn)
    conn.close()
    return df

def get_document_lineage():
    """Fetches list of registered documents representing Unity Catalog Lineage."""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM delta_documents ORDER BY upload_timestamp DESC", conn)
    conn.close()
    return df

def delete_all_data():
    """Wipes the simulated tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM delta_document_chunks")
    cursor.execute("DELETE FROM delta_documents")
    cursor.execute("DELETE FROM audit_query_logs")
    conn.commit()
    conn.close()
