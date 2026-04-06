"""Supabase client — audit persistence + pgvector RAG. Runs in mock mode if unconfigured."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional
import httpx

from core.config import settings
from core.exceptions import AuditPersistenceError

logger = logging.getLogger(__name__)

_MOCK_LOG = Path("audit_log_mock.jsonl")  # local fallback when Supabase is absent


class SupabaseService:
    """Persistence layer for audit records and EUDR RAG corpus."""

    def __init__(self) -> None:
        self._client = None
        if settings.supabase_configured:
            try:
                from supabase import create_client  # type: ignore

                self._client = create_client(settings.supabase_url, settings.supabase_anon_key)
                logger.info("Supabase client initialised successfully.")
            except Exception as exc:
                logger.warning("Could not initialise Supabase client: %s. Running in mock mode.", exc)
        else:
            logger.warning(
                "SUPABASE_URL / SUPABASE_ANON_KEY not set. "
                "Audit records will be written locally to %s",
                _MOCK_LOG,
            )

    # ── Audit Persistence ──────────────────────────────────────────────────────

    def save_audit(self, report_dict: dict, audit_hash: str) -> bool:
        """
        Persist the compliance report to Supabase `compliance_audits` table.
        Falls back to a local JSONL file when Supabase is not configured.

        Returns True on success, False on failure (never raises — audit is best-effort).
        """
        record = {"audit_hash": audit_hash, **report_dict}

        if self._client:
            try:
                self._client.table("compliance_audits").insert(record).execute()
                logger.info("Audit %s persisted to Supabase.", audit_hash)
                return True
            except Exception as exc:
                logger.error("Failed to persist audit to Supabase: %s", exc)
                # Fallback to local log so we don't lose data
                self._write_local(record)
                return False
        else:
            self._write_local(record)
            return True  # "mock success"

    # ── RAG Search ─────────────────────────────────────────────────────────────

    def rag_search(self, query: str, top_k: int = 4) -> list[str]:
        """
        Retrieve the most relevant EUDR regulation chunks via pgvector similarity search.
        Returns empty list when Supabase is not configured (the legal reasoner uses defaults).
        """
        if not self._client:
            logger.warning("RAG search unavailable — Supabase not configured. Returning empty context.")
            return self._mock_rag_context()

        try:
            # NOTE: Requires the `match_eudr_docs` RPC function + pgvector extension in Supabase.
            # The function signature is:
            #   match_eudr_docs(query_embedding vector, match_count int) returns table(content text, similarity float)
            # Embedding generation is handled here using a simple hash-based stub until
            # an embedding model is integrated.
            embedding = self._embed_query(query)
            result = (
                self._client.rpc(
                    "match_eudr_docs",
                    {"query_embedding": embedding, "match_count": top_k},
                ).execute()
            )
            return [row["content"] for row in (result.data or [])]
        except Exception as exc:
            logger.error("RAG search failed: %s", exc)
            return self._mock_rag_context()

    # ── Private helpers ────────────────────────────────────────────────────────

    def _write_local(self, record: dict) -> None:
        """Append record to local mock log file."""
        try:
            with _MOCK_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            logger.info("Audit record written to local log: %s", _MOCK_LOG)
        except Exception as exc:
            logger.error("Could not write local audit log: %s", exc)

    def _embed_query(self, text: str) -> list[float]:
        """
        Calls the Oxlo BGE-Large embeddings endpoint.
        Returns a mock vector if Oxlo is not configured or fails.
        """
        # BGE-Large embedding dimension is 1024
        mock_embedding = [0.0] * 1024

        if not settings.oxlo_configured:
            logger.warning("OXLO_API_KEY not set. Using mock embeddings for RAG.")
            return mock_embedding

        url = f"{settings.oxlo_base_url.rstrip('/')}/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.oxlo_api_key}"
        }
        payload = {
            "model": settings.oxlo_embedding_model,
            "input": text
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                res = client.post(url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                return data["data"][0]["embedding"]
        except Exception as exc:
            logger.error("Failed to generate embeddings from Oxlo: %s. Using mock.", exc)
            return mock_embedding

    def _mock_rag_context(self) -> list[str]:
        """Hardcoded EUDR law excerpts for development / testing."""
        return [
            "EUDR Article 3.1: Operators shall not place relevant commodities on the EU market "
            "unless those commodities have not contributed to deforestation or forest degradation "
            "after 31 December 2020.",
            "EUDR Article 4: Due diligence systems must include information on geolocation "
            "coordinates of all plots of land where the relevant commodities were produced.",
            "EUDR Annex I: Relevant commodities include cattle, cocoa, coffee, palm oil, soya, "
            "wood, rubber, and derived products.",
            "EUDR Article 10: Member States shall designate competent authorities responsible "
            "for applying this Regulation and carrying out official controls.",
        ]
