import os
import psycopg2
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import fitz  # PyMuPDF
import re
import uuid

# Load environment variables
load_dotenv()

PGVECTOR_URL = os.environ.get("DATABASE_URL")

PDF_DIR = os.path.join(os.path.dirname(__file__), "PDFFiles")

MODEL_NAME = "all-MiniLM-L6-v2"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# ---------------------------
# DB CONNECTION
# ---------------------------

if not PGVECTOR_URL:
    raise ValueError("PGVECTOR_URL not set in environment")


def insert_policies_from_pdfs(pdf_dir=PDF_DIR):
    if not os.path.exists(pdf_dir):
        print(f"PDF directory not found: {pdf_dir}")
        return False

    conn = psycopg2.connect(PGVECTOR_URL)
    cursor = conn.cursor()
    model = SentenceTransformer(MODEL_NAME)

# ---------------------------
# CHUNK TEXT WITH OVERLAP
# ---------------------------

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


# ---------------------------
# DETECT BRAND FROM FILE NAME
# ---------------------------

def detect_brand(filename):

    name = filename.lower()

    if "visa" in name:
        return "visa"

    if "mastercard" in name:
        return "mastercard"

    return "unknown"


# ---------------------------
# EXTRACT RULE METADATA
# ---------------------------

def extract_rule_metadata(text):

    text_lower = text.lower()

    # rule id detection (like 5.4.1)
    rule_match = re.search(r'\b\d+(\.\d+)+\b', text)

    if rule_match:
        rule_id = rule_match.group()
    else:
        rule_id = str(uuid.uuid4())

    # rule type detection
    rule_type = "general"

    if "chargeback" in text_lower:
        rule_type = "chargeback"

    elif "fraud" in text_lower:
        rule_type = "fraud"

    elif "authorization" in text_lower:
        rule_type = "authorization"

    elif "settlement" in text_lower:
        rule_type = "settlement"

    # category detection
    category = "transaction_processing"

    if "dispute" in text_lower:
        category = "dispute"

    elif "fraud monitoring" in text_lower:
        category = "fraud"

    elif "authorization" in text_lower:
        category = "authorization"

    return rule_id, rule_type, category


# ---------------------------
# INSERT RULE INTO PGVECTOR
# ---------------------------

def insert_rule(rule_id, brand, rule_type, category, rule_text, embedding):

    cursor.execute(
        """
        INSERT INTO policy_rules
        (rule_id, brand, rule_type, category, rule_text, embedding)
        VALUES (%s,%s,%s,%s,%s,%s)
        """,
        (
            rule_id,
            brand,
            rule_type,
            category,
            rule_text,
            embedding.tolist()
        )
    )

    conn.commit()


# ---------------------------
# PROCESS PDF FILE
# ---------------------------

    for filename in os.listdir(pdf_dir):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(pdf_dir, filename)
            brand = detect_brand(filename)
            doc = fitz.open(pdf_path)
            all_chunks = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    chunks = chunk_text(text)
                    for idx, chunk in enumerate(chunks):
                        all_chunks.append({
                            "text": chunk,
                            "page_number": page_num + 1
                        })
            print(f"File: {filename} | Pages: {len(doc)} | Chunks: {len(all_chunks)}")
            for chunk in all_chunks:
                rule_id, rule_type, category = extract_rule_metadata(chunk["text"])
                embedding = model.encode(chunk["text"])
                insert_rule(
                    rule_id,
                    brand,
                    rule_type,
                    category,
                    chunk["text"],
                    embedding
                )
            print(f"Successfully processed {filename}")
    cursor.close()
    conn.close()
    print("All rules inserted successfully.")
    return True
