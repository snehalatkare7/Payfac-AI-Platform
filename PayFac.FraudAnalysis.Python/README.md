# PayFac Fraud Analysis AI Platform

## Overview
A multi-agent AI platform for Payment Facilitator (PayFac) fraud analysis using advanced concepts:
- **RAG** (Retrieval-Augmented Generation)
- **Agentic RAG** (Agent-driven adaptive retrieval)
- **Multi-Agent System** (Specialized fraud agents with orchestration)
- **Memory Management** (Short-term via Redis, Long-term via NeonDB, Episodic via vector embeddings)
- **Agent-to-Agent Communication** (via Kafka event streaming)
- **Kafka** for async event-driven agent communication and audit trails
- **Redis** for session state, caching, and short-term memory

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   PayFac Fraud Analysis AI Platform                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────────────┐       │
│  │ Orchestrator │   │  FastAPI     │   │   Streamlit / React   │       │
│  │   Agent      │◄──┤  Gateway     │◄──┤   Dashboard           │       │
│  └──────┬───────┘   └──────────────┘   └───────────────────────┘       │
│         │                                                               │
│  ┌──────┼──────────────────────────────────────────────────┐           │
│  │      ▼              ▼              ▼           ▼        │           │
│  │ ┌──────────┐  ┌──────────┐  ┌───────────┐ ┌─────────┐  │           │
│  │ │ Fraud    │  │Compliance│  │ Risk      │ │Investig.│  │           │
│  │ │ Detection│  │ Agent    │  │ Scoring   │ │ Agent   │  │           │
│  │ │ Agent    │  │          │  │ Agent     │ │         │  │           │
│  │ └────┬─────┘  └────┬─────┘  └────┬──────┘ └────┬────┘  │           │
│  │      │              │              │             │      │           │
│  │      ▼              ▼              ▼             ▼      │           │
│  │  ┌──────────────────────────────────────────────────┐   │           │
│  │  │            Kafka Event Bus (A2A Comms)           │   │           │
│  │  └──────────────────────────────────────────────────┘   │           │
│  └─────────────────────────────────────────────────────────┘           │
│         │              │              │                                 │
│         ▼              ▼              ▼                                 │
│  ┌─────────────────────────────────────────────┐                       │
│  │        Memory Management Layer              │                       │
│  │  ┌───────────┐ ┌────────────┐ ┌──────────┐  │                       │
│  │  │Short Term │ │Long Term   │ │Episodic  │  │                       │
│  │  │(Redis)    │ │(NeonDB/PG) │ │(NeonDB)  │  │                       │
│  │  └───────────┘ └────────────┘ └──────────┘  │                       │
│  └─────────────────────────────────────────────┘                       │
│         │              │              │                                 │
│         ▼              ▼              ▼                                 │
│  ┌─────────────────────────────────────────────┐                       │
│  │       RAG / Agentic RAG Layer               │                       │
│  │  ┌────────────────┐  ┌──────────────────┐   │                       │
│  │  │ NeonDB Vector  │  │  Azure OpenAI /  │   │                       │
│  │  │ Store           │  │  OpenAI LLM      │   │                       │
│  │  │ • Transactions  │  └──────────────────┘   │                       │
│  │  │ • Compliance    │                         │                       │
│  │  │ • Fraud Patterns│                         │                       │
│  │  └────────────────┘                          │                       │
│  └─────────────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Component            | Technology                          |
|----------------------|-------------------------------------|
| Language             | Python 3.11+                        |
| AI Framework         | LangChain + LangGraph               |
| LLM                  | Azure OpenAI GPT-4o                 |
| Vector DB            | NeonDB (PostgreSQL + pgvector)      |
| Short-Term Memory    | Redis                               |
| Event Streaming      | Apache Kafka (confluent-kafka)      |
| API Framework        | FastAPI                             |
| Embeddings           | text-embedding-3-small              |
| Observability        | OpenTelemetry                       |

## Quick Start

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

## Project Structure

```
PayFac.FraudAnalysis.Python/
├── app/
│   ├── main.py                          # FastAPI entry point
│   ├── config.py                        # Configuration / settings
│   ├── agents/                          # Multi-Agent System
│   │   ├── __init__.py
│   │   ├── orchestrator.py              # Orchestrator Agent (LangGraph)
│   │   ├── fraud_detection_agent.py     # Fraud Detection Specialist
│   │   ├── compliance_agent.py          # Card Brand Compliance Expert
│   │   ├── risk_scoring_agent.py        # Risk Scoring Analyst
│   │   ├── investigation_agent.py       # Deep Investigation Agent
│   │   └── base_agent.py               # Base Agent class
│   ├── memory/                          # 3-Tier Memory System
│   │   ├── __init__.py
│   │   ├── manager.py                   # Unified Memory Manager
│   │   ├── short_term.py               # Redis-backed short-term
│   │   ├── long_term.py                # NeonDB-backed long-term
│   │   └── episodic.py                 # Vector-backed episodic
│   ├── rag/                            # RAG & Agentic RAG
│   │   ├── __init__.py
│   │   ├── vector_store.py             # NeonDB pgvector integration
│   │   ├── retriever.py               # Standard RAG retriever
│   │   └── agentic_rag.py             # Agentic RAG (adaptive retrieval)
│   ├── kafka_bus/                      # Kafka Event Bus (A2A)
│   │   ├── __init__.py
│   │   ├── producer.py                # Kafka producer
│   │   ├── consumer.py                # Kafka consumer
│   │   └── events.py                  # Event schema definitions
│   ├── models/                         # Domain Models
│   │   ├── __init__.py
│   │   ├── transaction.py
│   │   ├── fraud_alert.py
│   │   ├── risk_score.py
│   │   └── enums.py
│   ├── api/                            # API Endpoints
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── schemas.py
│   └── infrastructure/                 # External integrations
│       ├── __init__.py
│       ├── neondb.py                   # NeonDB connection
│       ├── redis_client.py             # Redis connection
│       └── llm_client.py              # Azure OpenAI client
├── scripts/
│   └── init_neondb.py                  # DB initialization
├── tests/
│   ├── test_agents.py
│   ├── test_memory.py
│   ├── test_rag.py
│   └── test_kafka.py
├── .env.example
├── requirements.txt
├── docker-compose.yml                  # Kafka + Redis local dev
└── README.md
```
