import os
import time
import hashlib
import random
from openai import AzureOpenAI

def get_azure_openai_client(config):
    """Initializes and returns the Azure OpenAI client."""
    if not config or config.get("simulation_mode", True):
        return None
        
    try:
        client = AzureOpenAI(
            api_key=config.get("azure_openai_key"),
            api_version=config.get("azure_openai_version", "2024-02-15-preview"),
            azure_endpoint=config.get("azure_openai_endpoint")
        )
        return client
    except Exception as e:
        print(f"Error initializing Azure OpenAI client: {e}")
        return None

def generate_embeddings(text, config=None):
    """
    Generates embeddings for a given text.
    If in simulation mode or API setup fails, returns a deterministic mock vector of length 1536.
    """
    start_time = time.time()
    
    # Check if simulation mode is active
    if not config or config.get("simulation_mode", True):
        # Generate a deterministic mock embedding vector based on the hash of the text
        h = hashlib.sha256(text.encode('utf-8')).digest()
        random.seed(int.from_bytes(h[:4], byteorder='big'))
        mock_vector = [random.uniform(-1.0, 1.0) for _ in range(1536)]
        
        # Normalize vector
        magnitude = sum(x**2 for x in mock_vector)**0.5
        mock_vector = [x / magnitude for x in mock_vector]
        
        latency = (time.time() - start_time) * 1000
        return mock_vector, {"tokens": len(text.split()) * 1.3, "latency_ms": latency}

    client = get_azure_openai_client(config)
    if not client:
        # Fallback to simulation mode if client initialization fails
        return generate_embeddings(text, {"simulation_mode": True})

    try:
        deployment = config.get("azure_embeddings_deployment", "text-embedding-3-small")
        response = client.embeddings.create(
            input=[text],
            model=deployment
        )
        latency = (time.time() - start_time) * 1000
        vector = response.data[0].embedding
        tokens = response.usage.total_tokens
        return vector, {"tokens": tokens, "latency_ms": latency}
    except Exception as e:
        # Graceful fallback to mock vectors if network/auth fails
        mock_vec, meta = generate_embeddings(text, {"simulation_mode": True})
        meta["error"] = str(e)
        return mock_vec, meta

def generate_chat_completion(prompt, system_message, messages_history, context_chunks, config=None):
    """
    Generates grounded LLM response using Azure OpenAI (or simulated engine).
    Injects context_chunks into the prompt context for groundedness.
    """
    start_time = time.time()
    
    # Format system prompt with security and retrieved knowledge
    context_text = "\n\n".join([
        f"[Source: {chunk['doc_name']} | Department: {chunk['department']} | Page/Section: {chunk['section']}]\n{chunk['content']}"
        for chunk in context_chunks
    ])
    
    full_system_message = f"{system_message}\n\nHere is the retrieved grounded context. You MUST cite the source, section, or department when using these facts:\n\n{context_text}"
    
    # Compile messages
    messages = [{"role": "system", "content": full_system_message}]
    
    # Include history (up to last 10 messages for memory context)
    for msg in messages_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    # Append current user prompt
    messages.append({"role": "user", "content": prompt})

    # Simulation Mode
    if not config or config.get("simulation_mode", True):
        # High fidelity simulated generation
        simulated_response, confidence_score = simulate_response_generation(prompt, context_chunks)
        latency = (time.time() - start_time) * 1000
        
        prompt_tokens = sum(len(m["content"].split()) for m in messages) * 1.3
        completion_tokens = len(simulated_response.split()) * 1.3
        
        return {
            "content": simulated_response,
            "confidence_score": confidence_score,
            "tokens_used": int(prompt_tokens + completion_tokens),
            "latency_ms": latency,
            "model": "azure-openai/gpt-4o-simulated"
        }

    client = get_azure_openai_client(config)
    if not client:
        return generate_chat_completion(prompt, system_message, messages_history, context_chunks, {"simulation_mode": True})

    try:
        deployment = config.get("azure_llm_deployment", "gpt-4o")
        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
            temperature=config.get("temperature", 0.0),
            max_tokens=config.get("max_tokens", 800)
        )
        
        latency = (time.time() - start_time) * 1000
        output_text = response.choices[0].message.content
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        
        # Calculate confidence score based on keyword relevance
        confidence = calculate_simulation_confidence(output_text, context_chunks)
        
        return {
            "content": output_text,
            "confidence_score": confidence,
            "tokens_used": prompt_tokens + completion_tokens,
            "latency_ms": latency,
            "model": f"azure-openai/{deployment}"
        }
    except Exception as e:
        # Fallback to simulation with error info
        sim_res = generate_chat_completion(prompt, system_message, messages_history, context_chunks, {"simulation_mode": True})
        sim_res["error"] = str(e)
        return sim_res

def calculate_simulation_confidence(response, context_chunks):
    """Calculate dynamic confidence score based on response alignment with references."""
    if not context_chunks:
        return 0.1
    match_count = 0
    words = response.lower().split()
    for chunk in context_chunks:
        chunk_words = chunk['content'].lower().split()
        # count overlaps of key words
        overlap = len(set(words) & set(chunk_words))
        if overlap > 5:
            match_count += 1
            
    score = 0.5 + (match_count / len(context_chunks)) * 0.5
    return min(round(score, 2), 1.0)

