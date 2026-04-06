"""
Initialization script (Seeder) for the RAG module.
1. Takes raw fragments of the EUDR regulation.
2. Extracts their embeddings using Oxlo's 'bge-large' model.
3. Saves them into the Supabase database.

Execution: python scripts/seed_eudr_rag.py
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path

# Add project root to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import settings
from services.supabase_client import SupabaseService
import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_eudr")

# Mock chunks from the EUDR to inject into the Vector DB.
# In production, this should be extracted by processing the EUDR PDF document.
EUDR_CHUNKS = [
    "Regulation (EU) 2023/1115 (EUDR) Article 3 (1): Relevant commodities and relevant products shall not be placed or made available on the market or exported, unless all the following conditions are fulfilled: (a) they are deforestation-free; (b) they have been produced in accordance with the relevant legislation of the country of production; and (c) they are covered by a due diligence statement.",
    "EUDR Deforestation Cutoff Rule (Article 3.1): Deforestation means the conversion of forest to agricultural use, whether human-induced or not. For the purposes of this Regulation, commodities MUST NOT originate from land that has been deforested after December 31, 2020.",
    "EUDR Article 4: Due diligence systems must include information on geolocation coordinates of all plots of land where the relevant commodities were produced. The coordinates must be precise polygons if the land is over 4 hectares.",
    "EUDR Annex I: Relevant commodities include cattle, cocoa, coffee, palm oil, soya, wood, rubber, and derived products. If a farm produces Coffee or Cocoa, it is strictly subject to the 2020 deforestation cutoff date.",
    "EUDR Article 10: Member States shall designate competent authorities responsible for applying this Regulation and carrying out official controls. They may penalise non-compliance by confiscating the commodities or blocking market access."
]

def generate_embedding(text: str) -> list[float]:
    """Calls the Oxlo.ai embeddings API"""
    if not settings.oxlo_configured:
        raise ValueError("Missing OXLO_API_KEY in .env to generate embeddings.")
        
    url = f"{settings.oxlo_base_url.rstrip('/')}/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.oxlo_api_key}"
    }
    payload = {
        "model": settings.oxlo_embedding_model,
        "input": text
    }
    
    with httpx.Client(timeout=15.0) as client:
        res = client.post(url, headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()
        return data["data"][0]["embedding"]

def seed_database():
    supabase = SupabaseService()
    if not supabase._client:
        logger.error("Could not initialize Supabase. Check SUPABASE_URL and SUPABASE_ANON_KEY in .env")
        return
        
    logger.info("Connected to Supabase. Starting insertion of %d EUDR chunks...", len(EUDR_CHUNKS))
    
    # Clean the table first (Optional, for persistent testing)
    try:
        # In supabase python there is no delete all without an empty filter or match, so we delete if id > 0
        supabase._client.table("eudr_documents").delete().gt("id", 0).execute()
        logger.info("Table 'eudr_documents' cleared.")
    except Exception as exc:
        logger.warning(f"Could not clear table, it might be empty or RLS prevents Delete: {exc}")

    for idx, chunk in enumerate(EUDR_CHUNKS):
        logger.info(f"Processing Chunk #{idx + 1}...")
        try:
            vector = generate_embedding(chunk)
            assert len(vector) == 1024, "The model must return a 1024 dimension vector (bge-large)"
            
            supabase._client.table("eudr_documents").insert({
                "content": chunk,
                "embedding": vector
            }).execute()
            logger.info(f"Chunk #{idx + 1} successfully inserted.")
            
        except Exception as exc:
            logger.error(f"Failed inserting Chunk #{idx + 1}: {exc}")
            
    logger.info("🎉 RAG seeding process completed.")

if __name__ == "__main__":
    seed_database()
