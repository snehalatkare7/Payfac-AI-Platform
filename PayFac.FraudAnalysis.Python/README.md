# PayFac Fraud Analysis AI Platform

## Overview
A sophisticated multi-agent AI platform for Payment Facilitator (PayFac) fraud analysis using advanced concepts:
- **RAG** (Retrieval-Augmented Generation) — contextual knowledge from vector embeddings
- **Agentic RAG** (Agent-driven adaptive retrieval) — agents autonomously decide what to retrieve
- **Multi-Agent System** (Specialized fraud agents with LangGraph orchestration)
- **Memory Management** (3-Tier: Redis short-term, NeonDB long-term, Vector episodic)
- **Agent-to-Agent Communication** (via Kafka event streaming and audit trails)
- **Vector Search** — pgvector on NeonDB for semantic fraud pattern and compliance document retrieval
- **Real-Time Velocity Tracking** — Redis sorted sets for transaction counting and BIN attack detection
- **Async Processing** — FastAPI with asyncio for concurrent agent operations

## Mission
Detect fraud across payment transactions using intelligent agent reasoning, compliance checking, risk scoring, and deep investigation for escalated cases.

## Architecture

### System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        PayFac Fraud Analysis AI Platform                         │
└──────────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────────┐
                              │   FastAPI Gateway   │
                              │    POST /v1/analyze │
                              └──────────┬──────────┘
                                         │
                                  Transaction JSON
                                         ▼
                  ┌──────────────────────────────────────────┐
                  │      Orchestrator Agent (LangGraph)      │
                  │  Coordinates multi-agent workflow       │
                  └──────────────────────────────────────────┘
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         ▼                               ▼                               ▼
    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
    │  Fraud Detection│         │ Compliance Agent│         │ Risk Scoring    │
    │  Agent          │         │ (Card Brands)   │         │ Agent           │
    │ (Agentic RAG)   │         │ (Agentic RAG)   │         │ (Aggregates)    │
    └────────┬────────┘         └────────┬────────┘         └────────┬────────┘
             │                           │                          │
             │ Stores result in Redis    │ Stores result in Redis   │ Reads from Redis
             ▼                           ▼                          ▼
    ┌──────────────────────────────────────────────────────────────────────────┐
    │                   Short-Term Memory (Redis)                              │
    │  • Session context (current_merchant, analysis_stage, etc.)             │
    │  • Chat history (last N messages)                                       │
    │  • Agent results (fraud_result, compliance_result, risk_result)         │
    │  • Velocity tracking (merchant transaction counts, BIN attacks)         │
    │  • TTL-based auto-expiry (default 1 hour)                               │
    └──────────────────────────────────────────────────────────────────────────┘
                                         │
                      Risk Score > 60 ?  │
                      ┌──────────┴─────────────────┐
                      │                           │
                    YES                          NO
                      ▼                           ▼
         ┌──────────────────────┐    ┌──────────────────────┐
         │ Investigation Agent  │    │ Aggregate Results &  │
         │ (Deep Dive)          │    │ Return FraudAlert    │
         │ (Agentic RAG)        │    └──────────────────────┘
         └──────────┬───────────┘                  │
                    │                             │
                    │ Recalls past episodes       │
                    └─────────┬────────────────────┘
                              ▼
            ┌─────────────────────────────────────────────────────────┐
            │     Agentic RAG Tool Layer (Adaptive Retrieval)         │
            │  • search_similar_transactions (fraud_cases table)      │
            │  • search_compliance_documents (compliance_documents)   │
            │  • search_fraud_patterns (fraud_patterns table)         │
            │  • recall_past_investigations (episodic memory)         │
            │  • get_merchant_history (long-term profile)            │
            │  • check_velocity (merchant/BIN transaction counts)     │
            │  • evaluate_retrieval_sufficiency (adaptive loop ctrl)  │
            └──────────┬──────────────────────────────────────────────┘
                       │ Embedding generation (384-dim)
                       ▼
            ┌─────────────────────────────────────────────────────────┐
            │         NeonDB (PostgreSQL + pgvector)                  │
            ├─────────────────────────────────────────────────────────┤
            │  Vector Collections (384-dim embeddings):               │
            │  • fraud_cases — historical fraud transactions          │
            │  • compliance_documents — Visa/Mastercard/Amex rules    │
            │  • fraud_patterns — known fraud signatures              │
            │  Indexes: ivfflat (lists=100) on all embeddings        │
            ├─────────────────────────────────────────────────────────┤
            │  Long-Term Memory Tables:                              │
            │  • merchant_risk_profiles — merchant history           │
            │  • learned_fraud_patterns — patterns learned           │
            │  • analysis_decisions — decision audit trail           │
            ├─────────────────────────────────────────────────────────┤
            │  Episodic Memory Table:                                │
            │  • episodic_memory — investigation episodes + vectors  │
            │  Used for: similar case retrieval                      │
            └─────────────────────────────────────────────────────────┘
                       │
                       ▼
            ┌─────────────────────────────────────────────────────────┐
            │         LLM Layer (OpenAI/Azure OpenAI)                │
            │  • Chat completion (reasoning + tool calling)          │
            │  • Embeddings (text-embedding-3-small / local)        │
            │  • Temperature: 0.1 (consistency)                      │
            │  • Max tokens: 4096                                    │
            └─────────────────────────────────────────────────────────┘
                       │
                       ▼
            ┌─────────────────────────────────────────────────────────┐
            │         Kafka Event Bus (Audit Trail & A2A Comms)       │
            │  Topics:                                               │
            │  • analysis_started — when workflow begins             │
            │  • fraud_detected — from fraud detection agent         │
            │  • compliance_result — from compliance agent           │
            │  • risk_score_calculated — from risk scoring           │
            │  • analysis_completed — final FraudAlert result        │
            │  • investigation_triggered — when escalated            │
            └─────────────────────────────────────────────────────────┘
                       │
                       ▼
            ┌─────────────────────────────────────────────────────────┐
            │         FraudAlert Response to FastAPI                 │
            │  {                                                      │
            │    "alert_id": "uuid",                                  │
            │    "merchant_id": "m-123",                              │
            │    "transaction_id": "txn-456",                         │
            │    "fraud_type": "card_testing",                        │
            │    "risk_level": "critical" (0-100 scale),            │
            │    "risk_score": 78,                                    │
            │    "summary": "Multi-line narrative",                   │
            │    "evidence": [...],                                   │
            │    "recommendations": [...],                            │
            │    "analyzed_by_agents": [fraud_det, compliance, ...], │
            │    "confidence": 0.92                                   │
            │  }                                                      │
            └─────────────────────────────────────────────────────────┘
