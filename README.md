# Databricks Enterprise Knowledge Assistant

A production-ready, secure, and fully auditable Enterprise RAG (Retrieval-Augmented Generation) Knowledge Assistant designed for high-governance industries. The solution leverages **Databricks Delta Lake**, **Unity Catalog**, **Vector Search**, **MLflow**, **Azure OpenAI GPT-4**, and a **Streamlit** user interface.

---

## Technical Architecture

```mermaid
graph TD
    %% Upload Pipeline
    subgraph Raw Ingestion (UC Volume)
        A[PDF/DOCX/XLSX/PPTX Upload] -->|Stream Ingestion| B[Unity Catalog Volume]
        B -->|CloudFiles Spark stream| C[Spark Ingestion Auto Loader]
    end

    %% Processing Pipeline
    subgraph Data Platform (Delta Lake & Unity Catalog)
        C -->|Pandas UDF Parsing| D[Delta Bronze Metadata Table]
        C -->|Chunking & Embeddings UDF| E[Delta Silver Chunks Table]
        E -->|Delta Sync Pipeline| F[Databricks Vector Search Endpoint]
    end

    %% RAG serving
    subgraph Model Registry & Serving
        G[MLflow PyFunc custom class] -->|Logs Run & Prompt| H[Unity Catalog Model Registry]
        H -->|Deploy Model| I[Databricks Serving REST API]
    end

    %% User Interaction
    subgraph User Dashboard Layer (Streamlit)
        J[Streamlit User Client] -->|Select User Profile| K{Auth Context: RBAC/ABAC}
        J -->|Search Query| L[Secure Search Broker]
        K -->|Inject Clearance Filters| L
        L -->|Query Vector Index| F
        F -->|Return Filtered Chunks| L
        L -->|Prompt + Context| M[Azure OpenAI Endpoint]
        M -->|Grounded Answer| J
        L -->|Audit Logs| N[Delta Audit Logs Table]
        L -->|MLflow Run telemetry| O[MLflow Tracking Database]
    end

    style K fill:#1E293B,stroke:#3B82F6,stroke-width:2px;
    style F fill:#1E293B,stroke:#10B981,stroke-width:2px;
    style N fill:#1E293B,stroke:#EF4444,stroke-width:2px;
    style O fill:#1E293B,stroke:#F59E0B,stroke-width:2px;
```

---

## Key Features

1. **Multi-Format Ingestion**: Fully extracts and processes structured and unstructured documents, including PDFs (Policies), DOCX (Manuals), XLSX (Budgets), and PPTX (Playbooks).
2. **Dual-Mode Serving Engine**:
   * **Simulation Mode**: Run the full workspace locally using an in-memory/SQLite database modeling Delta Lake structures, complete with a vector cosine-similarity search engine in Python. Excellent for frictionless demonstrations and interviews.
   * **Direct Production Mode**: Direct REST connectors to active Databricks clusters, Unity Catalog Volumes, Databricks Vector Search indexes, and Azure OpenAI API endpoints.
3. **RBAC & ABAC Security Model**: Employs fine-grained row-level filters matching user role attributes (departments, security clearances) against document metadata.
4. **Delta Audit Trail**: Logs every single search interaction (user details, query content, security filtering results, access clearance logs, latency, token consumption) to simulated or live System Audit tables.
5. **MLflow MLOps Tracking**: Registers prompt structures, generation latencies, token counts, and input/output evaluation traces, supporting complete reproducibility and model governance.

---

## Directory Structure