def simulate_response_generation(prompt, context_chunks):
    """Simulates RAG reasoning process and prints realistic responses based on context files."""
    p_lower = prompt.lower()
    
    if not context_chunks:
        return "I apologize, but I do not have access to any grounded documentation containing details to answer that question. This may be due to security policies or lack of uploaded documents.", 0.0

    # Look for matching contexts
    hr_chunks = [c for c in context_chunks if c["department"] == "HR"]
    finance_chunks = [c for c in context_chunks if c["department"] == "Finance"]
    it_chunks = [c for c in context_chunks if c["department"] == "IT"]
    ops_chunks = [c for c in context_chunks if c["department"] == "Operations"]
    
    # 1. HR Query handling
    if hr_chunks and any(x in p_lower for x in ["leave", "holiday", "vacation", "review", "performance", "wfh", "home", "remote", "hybrid"]):
        response = "Based on the **HR Employee Handbook 2026** (Section: *Annual Leave & Time Off Policy* and *Flexible Hybrid Work Guidelines*):\n\n"
        
        if any(x in p_lower for x in ["leave", "holiday", "vacation"]):
            response += "- **Annual Leave:** Full-time employees are entitled to **20 days of paid annual leave** per calendar year, which accrues at **1.67 days per month**. Requests should be made **14 days in advance**.\n"
            response += "- **Carry Over:** A maximum of **5 unused days** can carry over, but they must be used by **March 31st** of the following year.\n"
            
        if any(x in p_lower for x in ["wfh", "home", "remote", "hybrid"]):
            response += "- **Hybrid Work Model:** Employees are required to work in the office a minimum of **3 days per week**. Remote work days (up to 2 days) must be aligned with the team manager.\n"
            response += "- **Stipend:** The handbook specifies a **$500 one-time stipend** for remote office ergonomic setups.\n"
            
        if any(x in p_lower for x in ["review", "performance", "cycle"]):
            response += "- **Performance Review Cycle:** Conducted twice per year. The **Mid-Year Review** is in **June**, and the **Year-End Review** occurs in **December** (determining salary adjustments and discretionary bonuses). Self-evaluations are due on the **10th** of the review month.\n"
            
        response += "\n*Citations:* [HR_Employee_Handbook_2026.pdf | Section 1 & Section 3]"
        return response, 0.95

    # 2. Finance Query handling
    if finance_chunks and any(x in p_lower for x in ["revenue", "budget", "cost", "variance", "financial", "expenditure", "profit", "efficiency"]):
        response = "According to the **Q1 Performance Statement** (stored in Unity Catalog/Delta Lake):\n\n"
        
        response += "- **Total Budget Target:** The total Q1 budget target across all departments was **$12,150,000**.\n"
        response += "- **Total Actual Spend:** The actual spending was **$11,890,000**, resulting in a favorable variance of **$260,000**.\n"
        
        if "it" in p_lower or "information technology" in p_lower:
            response += "- **IT Department Details:** The IT budget was targetted at **$3,400,000** with an actual cost of **$3,150,000**, representing a saving of **$250,000** and an efficiency rating of **92.6%**.\n"
        if "hr" in p_lower or "human resources" in p_lower:
            response += "- **HR Department Details:** HR was targetted at **$1,200,000** and spent **$1,150,000** (Variance: **$50,000**, Efficiency: **95.8%**).\n"
        if "marketing" in p_lower or "sales" in p_lower:
            response += "- **Marketing & Sales Details:** Budget was **$2,500,000** and they spent **$2,600,000** (an overspend of **$100,000**, Efficiency: **104.0%**).\n"
            
        response += "\n*Citations:* [Finance_Q1_Performance_Statement.xlsx | Sheet: Q1 Financial Summary]"
        return response, 0.98

    # 3. IT Security Query handling
    if it_chunks and any(x in p_lower for x in ["password", "mfa", "phishing", "security", "breach", "escalation", "incident"]):
        response = "According to the **IT Security Standard Operating Procedures & Incident Plan**:\n\n"
        
        if any(x in p_lower for x in ["password", "mfa"]):
            response += "- **Passwords:** Must be at least **14 characters** with uppercase, lowercase, numbers, and symbols. They must be changed every **365 days** and the last **5 passwords** cannot be reused.\n"
            response += "- **MFA/SSO:** Multi-Factor Authentication is **mandatory** for all logins (VPN, Azure, etc.) and Single Sign-On (SSO) must be integrated for all new tools.\n"
            
        if any(x in p_lower for x in ["phishing", "breach", "incident"]):
            response += "- **Incident Response Flow:** Users must report phishing via Outlook immediately. In case of a suspected breach, the system must be disconnected from the network (unplug ethernet/Wi-Fi) and the SOC hotline called at **ext. 911** or emailed at `soc@company.com`.\n"
            response += "- **Containment SLA:** The Incident Response Team initiates containment within **15 minutes**.\n"
            
        response += "\n*Citations:* [IT_Security_Incident_Response_Plan.docx | Sections 1 & 2]"
        return response, 0.96

    # 4. Operations / Generic Query handling
    if ops_chunks and any(x in p_lower for x in ["values", "conduct", "mission", "playbook", "frugality", "customer"]):
        response = "According to the **Company Operations Playbook**:\n\n"
        response += "- **Customer Obsession:** Starting with the customer and working backwards to earn and maintain trust.\n"
        response += "- **Frugality:** Constraints are highlighted as breeding resourcefulness and invention; achieving more with less.\n"
        response += "- **Standards of Conduct:** Reports of misconduct must be filed with HR or the Whistleblower Portal. Inquiries follow a **10-day SLA**.\n"
        response += "\n*Citations:* [Company_Operations_Playbook.pptx | Slide 2]"
        return response, 0.90

    # Default fallback using whatever chunks are present
    best_chunk = context_chunks[0]
    return f"Based on the retrieved document **{best_chunk['doc_name']}** (Section: *{best_chunk['section']}*):\n\n" \
           f"{best_chunk['content']}\n\n" \
           f"*Citations:* [{best_chunk['doc_name']} | Section: {best_chunk['section']}]", 0.85