```

### Data Flow: Request → Response

```
1. API Request
   POST /v1/analyze
   {transaction_id, merchant_id, amount_cents, card_brand, ...}
   
   ↓ (routes.py: analyze_transaction)
   
2. Create Transaction domain object
   Convert request to internal Transaction model with to_analysis_text()
   
   ↓ (orchestrator.py: analyze)
   
3. Create session & correlation IDs
   session_id: ties memory tiers for this request
   correlation_id: ties Kafka events across components
   
   ↓
   
4. Record session initialization
   • Store initial chat message in Redis short-term memory
   • Record transaction velocity event (merchant + BIN)
   • Publish ANALYSIS_STARTED event to Kafka
   
   ↓
   
5. LangGraph Workflow Execution
   
   5a. Fraud Detection Node (fraud_detection_agent.py)
       • Query: "Analyze this transaction for fraud..."
       • Available tools: search_similar, search_patterns, check_velocity, etc.
       • Agent autonomously calls tools until confident
       • Result stored in Redis (agent_result:fraud_detection)
       • Event published to Kafka (fraud_detected)
   
   5b. Compliance Check Node (compliance_agent.py)
       • Query: "Check compliance for {card_brand} rules"
       • Reads fraud_detection result from Redis
       • Searches compliance_documents via Agentic RAG
       • Building context from long-term memory (merchant profile)
       • Result stored in Redis (agent_result:compliance)
       • Event published to Kafka (compliance_result)
   
   5c. Risk Scoring Node (risk_scoring_agent.py)
       • Reads prior agent results from Redis
       • Synthesizes fraud score, compliance score, velocity, history
       • Produces numeric risk score (0-100) and risk level
       • Result stored in Redis (agent_result:risk_scoring)
       • Event published to Kafka (risk_score_calculated)
   
   5d. Conditional Routing
       • If risk_score > 60 → Investigation node
       • Else → Aggregate node
   
   5e. Investigation Node (conditional, investigation_agent.py)
       • Detailed deep-dive analysis for escalated cases
       • Recalls similar past investigations from episodic memory
       • Result stored (investigation_result)
   
   5f. Aggregate Node
       • Compile all agent outputs into FraudAlert
       • Record investigation episode in long-term memory
       • Update merchant risk profile in long-term memory
       • Publish ANALYSIS_COMPLETED event to Kafka
       • Clear session from Redis (free memory)

6. Return FraudAlert via API
   {alert_id, fraud_type, risk_score, evidence, recommendations, ...}
