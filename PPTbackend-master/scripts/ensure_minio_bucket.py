"""
Create MinIO bucket ai-teacher if not exists (for local RAGFlow Docker).
Run from PPTbackend-master:  python scripts/ensure_minio_bucket.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000").strip().replace("http://", "").replace("https://", "")
access = os.getenv("MINIO_ACCESS_KEY", "rag_flow").strip()
secret = os.getenv("MINIO_SECRET_KEY", "infini_rag_flow").strip()
bucket = os.getenv("MINIO_BUCKET_NAME", "ai-teacher").strip()
secure = os.getenv("MINIO_SECURE", "false").strip().lower() == "true"

try:
    from minio import Minio
    client = Minio(endpoint, access_key=access, secret_key=secret, secure=secure)
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        print("OK: bucket created:", bucket)
    else:
        print("OK: bucket exists:", bucket)
except Exception as e:
    print("ERROR:", e)
    sys.exit(1)
