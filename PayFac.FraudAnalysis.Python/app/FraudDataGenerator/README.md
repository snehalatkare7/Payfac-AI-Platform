# FraudDataGenerator

Generates synthetic fraud case data and inserts it into the **PayFac Fraud Analysis** RAG table `synthetic_transactions`, so the app’s agents and `search_similar_transactions` can use it.

## Alignment with the app

- **Table**: `synthetic_transactions` (same as `app.rag.vector_store.VectorStore.TRANSACTIONS`).
- **Schema**: `id`, `embedding vector(1536)`, `content`, `metadata` (matches `vector_store.initialize_collections()` and Azure `text-embedding-3-small`).
- **Config**: Uses `.env` via `app.config.get_settings()`: `NEONDB_CONNECTION_STRING`; optional Azure OpenAI for real embeddings.

## Prerequisites

- Project dependencies installed (`pip install -r requirements.txt`).
- `.env` with at least `NEONDB_CONNECTION_STRING`.
- Optional: Azure OpenAI keys in `.env` for real 1536-dim embeddings (otherwise uses deterministic random embeddings).

## Usage

From the **project root**:

```bash
# Use .env (NEONDB_CONNECTION_STRING)
python -m app.FraudDataGenerator.fraud_data_generator --count 1000 --batch-size 100

# Override DSN
python -m app.FraudDataGenerator.fraud_data_generator --count 500 --dsn "postgresql://user:pass@host/db?sslmode=require"
```

- **--count**: Number of synthetic fraud cases to generate (default: 1000).
- **--batch-size**: Insert batch size (default: 100).
- **--dsn**: PostgreSQL connection string (overrides env).

The script ensures the `vector` extension and `synthetic_transactions` table exist, then inserts records. The app’s RAG (e.g. Fraud Detection Agent and `search_similar_transactions`) will use this data after you run the generator.

## Other files

- **schema.sql**: Optional standalone schema for the `fraud_cases` table (384-dim). The **app** uses only `synthetic_transactions` (1536-dim); this schema is for separate analytics if you want it.
- **sample_queries.sql**: Example queries for `fraud_cases` (if you use that table).