```

## Tech Stack

| Component            | Technology                                 | Purpose                                    |
|----------------------|--------------------------------------------|--------------------------------------------|
| **Language**         | Python 3.11+                               | Core runtime                               |
| **API Framework**    | FastAPI + Uvicorn                          | REST API gateway                           |
| **AI Orchestration** | LangChain (agents) + LangGraph (workflows) | Agent reasoning & LLM tools binding        |
| **LLM**              | Azure OpenAI GPT-4o or OpenAI GPT-4       | Agent chat completions                     |
| **Embeddings**       | text-embedding-3-small (OpenAI) / all-MiniLM-L6-v2 (local) | 384-dim for vector search |
| **Vector Database**  | NeonDB (PostgreSQL 15+ with pgvector)      | Semantic search on fraud/compliance data   |
| **Short-Term Memory** | Redis                                      | Session context, velocity tracking, caching |
| **Event Streaming**  | Apache Kafka (Confluent Cloud)             | Agent-to-agent comms, audit trail          |
| **Async Framework**  | asyncio (Python native)                    | Concurrent agent operations                |
| **HTTP Client**      | httpx / aiohttp (async)                    | LLM API calls                              |
| **Database Client**  | asyncpg (async PostgreSQL)                 | NeonDB connection pool                     |
| **Observability**    | Logging (Python native)                    | Component traces and operational visibility|

### Key Technology Decisions

1. **Async-First Design**: All I/O operations (DB, Redis, LLM, Kafka) are async to maximize concurrency and throughput.
2. **pgvector for Semantic Search**: 384-dimensional embeddings enable similarity search across fraud cases, compliance docs, and fraud patterns.
3. **Agentic RAG over Static RAG**: Agents decide what to retrieve (not upfront), enabling adaptive and efficient retrieval strategies.
4. **LangGraph Orchestration**: Provides stateful workflow with conditional branching (e.g., Investigation only if risk > 60).
5. **Redis for Velocity**: Sorted sets enable efficient time-windowed transaction counting for real-time fraud detection (e.g., BIN attacks).
6. **Kafka for Audit Trail**: All agent decisions are published as immutable events for compliance and downstream consumers.

## Core Concepts

### 1. Agentic RAG (Adaptive Retrieval)
Unlike traditional RAG which retrieves all context upfront, **Agentic RAG** lets agents autonomously decide:
- **WHAT** to search for (e.g., "similar card testing transactions", "Visa VDMP rules")
- **WHEN** to search (based on current confidence)
- **WHETHER** to iterate (retrieve more if insufficient evidence)

**Flow**: Agent reasons → decides tool is needed → calls search tool → evaluates results → decides if confident enough → produces analysis OR retrieves more data.

This reduces noise and enables deeper, more targeted analysis.

### 2. Multi-Agent Orchestration
The **Orchestrator Agent** (using LangGraph) coordinates a pipeline of specialized agents:
1. **Fraud Detection** → identifies fraud patterns
2. **Compliance** → checks regulatory rules
3. **Risk Scoring** → synthesizes findings into numeric score
4. **Investigation** (conditional) → deep dive if risk > 60

Each agent has its own system prompt, tools, and reasoning loop. They communicate via:
- **Redis** (within-session: agent results)
- **NeonDB** (historical: merchant profiles, past cases)
- **Kafka** (audit trail: published events)

### 3. 3-Tier Memory System

| Tier | Technology | Scope | Purpose |
|------|-----------|-------|---------|
| **Short-Term** | Redis | Session (ephemeral) | Active context, chat history, inter-agent state |
| **Long-Term** | NeonDB | Persistent | Merchant profiles, fraud history, decision audit |
| **Episodic** | NeonDB + Vector | Persistent (semantic) | Investigation episodes, case narratives, pattern recall |

**Build Agent Context**: Before an agent reasons, MemoryManager gathers context from all three tiers and formats it into a readable prompt. This enables agents to leverage both immediate session state and institutional knowledge.

### 4. Vector Search (pgvector)

All vector operations use **384-dimensional embeddings** generated by `all-MiniLM-L6-v2` (local, no API cost).

**Collections**:
- `fraud_cases` – 100K+ synthetic fraud transactions (embeds description field)
- `compliance_documents` – Visa VDMP, Mastercard ECM, Amex OptBlue, etc.
- `fraud_patterns` – Named patterns (card testing, transaction laundering, etc.)
- `episodic_memory` – Investigation episodes as narratives

**Search**: Cosine similarity with ivfflat indexes for fast approximate nearest neighbors.

### 5. Velocity Tracking (Real-Time)

**Redis sorted sets** track transaction timing per merchant and per BIN:
- **Merchant velocity**: How many transactions in last 60 minutes?
- **BIN velocity**: How many attempts with this card in last 5 minutes?

Used to detect:
- **Velocity abuse**: Sudden spike (200%+ normal) → suspend
- **BIN attacks**: Micro-transactions ($0.01–$1) in rapid succession → auto-block

### 6. Event Streaming (Kafka)

Every decision is published as an immutable event for:
- **Audit trail** (compliance)
- **Downstream processors** (e.g., real-time dashboards)
- **Feedback loops** (improve future decisions)

**Topics**:
- `analysis_started`
- `fraud_detected`
- `compliance_result`
- `risk_score_calculated`
- `analysis_completed`
- `investigation_triggered`

### 7. Feedback Loop for Learning

Analysts can provide feedback via `POST /v1/feedback`:
```json
{
  "decision_id": "alert-xyz",
  "was_correct": true,
  "feedback_notes": "Chargeback confirmed fraud. Analysis was accurate."
}
```

This feedback updates:
- Merchant risk profile (fraud history)
- Decision audit trail (for model tuning)
- Learned patterns (inform future agents)

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
cp .env.example .env
# Edit .env with your credentials

# 4. Initialize NeonDB schema
python -m scripts.init_neondb

# 5. Run the application
uvicorn app.main:app --reload --port 8000
```

## Project Structure & File Descriptions

