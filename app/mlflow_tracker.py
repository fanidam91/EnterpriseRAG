import os
import time
import uuid
import sqlite3
import json
from datetime import datetime
import pandas as pd

# Reuse simulated DB for MLflow tracking tables
from app.databricks_client import get_db_connection

def initialize_mlflow_db():
    """Sets up local tables representing the MLflow Experiment Tracking Server."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # MLflow runs metadata
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mlflow_runs (
            run_id TEXT PRIMARY KEY,
            experiment_name TEXT NOT NULL,
            run_name TEXT NOT NULL,
            status TEXT NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            user_id TEXT NOT NULL,
            model_name TEXT NOT NULL
        )
    """)
    
    # MLflow metrics (for visual tracking over time)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mlflow_metrics (
            run_id TEXT,
            timestamp TIMESTAMP NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            FOREIGN KEY (run_id) REFERENCES mlflow_runs(run_id) ON DELETE CASCADE
        )
    """)
    
    # MLflow parameters
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mlflow_params (
            run_id TEXT,
            param_name TEXT NOT NULL,
            param_value TEXT NOT NULL,
            PRIMARY KEY (run_id, param_name),
            FOREIGN KEY (run_id) REFERENCES mlflow_runs(run_id) ON DELETE CASCADE
        )
    """)
    
    # MLflow Artifact: RAG input/output traces
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mlflow_traces (
            run_id TEXT PRIMARY KEY,
            input_query TEXT NOT NULL,
            retrieved_context_json TEXT NOT NULL,
            output_response TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            FOREIGN KEY (run_id) REFERENCES mlflow_runs(run_id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

# Initialize MLflow database schema
initialize_mlflow_db()

def log_rag_run(query_text, system_message, output_data, retrieved_chunks, user_profile, config=None):
    """
    Logs model evaluation and metrics.
    If production mode is active, logs parameters and metrics to a remote Databricks MLflow tracking server.
    """
    start_time = datetime.now()
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    experiment_name = "Databricks_Enterprise_RAG_Assistant"
    run_name = f"rag_query_{start_time.strftime('%H%M%S')}"
    
    # Extract metrics from output data
    latency = output_data.get("latency_ms", 120.0)
    tokens = output_data.get("tokens_used", 150)
    confidence = output_data.get("confidence_score", 0.85)
    model = output_data.get("model", "azure-openai/gpt-4o")
    
    # Retrieve parameters
    temperature = config.get("temperature", 0.0) if config else 0.0
    max_tokens = config.get("max_tokens", 800) if config else 800
    top_k = config.get("top_k", 4) if config else 4
    sim_mode = config.get("simulation_mode", True) if config else True
    
    # 1. Log to Simulation SQL Database (always done to power local Dashboard visuals)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Insert Run
        cursor.execute("""
            INSERT INTO mlflow_runs (run_id, experiment_name, run_name, status, start_time, end_time, user_id, model_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, experiment_name, run_name, "FINISHED", 
            start_time.strftime("%Y-%m-%d %H:%M:%S"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_profile.get("user_id"), model
        ))
        
        # Insert Metrics
        metrics = [
            ("latency_ms", latency),
            ("tokens_used", tokens),
            ("confidence_score", confidence),
            ("retrieved_chunks_count", len(retrieved_chunks))
        ]
        for m_name, m_val in metrics:
            cursor.execute("""
                INSERT INTO mlflow_metrics (run_id, timestamp, metric_name, metric_value)
                VALUES (?, ?, ?, ?)
            """, (run_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), m_name, m_val))
            
        # Insert Params
        params = [
            ("temperature", str(temperature)),
            ("max_tokens", str(max_tokens)),
            ("retrieval_top_k", str(top_k)),
            ("system_prompt_length", str(len(system_message))),
            ("simulation_mode", str(sim_mode))
        ]
        for p_name, p_val in params:
            cursor.execute("""
                INSERT INTO mlflow_params (run_id, param_name, param_value)
                VALUES (?, ?, ?)
            """, (run_id, p_name, p_val))
            
        # Insert Trace Artifact
        cursor.execute("""
            INSERT INTO mlflow_traces (run_id, input_query, retrieved_context_json, output_response, confidence_score)
            VALUES (?, ?, ?, ?, ?)
        """, (
            run_id,
            query_text,
            json.dumps([
                {
                    "doc_name": rc["doc_name"],
                    "section": rc["section"],
                    "similarity": round(rc["similarity"], 4)
                } for rc in retrieved_chunks
            ]),
            output_data.get("content", ""),
            confidence
        ))
        
        conn.commit()
    except Exception as e:
        print(f"Failed to log to simulated MLflow DB: {e}")
    finally:
        conn.close()

    # 2. Log to Live MLflow server if Production Mode
    if not sim_mode:
        import mlflow
        try:
            # Set Tracking URI from config
            if config.get("databricks_host"):
                os.environ["MLFLOW_TRACKING_URI"] = "databricks"
                mlflow.set_tracking_uri("databricks")
            
            # Start run
            mlflow.set_experiment(f"/Users/{user_profile.get('user_id')}/{experiment_name}")
            with mlflow.start_run(run_name=run_name) as run:
                # Log Parameters
                mlflow.log_param("model_name", model)
                mlflow.log_param("temperature", temperature)
                mlflow.log_param("max_tokens", max_tokens)
                mlflow.log_param("top_k", top_k)
                mlflow.log_param("user_role", user_profile.get("role"))
                
                # Log Metrics
                mlflow.log_metric("latency_ms", latency)
                mlflow.log_metric("tokens_used", tokens)
                mlflow.log_metric("confidence_score", confidence)
                mlflow.log_metric("chunks_retrieved", len(retrieved_chunks))
                
                # Log Text input/output traces as an evaluation table
                eval_data = pd.DataFrame([{
                    "query": query_text,
                    "response": output_data.get("content", ""),
                    "confidence": confidence,
                    "retrieved_context": str([r["chunk_id"] for r in retrieved_chunks])
                }])
                mlflow.log_table(data=eval_data, artifact_file="rag_evaluation_table.json")
                
        except Exception as e:
            print(f"MLflow Live Logging Exception: {e}")
            
    return run_id

def get_mlflow_runs():
    """Fetches MLflow runs from SQLite simulator for reporting in UI."""
    conn = get_db_connection()
    df = pd.read_sql_query("""
        SELECT r.run_id, r.run_name, r.start_time, r.user_id, r.model_name,
               (SELECT metric_value FROM mlflow_metrics WHERE run_id = r.run_id AND metric_name = 'latency_ms') as latency_ms,
               (SELECT metric_value FROM mlflow_metrics WHERE run_id = r.run_id AND metric_name = 'tokens_used') as tokens_used,
               (SELECT metric_value FROM mlflow_metrics WHERE run_id = r.run_id AND metric_name = 'confidence_score') as confidence_score
        FROM mlflow_runs r
        ORDER BY r.start_time DESC
    """, conn)
    conn.close()
    return df

def get_mlflow_run_details(run_id):
    """Fetches full parameters, metrics history, and traces for a specific run."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get params
    cursor.execute("SELECT param_name, param_value FROM mlflow_params WHERE run_id = ?", (run_id,))
    params = {row["param_name"]: row["param_value"] for row in cursor.fetchall()}
    
    # Get metrics
    cursor.execute("SELECT metric_name, metric_value FROM mlflow_metrics WHERE run_id = ?", (run_id,))
    metrics = {row["metric_name"]: row["metric_value"] for row in cursor.fetchall()}
    
    # Get traces
    cursor.execute("SELECT * FROM mlflow_traces WHERE run_id = ?", (run_id,))
    trace_row = cursor.fetchone()
    trace = dict(trace_row) if trace_row else {}
    
    conn.close()
    return {"params": params, "metrics": metrics, "trace": trace}
