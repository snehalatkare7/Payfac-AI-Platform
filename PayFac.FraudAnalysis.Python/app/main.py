"""PayFac Fraud Analysis AI Platform — FastAPI Application Entry Point.

This is the main application module that:
  1. Initializes all infrastructure (NeonDB, Redis, Kafka)
  2. Sets up the 3-tier memory system
  3. Initializes the RAG layer and Agentic RAG tools
  4. Creates the multi-agent orchestrator
  5. Registers API routes
  6. Manages application lifecycle (startup/shutdown)
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.infrastructure.neondb import NeonDbClient
from app.infrastructure.redis_client import RedisClient
from app.infrastructure.llm_client import LLMClient
from app.memory.manager import MemoryManager
from app.rag.vector_store import VectorStore
from app.rag.agentic_rag import init_agentic_rag
from app.kafka_bus.producer import KafkaProducer
from app.agents.orchestrator import OrchestratorAgent
from app.api.routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)

# Global application state (dependency injection container)
app_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Startup: Initialize all infrastructure and agent systems.
    Shutdown: Clean up connections gracefully.
    """
    settings = get_settings()
    logger.info("Starting PayFac Fraud Analysis Platform (%s)", settings.environment)

    # ── 1. Infrastructure Layer ───────────────────────────────────────

    # NeonDB (PostgreSQL + pgvector)
    neondb = NeonDbClient(settings.neondb_connection_string)
    await neondb.connect()
    app_state["neondb"] = neondb
    logger.info("✅ NeonDB connected")

    # Redis
    redis_client = RedisClient(settings.redis_url)
    await redis_client.connect()
    app_state["redis"] = redis_client
    logger.info("✅ Redis connected")

    # LLM Client (Azure OpenAI)
    llm_client = LLMClient()
    app_state["llm"] = llm_client
    logger.info("✅ LLM client initialized")

    # Kafka Producer
    kafka_producer = KafkaProducer(settings.kafka_bootstrap_servers)
    kafka_producer.connect()
    try:
        kafka_producer.ensure_topics_exist()
    except Exception as e:
        logger.warning("Kafka topic creation skipped: %s", e)
    app_state["kafka_producer"] = kafka_producer
    logger.info("✅ Kafka producer connected")

    # ── 2. Memory Layer (3-Tier) ──────────────────────────────────────

    memory = MemoryManager(neondb, redis_client, llm_client)
    await memory.initialize()
    app_state["memory"] = memory
    logger.info("✅ Memory system initialized (short-term + long-term + episodic)")

    # ── 3. RAG Layer ──────────────────────────────────────────────────

    vector_store = VectorStore(neondb, llm_client)
    await vector_store.initialize_collections()
    app_state["vector_store"] = vector_store
    logger.info("✅ Vector store initialized")

    # Initialize Agentic RAG tools with dependencies
    init_agentic_rag(vector_store, memory)
    logger.info("✅ Agentic RAG tools registered")

    # ── 4. Multi-Agent System ─────────────────────────────────────────

    orchestrator = OrchestratorAgent(llm_client, memory, kafka_producer)
    app_state["orchestrator"] = orchestrator
    logger.info("✅ Multi-agent orchestrator ready")

    logger.info("🚀 PayFac Fraud Analysis Platform is ready!")
    logger.info(
        "   Agents: Fraud Detection, Compliance, Risk Scoring, Investigation"
    )
    logger.info(
        "   Memory: Redis (short-term) + NeonDB (long-term + episodic)"
    )
    logger.info("   Events: Kafka (agent-to-agent communication)")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────
    logger.info("Shutting down PayFac Fraud Analysis Platform...")

    kafka_producer.close()
    await redis_client.close()
    await neondb.close()

    logger.info("Shutdown complete.")


# ── FastAPI Application ───────────────────────────────────────────────

app = FastAPI(
    title="PayFac Fraud Analysis AI Platform",
    description=(
        "Multi-agent AI platform for Payment Facilitator fraud analysis. "
        "Uses RAG, Agentic RAG, multi-agent orchestration, and 3-tier memory "
        "(Redis short-term, NeonDB long-term, vector episodic) with Kafka "
        "event streaming for agent-to-agent communication."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(router)