```
PayFac.FraudAnalysis.Python/
│
├── app/
│   │
│   ├── main.py
│   │   ├─ FastAPI application entry point
│   │   ├─ Manages application lifecycle (startup/shutdown)
│   │   ├─ Initializes all infrastructure (NeonDB, Redis, Kafka, LLM)
│   │   ├─ Creates 3-tier memory system
│   │   ├─ Initializes vector store and Agentic RAG tools
│   │   ├─ Instantiates multi-agent orchestrator
│   │   ├─ Registers API routes
│   │   └─ Serves as dependency injection container (app_state)
│   │
│   ├── config.py
│   │   ├─ Pydantic Settings model for environment variables
│   │   ├─ Loads .env file using absolute path (project root)
│   │   ├─ Defines all configuration: API keys, DB URLs, TTLs
│   │   ├─ Provides get_settings() singleton cached function
│   │   └─ Used by all components for configuration
│   │
│   ├── agents/
│   │   │
│   │   ├── base_agent.py ⭐
│   │   │   ├─ Abstract base class for all agents
│   │   │   ├─ Key method: invoke() - runs agent with tool calling loop
│   │   │   ├─ Implements Agentic RAG loop: LLM → tool calls → results → repeat
│   │   │   ├─ Stores agent results in Redis short-term memory
│   │   │   ├─ Publishes events to Kafka
│   │   │   ├─ Adds session context from memory before reasoning
│   │   │   └─ Core execution: _execute_with_tools() iterative loop
│   │   │
│   │   ├── orchestrator.py ⭐
│   │   │   ├─ Orchestrator Agent using LangGraph state machine
│   │   │   ├─ Main entry: analyze(transaction) → calls all agents in sequence
│   │   │   ├─ Workflow nodes:
│   │   │   │   • fraud_detection → compliance_check → risk_scoring
│   │   │   │   • conditional: if risk > 60 → investigation
│   │   │   │   • aggregate (final results)
│   │   │   ├─ Creates session IDs for memory tying
│   │   │   ├─ Publishes ANALYSIS_STARTED and ANALYSIS_COMPLETED events
│   │   │   ├─ Records investigation episodes in episodic memory
│   │   │   ├─ Updates merchant risk profiles in long-term memory
│   │   │   └─ Returns final FraudAlert to API layer
│   │   │
│   │   ├── fraud_detection_agent.py ⭐
│   │   │   ├─ Specialized fraud analyst agent
│   │   │   ├─ Detects: card testing, BIN attacks, transaction laundering,
│   │   │   │   velocity abuse, synthetic identity, account takeover,
│   │   │   │   friendly fraud, cross-merchant collusion
│   │   │   ├─ Agentic RAG tools: search_similar_transactions,
│   │   │   │   search_fraud_patterns, check_velocity, get_merchant_history,
│   │   │   │   recall_past_investigations
│   │   │   ├─ Outputs: fraud_type, confidence (0-1), evidence[], recommendations[]
│   │   │   ├─ Publishes fraud_detected event to Kafka
│   │   │   └─ Result stored in Redis for compliance & risk agents to consume
│   │   │
│   │   ├── compliance_agent.py ⭐
│   │   │   ├─ Card brand compliance specialist
│   │   │   ├─ Monitors: Visa VDMP (dispute ratio), Visa VFMP (fraud ratio),
│   │   │   │   Mastercard ECM (chargeback merchant), BRAM (high-risk MCCs),
│   │   │   │   Amex OptBlue, PCI DSS
│   │   │   ├─ Agentic RAG tools: search_compliance_documents,
│   │   │   │   get_merchant_history, recall_past_violations
│   │   │   ├─ Outputs: is_compliant (bool), violations[] with severity levels
│   │   │   ├─ Reads fraud detection context via memory
│   │   │   ├─ Publishes compliance_result event to Kafka
│   │   │   └─ Identifies which brands/programs are affected
│   │   │
│   │   ├── risk_scoring_agent.py ⭐
│   │   │   ├─ Risk analyst that aggregates all findings
│   │   │   ├─ Reads fraud_result and compliance_result from Redis
│   │   │   ├─ Computes weighted score (0-100):
│   │   │   │   - Fraud Score (40% weight)
│   │   │   │   - Compliance Score (30% weight)
│   │   │   │   - Velocity Score (15% weight)
│   │   │   │   - Historical Score (15% weight)
│   │   │   ├─ Maps score to risk level: LOW/MEDIUM/HIGH/CRITICAL/SEVERE
│   │   │   ├─ Uses Agentic RAG for merchant history and velocity context
│   │   │   ├─ Outputs: risk_score (0-100), risk_level, factors[]
│   │   │   ├─ Publishes risk_score_calculated event to Kafka
│   │   │   └─ If score > 60, orchestrator triggers investigation
│   │   │
│   │   ├── investigation_agent.py ⭐
│   │   │   ├─ Deep investigation agent for escalated (high-risk) cases
│   │   │   ├─ Triggered only when risk_score > 60 (conditional routing)
│   │   │   ├─ Extensively uses episodic memory for similar past cases
│   │   │   ├─ Performs broader searches and pattern matching
│   │   │   ├─ Builds comprehensive narrative report
│   │   │   ├─ Outputs: case summary, investigation steps, evidence for/against,
│   │   │   │   historical precedents, final determination, recommendations
│   │   │   ├─ Agentic RAG allows multiple retrieval iterations
│   │   │   └─ Records investigation episode if needed
│   │   │
│   │   └── __init__.py
│   │       └─ Module initialization
│   │
│   ├── memory/
│   │   │
│   │   ├── manager.py ⭐
│   │   │   ├─ Unified facade over 3-tier memory system
│   │   │   ├─ Delegates to short_term, long_term, episodic
│   │   │   ├─ Key method: build_agent_context()
│   │   │   │   - Gathers short-term chat history
│   │   │   │   - Gathers prior agent results from same session
│   │   │   │   - Gathers merchant profile from long-term
│   │   │   │   - Recalls similar past investigations (episodic)
│   │   │   ├─ Key method: record_investigation_complete()
│   │   │   │   - Records episode in episodic memory
│   │   │   │   - Updates merchant profile in long-term
│   │   │   │   - Records decision for feedback loop
│   │   │   │   - Clears session from Redis
│   │   │   └─ Initialize method bootstraps long-term and episodic tables
│   │   │
│   │   ├── short_term.py ⭐
│   │   │   ├─ Redis-backed session-scoped memory
│   │   │   ├─ Stores: session context, chat history, agent results,
│   │   │   │   velocity tracking
│   │   │   ├─ All keys auto-expire via TTL (default 1 hour)
│   │   │   ├─ Velocity tracking uses Redis sorted sets with timestamps
│   │   │   │   (for efficient time-windowed counting)
│   │   │   ├─ Methods:
│   │   │   │   - store_session_context(session_id, key, value, ttl)
│   │   │   │   - get_session_context()
│   │   │   │   - add_chat_message() → append to Redis list
│   │   │   │   - get_chat_history(session_id, last_n)
│   │   │   │   - store_agent_result(session_id, agent_name, result)
│   │   │   │   - get_agent_result(session_id, agent_name)
│   │   │   │   - record_transaction_event() → sorted set insert
│   │   │   │   - get_velocity_count() → count in time window
│   │   │   │   - get_bin_velocity() → BIN-specific transaction counting
│   │   │   └─ Enables inter-agent communication within single session
│   │   │
│   │   ├── long_term.py
│   │   │   ├─ NeonDB-backed persistent memory
│   │   │   ├─ Stores: merchant_risk_profiles, learned_fraud_patterns,
│   │   │   │   analysis_decisions
│   │   │   ├─ Methods:
│   │   │   │   - get_merchant_profile(merchant_id)
│   │   │   │   - store_merchant_profile(profile)
│   │   │   │   - get_high_risk_merchants()
│   │   │   │   - record_decision(decision_id, merchant_id, fraud_type, etc.)
│   │   │   │   - update_decision_feedback(decision_id, was_correct, notes)
│   │   │   └─ Used for learning patterns and decision audit
│   │   │
│   │   ├── episodic.py ⭐
│   │   │   ├─ Vector-backed episodic memory in NeonDB
│   │   │   ├─ Stores investigation episodes with vector embeddings
│   │   │   ├─ Methods:
│   │   │   │   - initialize_table() → creates episodic_memory table
│   │   │   │   - record_episode(episode) → embeds and stores
│   │   │   │   - recall_similar_episodes(description, top_k) → vector search
│   │   │   ├─ Enables Investigation Agent to find similar past cases
│   │   │   ├─ Retrieval is semantic (e.g., "card testing with BIN sequencing")
│   │   │   └─ Uses 384-dim embeddings for vector similarity
│   │   │
│   │   └── __init__.py
│   │       └─ Module initialization
│   │
│   ├── rag/
│   │   │
│   │   ├── vector_store.py ⭐
│   │   │   ├─ High-level service wrapping NeonDbClient
│   │   │   ├─ Collections: fraud_cases, compliance_documents,
│   │   │   │   fraud_patterns (all with 384-dim pgvector)
│   │   │   ├─ Methods:
│   │   │   │   - initialize_collections() → creates tables + ivfflat indexes
│   │   │   │   - search_similar_fraud_cases(query, top_k, fraud_type, country)
│   │   │   │   - search_compliance_docs(query, card_brand)
│   │   │   │   - search_fraud_patterns(description, fraud_type)
│   │   │   │   - ingest_fraud_case(case_id, text, metadata)
│   │   │   │   - ingest_compliance_doc(chunk_id, text, metadata)
│   │   │   │   - ingest_fraud_pattern(pattern_id, text, metadata)
│   │   │   ├─ All embeddings generated automatically via LLMClient
│   │   │   └─ Cleaner API than raw NeonDbClient
│   │   │
│   │   ├── agentic_rag.py ⭐
│   │   │   ├─ Defines tool functions that agents can call
│   │   │   ├─ Adaptive retrieval: agents decide what to search for
│   │   │   ├─ Tools:
│   │   │   │   • search_similar_transactions() → fraud_cases table
│   │   │   │   • search_compliance_documents() → compliance docs
│   │   │   │   • search_fraud_patterns() → fraud patterns
│   │   │   │   • recall_past_investigations() → episodic memory
│   │   │   │   • get_merchant_history() → long-term profile
│   │   │   │   • check_velocity() → Redis velocity count
│   │   │   │   • evaluate_retrieval_sufficiency() → adaptive loop control
│   │   │   ├─ Each tool is decorated with @tool (LangChain)
│   │   │   ├─ Returns formatted text for agent consumption
│   │   │   ├─ Registered in main.py via init_agentic_rag()
│   │   │   └─ Enables agents to autonomously iterate on retrieval
│   │   │
│   │   ├── retriever.py
│   │   │   ├─ Standard RAG retriever (less used; for batch scenarios)
│   │   │   └─ Provides simpler retrieval without agent autonomy
│   │   │
│   │   └── __init__.py
│   │       └─ Module initialization
│   │
│   ├── kafka_bus/
│   │   │
│   │   ├── producer.py
│   │   │   ├─ Kafka producer for publishing events
│   │   │   ├─ Connects to Confluent Cloud (or local Kafka)
│   │   │   ├─ Methods:
│   │   │   │   - connect() → establish producer
│   │   │   │   - publish(event) → send to Kafka topic
│   │   │   │   - ensure_topics_exist() → auto-create topics
│   │   │   │   - close() → cleanup
│   │   │   └─ Publishes all agent decisions for audit trail
│   │   │
│   │   ├── consumer.py
│   │   │   ├─ Kafka consumer template (for downstream processors)
│   │   │   ├─ Listens on topics: analysis_started, fraud_detected,
│   │   │   │   compliance_result, risk_score_calculated, analysis_completed
│   │   │   └─ Can be used for real-time analytics or remediation actions
│   │   │
│   │   ├── events.py
│   │   │   ├─ Event schema definitions
│   │   │   ├─ AgentEvent base class with: event_type, correlation_id,
│   │   │   │   session_id, source_agent, payload
│   │   │   ├─ EventType enum: ANALYSIS_STARTED, FRAUD_DETECTED,
│   │   │   │   COMPLIANCE_RESULT, RISK_SCORE_CALCULATED, etc.
│   │   │   ├─ Factory functions: create_fraud_detected_event(),
│   │   │   │   create_compliance_result_event(), etc.
│   │   │   └─ Ensures consistent event publishing across agents
│   │   │
│   │   └── __init__.py
│   │       └─ Module initialization
│   │
│   ├── models/
│   │   │
│   │   ├── transaction.py
│   │   │   ├─ Transaction domain model (Pydantic)
│   │   │   ├─ Fields: transaction_id, merchant_id, amount_cents,
│   │   │   │   card_brand, card_bin, is_card_present, entry_mode,
│   │   │   │   ip_address, billing_country, etc.
│   │   │   ├─ Key method: to_analysis_text()
│   │   │   │   - Converts structured fields to readable narrative
│   │   │   │   - Used for LLM embeddings and reasoning
│   │   │   │   - Ex: "Transaction txn-123: Merchant FreshCart, $45.99 USD,
│   │   │   │     Visa ending 4242, Card-present..."
│   │   │   └─ Pass-through to analysis pipeline
│   │   │
│   │   ├── fraud_alert.py
│   │   │   ├─ FraudAlert domain model (final output)
│   │   │   ├─ Fields: alert_id, merchant_id, transaction_id, fraud_type,
│   │   │   │   risk_level, risk_score, summary, evidence[],
│   │   │   │   recommendations[], confidence, analyzed_by_agents[]
│   │   │   └─ Returned by orchestrator to API
│   │   │
│   │   ├── enums.py
│   │   │   ├─ Defines enumerations:
│   │   │   ├─ FraudType: CARD_TESTING, BIN_ATTACK, TRANSACTION_LAUNDERING,
│   │   │   │   VELOCITY_ABUSE, SYNTHETIC_IDENTITY, ACCOUNT_TAKEOVER,
│   │   │   │   FRIENDLY_FRAUD, CROSS_MERCHANT_COLLUSION, etc.
│   │   │   ├─ RiskLevel: LOW, MEDIUM, HIGH, CRITICAL, SEVERE
│   │   │   ├─ AgentRole: ORCHESTRATOR, FRAUD_DETECTION, COMPLIANCE,
│   │   │   │   RISK_SCORING, INVESTIGATION
│   │   │   ├─ CardBrand: VISA, MASTERCARD, AMEX, DISCOVER
│   │   │   ├─ InvestigationOutcome: CONFIRMED_FRAUD, FALSE_POSITIVE,
│   │   │   │   ESCALATED, MONITORING, RESOLVED
│   │   │   └─ MerchantRiskProfile, InvestigationEpisode, etc.
│   │   │
│   │   └── __init__.py
│   │       └─ Module initialization + exports
│   │
│   ├── api/
│   │   │
│   │   ├── routes.py ⭐
│   │   │   ├─ FastAPI router defining all REST endpoints
│   │   │   ├─ POST /v1/analyze
│   │   │   │   - Accepts AnalyzeTransactionRequest
│   │   │   │   - Calls orchestrator.analyze(transaction)
│   │   │   │   - Returns FraudAlertResponse
│   │   │   ├─ POST /v1/analyze/batch
│   │   │   │   - Batch version (multiple txns → multiple alerts)
│   │   │   ├─ GET /v1/merchants/{merchant_id}/risk-profile
│   │   │   │   - Retrieves long-term merchant risk profile
│   │   │   ├─ GET /v1/merchants/high-risk
│   │   │   │   - Lists all high-risk merchants
│   │   │   ├─ POST /v1/feedback
│   │   │   │   - Analyst provides feedback: was alert correct?
│   │   │   │   - Stored in long-term memory for learning
│   │   │   ├─ GET /health
│   │   │   │   - Returns NeonDB, Redis, Kafka connectivity status
│   │   │   └─ Dependency injection via get_orchestrator(), get_memory()
│   │   │
│   │   ├── schemas.py
│   │   │   ├─ Pydantic request/response models
│   │   │   ├─ AnalyzeTransactionRequest (single txn input)
│   │   │   ├─ FraudAlertResponse (single txn output)
│   │   │   ├─ BatchAnalyzeRequest / BatchAnalyzeResponse
│   │   │   ├─ MerchantRiskProfileResponse
│   │   │   ├─ FeedbackRequest
│   │   │   ├─ HealthResponse
│   │   │   └─ Input validation & serialization
│   │   │
│   │   └── __init__.py
│   │       └─ Module initialization
│   │
│   ├── infrastructure/
│   │   │
│   │   ├── neondb.py ⭐
│   │   │   ├─ Low-level NeonDB (PostgreSQL + pgvector) client
│   │   │   ├─ Wraps asyncpg connection pool
│   │   │   ├─ Methods:
│   │   │   │   - connect() → create pool, ensure pgvector extension
│   │   │   │   - close() → close pool
│   │   │   │   - vector_search(collection, query_embedding, top_k,
│   │   │   │       min_score, metadata_filter) → cosine similarity search
│   │   │   │   - upsert_vector(collection, record_id, embedding,
│   │   │   │       content, metadata) → INSERT ON CONFLICT
│   │   │   │   - execute_query(sql, args) → SELECT with results
│   │   │   │   - execute_command(sql, args) → DML/DDL
│   │   │   ├─ Handles vectorization and pgvector type casting
│   │   │   └─ Connection pooling for concurrency
│   │   │
│   │   ├── redis_client.py
│   │   │   ├─ Redis client for short-term memory
│   │   │   ├─ Methods:
│   │   │   │   - connect() → establish connection
│   │   │   │   - close() → disconnect
│   │   │   │   - set_json(key, value, ttl) → store with TTL
│   │   │   │   - get_json(key) → retrieve
│   │   │   │   - append_to_list(key, item, max_length) → chat history
│   │   │   │   - get_list(key, start, stop) → range retrieval
│   │   │   │   - add_to_sorted_set(key, item, score) → velocity tracking
│   │   │   │   - count_in_window(key, min_score, max_score) → time-windowed
│   │   │   │   - delete_pattern(pattern) → cleanup
│   │   │   └─ Async operations
│   │   │
│   │   ├── llm_client.py ⭐
│   │   │   ├─ Provides both chat and embedding models
│   │   │   ├─ Chat model: ChatOpenAI from LangChain
│   │   │   │   - Wraps OpenAI/Azure OpenAI API
│   │   │   │   - Used by agents for reasoning via LLM
│   │   │   │   - Temperature: 0.1 (deterministic)
│   │   │   │   - Max tokens: 4096
│   │   │   ├─ Embedding model: SentenceTransformer (all-MiniLM-L6-v2)
│   │   │   │   - Local—no API calls needed
│   │   │   │   - 384-dimensional embeddings
│   │   │   │   - L2 normalization for cosine similarity
│   │   │   │   - Used for: fraud_cases, compliance_docs, fraud_patterns,
│   │   │   │       episodic memory
│   │   │   ├─ Methods:
│   │   │   │   - generate_embedding(text) → 384-dim vector
│   │   │   │   - generate_embeddings(texts) → batch version with batching
│   │   │   └─ Lazy initialization (models loaded on first access)
│   │   │
│   │   └── __init__.py
│   │       └─ Module initialization
│   │
│   └── __init__.py
│       └─ Package marker
│
├── scripts/
│   │
│   ├── init_neondb.py ⭐
│   │   ├─ Database initialization script
│   │   ├─ Called once at deployment (python scripts.init_neondb)
│   │   ├─ Creates all vector tables with 384-dim indexes
│   │   ├─ Creates long-term and episodic memory tables
│   │   ├─ Seeds fraud patterns (7 pre-loaded)
│   │   ├─ Seeds compliance documents (5 pre-loaded per card brand)
│   │   ├─ Uses VectorStore for automated embedding generation
│   │   └─ Loads embedding model for initial ingestion
│   │
│   └── (other scripts as needed)
│
├── tests/
│   │
│   ├── test_agents.py
│   │   ├─ Unit tests for agent logic
│   │   └─ Integration tests for orchestrator
│   │
│   ├── test_memory.py
│   │   ├─ Tests for short-term, long-term, episodic memory
│   │   └─ Redis and NeonDB fixture tests
│   │
│   ├── test_rag.py
│   │   ├─ Tests for vector store operations
│   │   └─ Agentic RAG tool tests
│   │
│   └── test_kafka.py
│       ├─ Tests for event publishing
│       └─ Kafka producer tests
│
├── .env.example
│   └─ Template environment file (copy to .env and fill in credentials)
│
├── .env ⭐
│   ├─ Actual credentials (git-ignored)
│   ├─ OPENAI_API_KEY, NEONDB_CONNECTION_STRING,
│   │   REDIS_URL, KAFKA_BOOTSTRAP_SERVERS, etc.
│   └─ Loaded by config.py
│
├── requirements.txt
│   ├─ Python dependencies
│   ├─ Core: fastapi, langchain, langchain-openai, langgraph
│   ├─ Databases: asyncpg, redis, pgvector
│   ├─ Events: confluent-kafka
│   ├─ LLM: sentence-transformers, openai
│   └─ Dev: pytest, black, ruff
│
├── docker-compose.yml
│   ├─ Local development environment
│   ├─ Containers: Kafka, Redis, Zookeeper (if needed)
│   └─ Run: docker-compose up -d
│
└── README.md
    └─ This file—architecture, setup, and usage
```

