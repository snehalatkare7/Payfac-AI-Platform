import os
import psycopg2
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import fitz  # PyMuPDF

# Load environment variables from .env file
load_dotenv()

PGVECTOR_URL = "postgresql://neondb_owner:npg_NwqA5n9YgkXl@ep-soft-heart-a85a6azm-pooler.eastus2.azure.neon.tech/neondb?sslmode=require&channel_binding=require"
PDF_DIR = 'PDFFiles'
MODEL_NAME = 'all-MiniLM-L6-v2'
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Connect to PostgreSQL
if not PGVECTOR_URL:
    raise ValueError("DATABASE_URL environment variable not set. Please set it to your PostgreSQL connection string.")
conn = psycopg2.connect(PGVECTOR_URL)
cursor = conn.cursor()

# Load embedding model
model = SentenceTransformer(MODEL_NAME)


# Helper: chunk text with overlap
def chunk_text(text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += chunk_size - chunk_overlap
    return chunks

# Helper: Insert embedding and metadata into pgvector
def insert_embedding(doc_id, embedding, text, page_number, source):
    cursor.execute(
        """
        INSERT INTO policy_documents (file_name, embedding, text, page_num, source)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (doc_id, embedding.tolist(), text, page_number, source)
    )
    conn.commit()

for filename in os.listdir(PDF_DIR):
    if filename.lower().endswith('.pdf'):
        pdf_path = os.path.join(PDF_DIR, filename)
        doc = fitz.open(pdf_path)
        all_chunks = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                chunks = chunk_text(text)
                for idx, chunk in enumerate(chunks):
                    chunk_id = f"{filename}-{page_num+1}-{idx}"
                    all_chunks.append({
                        'id': chunk_id,
                        'text': chunk,
                        'page_number': page_num + 1,
                        'source': pdf_path
                    })
        print(f"File: {filename} | Pages: {len(doc)} | Chunks: {len(all_chunks)}")
        for chunk in all_chunks:
            emb = model.encode(chunk['text'])
            insert_embedding(chunk['id'], emb, chunk['text'], chunk['page_number'], chunk['source'])
        print(f"Successfully processed {filename}.")

cursor.close()
conn.close()
print('All embeddings inserted successfully.')