```
EnterpriseRAGChat/
├── app/
│   ├── main.py                     # Streamlit Main App entry point
│   ├── auth.py                     # Security, RBAC/ABAC User context configuration
│   ├── databricks_client.py         # Real/Mock Databricks API integration (Vector Search, UC)
│   ├── openai_client.py            # Azure OpenAI integration (GPT-4 completions & embeddings)
│   ├── mlflow_tracker.py           # MLflow tracking client (logging params, metrics, traces)
│   ├── utils.py                    # PDF/text processing and UI helper utilities
│   └── pages/
│       ├── 01_Upload_Documents.py   # Page: File ingestion, chunking, Delta Lake lineage
│       ├── 02_Governance_&_Audit.py # Page: UC schemas, ABAC policies, Query Audit Trail, Delta Lineage
│       └── 03_System_Settings.py   # Page: Cloud configs, API keys, Toggle Sim Mode
├── notebooks/
│   ├── 01_UC_and_Delta_Setup.py    # Databricks: Unity Catalog, external volumes, Delta schemas
│   ├── 02_Document_Ingestion.py    # Databricks: PySpark pipeline for auto-loader ingestion
│   ├── 03_Vector_Search_Setup.py   # Databricks: Vector Search index setup and endpoints
│   └── 04_MLflow_RAG_Deployment.py # Databricks: MLflow PyFunc model registration and deployment
├── scripts/
│   └── generate_sample_docs.py     # Script to generate sample files (PDF, DOCX, XLSX, PPTX)
├── data/                           # Directory to store sample files
│   └── (Generated sample files)
├── requirements.txt                # Python dependencies
├── deployment_instructions.md      # Step-by-step production cloud deployment instructions
└── README.md                       # Main README with diagrams and deployment instructions
```

---

## Quickstart Guide (Local Sandbox Mode)

You can spin up a local simulated sandbox environment of the entire RAG pipeline in under **2 minutes**:

### 1. Set Up Your Local Environment
Clone the repository and install all required python libraries:
```bash
pip install -r requirements.txt
```

### 2. Generate Sample Documents
Run the script to programmatically create realistic sample corporate documents:
```bash
python scripts/generate_sample_docs.py
```
This builds four file formats inside a newly created `data/` folder:
* `HR_Employee_Handbook_2026.pdf` (HR Department - Confidential Clearance)
* `Finance_Q1_Performance_Statement.xlsx` (Finance Department - Confidential Clearance)
* `IT_Security_Incident_Response_Plan.docx` (IT Department - Confidential Clearance)
* `Company_Operations_Playbook.pptx` (Operations Department - Public Clearance)

### 3. Start the Streamlit Application
Launch the frontend dashboard:
```bash
streamlit run app/main.py
```

### 4. Pre-populate the Database Sandbox
1. Go to the **System Settings** page (`03_System_Settings`) using the sidebar.
2. In the **Simulated Sandbox Manager** section, click **Pre-populate Sandbox Database**.
3. The app will parse, chunk, embed, and load all 4 documents into the local SQLite database.

---

## Demonstrating Security Governance & Audit Trails

To showcase this application for senior leadership, customer demos, or interviews, follow this script:

### Scenario A: Testing Security Clearance (ABAC)
1. Navigate back to the main chat interface (**Chat**).
2. Select **Sarah Jenkins (HR Manager)** as the active user from the sidebar dropdown.
3. Query: *"What is the annual leave and work from home policy?"*
   * *Outcome:* Sarah is authorized. The system successfully displays details from `HR_Employee_Handbook_2026.pdf` with citations.
4. Now, switch the active user to **David Miller (Finance Analyst)**. Ask the same question.
   * *Outcome:* David does not have clearance for HR documents. The search query blocks HR chunks at the query layer. The model responds that it does not have access to that information.

### Scenario B: Testing Role-Based Contexts (RBAC)
1. Select **Elena Rostova (Executive VP)** as the active user. Ask: *"Compare the IT budget variance with the HR budget variance."*
   * *Outcome:* Elena has Secret level clearance across all departments. The system retrieves details from `Finance_Q1_Performance_Statement.xlsx` and reports the variances ($250k under for IT, $50k under for HR).
2. Now, switch the active user to **John Doe (General Contractor)**. Ask the same question.
   * *Outcome:* John only has access to the Operations department with Public clearance. The system filters out the Finance document, reporting an access block.

### Scenario C: Reviewing Audit Trails & Compliance
1. Go to the **Governance & Audit** tab.
2. Under the **Unity Catalog Access Audit Logs** tab, review the Plotly charts mapping allowed vs. blocked requests.
3. Inspect the audit logs table, which captures the exact timestamp, active user role, user query, and the security verdict (e.g., `ACCESS_GRANTED`, `ACCESS_DENIED_VIOLATION`).
4. Go to the **MLflow Experiment Tracking** tab. Select the latest run ID to view the logged parameters, evaluation metrics (latency and tokens), and the exact prompt input/output trace paths.