## Quick Start

### Prerequisites
- Python 3.11+
- NeonDB instance (cloud or Docker)
- Redis instance
- Kafka/Confluent Cloud
- OpenAI API key (or Azure OpenAI)

### Setup

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
cp .env.example .env
# Edit .env with your actual credentials:
# - OPENAI_API_KEY
# - NEONDB_CONNECTION_STRING (e.g., postgresql://user:pass@host/db?sslmode=require)
# - REDIS_URL
# - KAFKA_BOOTSTRAP_SERVERS
# - KAFKA_SASL_USERNAME / KAFKA_SASL_PASSWORD

# 4. Initialize NeonDB schema
# (Creates vector tables, indexes, seeds fraud patterns & compliance docs)
python scripts/init_neondb.py

# 5. Run the application
uvicorn app.main:app --reload --port 8000

# 6. Visit docs
# Interactive API docs: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

### Local Development with Docker Compose

```bash
# Spin up Kafka + Redis locally (NeonDB still requires cloud/external instance)
docker-compose up -d

# Alternative: use docker-compose for full local stack if you have Postgres image
```

## API Usage

### Analyze a Single Transaction

```bash
curl -X POST http://localhost:8000/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn-12345",
    "merchant_id": "m-9876",
    "merchant_name": "FreshCart Grocery",
    "merchant_category_code": "5411",
    "amount_cents": 4599,
    "currency": "USD",
    "card_brand": "visa",
    "card_last_four": "4242",
    "card_bin": "411111",
    "is_card_present": true,
    "entry_mode": "chip",
    "billing_country": "US"
  }'
```

**Response**:
```json
{
  "alert_id": "alert-uuid-1",
  "merchant_id": "m-9876",
  "transaction_id": "txn-12345",
  "fraud_type": "no_fraud_detected",
  "risk_level": "low",
  "risk_score": 12,
  "summary": "Legitimate grocery transaction. No fraud indicators detected.",
  "evidence": [],
  "recommendations": ["APPROVE"],
  "confidence": 0.95,
  "analyzed_by_agents": ["fraud_detection", "compliance", "risk_scoring"],
  "analyzed_at": "2024-03-20T10:30:45.123Z"
}
```

### Batch Analyze

```bash
curl -X POST http://localhost:8000/v1/analyze/batch \
  -H "Content-Type: application/json" \
  -d '{
    "transactions": [
      { "transaction_id": "txn-1", ... },
      { "transaction_id": "txn-2", ... }
    ]
  }'
```

**Response**:
```json
{
  "total": 2,
  "alerts": [...],
  "high_risk_count": 1,
  "processing_time_ms": 3421
}
```

### Get Merchant Risk Profile

```bash
curl http://localhost:8000/v1/merchants/m-9876/risk-profile
```

**Response**:
```json
{
  "merchant_id": "m-9876",
  "merchant_name": "FreshCart Grocery",
  "mcc": "5411",
  "historical_fraud_count": 2,
  "chargeback_ratio": 0.0012,
  "average_risk_score": 18.3,
  "known_fraud_types": ["card_testing"],
  "is_high_risk": false,
  "last_review_date": "2024-03-15T14:22:00Z"
}
```

### List High-Risk Merchants

```bash
curl http://localhost:8000/v1/merchants/high-risk
```

### Submit Feedback

```bash
curl -X POST http://localhost:8000/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "decision_id": "alert-uuid-1",
    "was_correct": true,
    "feedback_notes": "Fraud confirmed. Merchant account closed."
  }'
```

### Health Check

```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "neondb_connected": true,
  "redis_connected": true,
  "kafka_connected": true
}
```

## Request/Response Flow Details

### How a Transaction is Analyzed

```
POST /v1/analyze
  ↓
AnalyzeTransactionRequest (validation)
  ↓
Transaction model + to_analysis_text()
  ↓
orchestrator.analyze(transaction)
  ├─ 1. Create session_id, correlation_id
  ├─ 2. Publish ANALYSIS_STARTED event
  ├─ 3. Record velocity in Redis
  ├─ 4. LangGraph executes workflow:
  │    ├─ a. Fraud Detection Node
  │    │     • Calls agentic_rag tools
  │    │     • Fetches from NeonDB vector store
  │    │     • Stores result in Redis
  │    │     • Publishes fraud_detected event
  │    ├─ b. Compliance Node
  │    │     • Reads fraud result from Redis
  │    │     • Searches compliance_documents
  │    │     • Publishes compliance_result event
  │    ├─ c. Risk Scoring Node
  │    │     • Reads both prior results from Redis
  │    │     • Synthesizes score
  │    │     • Publishes risk_score_calculated event
  │    ├─ d. Conditional: if score > 60?
  │    │     • YES → Investigation Node (escalate)
  │    │     • NO → Aggregate Node
  │    └─ e. Aggregate Node
  │         • Compile FraudAlert
  │         • Record episode in episodic memory
  │         • Update merchant profile
  │         • Publish ANALYSIS_COMPLETED event
  │         • Clear session from Redis
  ├─ 5. Return FraudAlert
  └─
FraudAlertResponse (transform)
  ↓
HTTP 200 + JSON body
```

## Fraud Detection Examples

### Card Testing Attack
**Scenario**: 10 transactions of $0.99 each with BIN 411111 from same IP in 2 minutes.

**Expected Flow**:
1. Fraud Detection searches `fraud_cases` for "card testing" & "micro transactions"
2. Finds similar past incidents
3. Checks BIN velocity in Redis (10 attempts in 2 min = HIGH)
4. Output: fraud_type=card_testing, confidence=0.92, risk_score → 75+
5. Investigation triggered (score > 60)
6. Alert: **BLOCK**

### Transaction Laundering
**Scenario**: Retail merchant processing $50K wire transfer with unusual entry mode.

**Expected Flow**:
1. Fraud Detection searches `fraud_cases` for "transaction laundering"
2. Compliance Agent searches for BRAM high-risk MCC violations
3. Risk Scoring finds merchant profile shows previous violations
4. Output: risk_score → 82+, violation="Transaction laundering suspected"
5. Investigation triggered
6. Episodic recall finds similar past cases with confirmed fraud
7. Alert: **ESCALATE** (recommend merchant review)

### Friendly Fraud on Recurring Payment
**Scenario**: Customer disputes a $19.99 recurring digital subscription charge (3rd month).

**Expected Flow**:
1. Fraud Detection checks merchant type (digital content)
2. Compliance checks Visa VDMP chargeback thresholds for this merchant
3. Long-term memory shows merchant has chargeback ratio near threshold
4. Risk Scoring aggregates: moderate fraud risk + compliance concern
5. Output: risk_score → 45 (borderline)
6. No investigation (score < 60, but flagged for monitoring)
7. Alert: **MONITOR & CONTACT CARDHOLDER**

## Development & Testing

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_agents.py

# With coverage
pytest --cov=app tests/

# Verbose output
pytest -v
```

### Local Development Notes

1. **Async debugging**: Use `asyncio-repl` for interactive testing
2. **LLM cost**: Use `OPENAI_API_KEY` with gpt-3.5-turbo for development (cheaper)
3. **Vector store**: On first run, embeddings are generated locally (5-10 mins for full init)
4. **Redis TTL**: Sessions auto-expire after 1 hour; adjust in config if needed
5. **Kafka topic**: Auto-created on first publish; check Confluent Cloud dashboard

## Deployment

### Docker Deployment

```dockerfile
# Example Dockerfile (provided in repo)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables (Production)

Ensure these are set before deploying:
- `OPENAI_API_KEY` – Azure OpenAI or OpenAI API key
- `NEONDB_CONNECTION_STRING` – PostgreSQL connection with pgvector
- `REDIS_URL` – Redis instance URL
- `KAFKA_BOOTSTRAP_SERVERS` – Kafka brokers
- `KAFKA_SASL_USERNAME` / `KAFKA_SASL_PASSWORD` – Kafka auth (if Confluent Cloud)
- `LOG_LEVEL` – INFO (production) or DEBUG (development)

### Monitoring & Observability

Enable logging in production:
```python
# logs/fraud_analysis.log captures all agent decisions
# Structured JSON logs for Datadog/ELK integration
# Kafka events serve as immutable audit trail
```

## Contributing

1. Fork the repo
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass: `pytest`
5. Submit a PR

## License

MIT License – see LICENSE file for details

## Support

For issues and questions:
- Open a GitHub issue
- Check existing documentation
- Review test cases for usage examples
