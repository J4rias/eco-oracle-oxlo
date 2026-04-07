"""EcoOracle FastAPI application — EUDR compliance agent API."""
from __future__ import annotations

import json
import logging
import logging.config
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from agents.agent_manager import run_compliance_check, stream_compliance_check
from core.config import settings
from core.exceptions import (
    EcoOracleError,
    GeoJSONValidationError,
    OxloAPIError,
    SatelliteFetchError,
    SatelliteRateLimitError,
)
from schemas.inputs import FarmMetadata
from schemas.outputs import ComplianceResponse

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("eco_oracle")


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🌿 EcoOracle starting up (env=%s)", settings.app_env)
    logger.info(
        "Services: SentinelHub=%s | Oxlo=%s | Supabase=%s",
        "✅" if settings.sentinel_hub_configured else "⚠️  MOCK",
        "✅" if settings.oxlo_configured else "⚠️  MOCK",
        "✅" if settings.supabase_configured else "⚠️  LOCAL",
    )
    yield
    logger.info("🌿 EcoOracle shutting down")


# ── FastAPI App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="EcoOracle — EUDR Compliance Agent",
    description=(
        "AI-powered EUDR (EU Deforestation Regulation) compliance screening agent. "
        "Upload a GeoJSON polygon and invoice metadata to receive a structured "
        "compliance verdict backed by satellite imagery and legal reasoning."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception Handlers ─────────────────────────────────────────────────────────

@app.exception_handler(GeoJSONValidationError)
async def geojson_error_handler(request, exc: GeoJSONValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "invalid_geojson", "detail": exc.message, "hints": exc.details},
    )


@app.exception_handler(SatelliteRateLimitError)
async def rate_limit_handler(request, exc: SatelliteRateLimitError):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"error": "satellite_rate_limit", "detail": exc.message},
        headers={"Retry-After": "120"},
    )


@app.exception_handler(SatelliteFetchError)
async def satellite_error_handler(request, exc: SatelliteFetchError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "satellite_fetch_failed", "detail": exc.message},
    )


@app.exception_handler(OxloAPIError)
async def oxlo_error_handler(request, exc: OxloAPIError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "oxlo_api_error", "detail": exc.message},
    )


@app.exception_handler(EcoOracleError)
async def generic_eco_error_handler(request, exc: EcoOracleError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_error", "detail": exc.message},
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/api/v1/health", tags=["Health"], summary="Liveness probe")
async def health_check():
    """Returns service status and configuration flags."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "env": settings.app_env,
        "services": {
            "sentinel_hub": "configured" if settings.sentinel_hub_configured else "mock",
            "oxlo": "configured" if settings.oxlo_configured else "mock",
            "supabase": "configured" if settings.supabase_configured else "local_fallback",
        },
    }


@app.post(
    "/api/v1/compliance/analyze",
    response_model=ComplianceResponse,
    status_code=status.HTTP_200_OK,
    tags=["Compliance"],
    summary="Run EUDR compliance analysis on a farm polygon",
)
async def analyze_compliance(
    geojson_file: Annotated[UploadFile, File(description="GeoJSON file (.geojson) with the farm polygon")],
    metadata: Annotated[str, Form(description="JSON string with crop_type, harvest_date, invoice_id, reported_tons")],
):
    """
    Accepts a multipart request with:
    - **geojson_file**: `.geojson` file containing a Polygon or FeatureCollection
    - **metadata**: JSON string matching the FarmMetadata schema

    Returns a full `ComplianceResponse` with verdict, risk score, and audit hash.
    """
    # ── Parse metadata ─────────────────────────────────────────────────────────
    try:
        meta_dict = json.loads(metadata)
        farm_metadata = FarmMetadata.model_validate(meta_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid metadata JSON: {exc}",
        )

    # ── Parse GeoJSON ──────────────────────────────────────────────────────────
    if not geojson_file.filename or not geojson_file.filename.endswith((".geojson", ".json")):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .geojson or .json files are accepted",
        )

    try:
        raw_bytes = await geojson_file.read()
        raw_geojson = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse GeoJSON file: {exc}",
        )

    # ── Run agent (Streaming) ──────────────────────────────────────────────────
    logger.info(
        "Compliance request (STREAM): invoice=%s crop=%s tons=%s",
        farm_metadata.invoice_id,
        farm_metadata.crop_type.value,
        farm_metadata.reported_tons,
    )

    async def event_generator():
        try:
            async for event in stream_compliance_check(raw_geojson=raw_geojson, metadata=farm_metadata):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:
            logger.exception("Error in event stream")
            error_event = {"type": "error", "detail": str(exc)}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@app.get(
    "/api/v1/compliance/{report_id}",
    tags=["Compliance"],
    summary="Retrieve a previously generated compliance report",
)
async def get_compliance_report(report_id: str):
    """
    Fetch a compliance report by its UUID from Supabase.
    Returns 404 if not found or Supabase is not configured.
    """
    if not settings.supabase_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Report retrieval requires Supabase to be configured",
        )
    try:
        from services.supabase_client import SupabaseService

        svc = SupabaseService()
        result = (
            svc._client.table("compliance_audits")
            .select("*")
            .eq("report_id", report_id)
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
        return result.data
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get(
    "/api/v1/compliance/certificate/{audit_hash}",
    tags=["Compliance"],
    summary="Lazily generate and download the EUDR Compliance Certificate PDF",
)
async def download_certificate(audit_hash: str):
    """
    Generates a EUDR Compliance Certificate PDF on demand for the given audit_hash.
    The report must have been generated in the current server session (in-memory cache).
    Returns a PDF file as a streaming download.
    """
    from agents.nodes.audit_finalizer import _CERTIFICATE_CACHE
    from services.certificate_service import generate_certificate

    cached_response = _CERTIFICATE_CACHE.get(audit_hash)
    if not cached_response:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Certificate data not found for hash {audit_hash[:16]}... "
                "The report may have expired from cache. Please run a new analysis."
            ),
        )

    logger.info("Generating certificate PDF for audit_hash=%s", audit_hash[:16])
    try:
        pdf_bytes = generate_certificate(cached_response)
    except Exception as exc:
        logger.exception("Certificate generation failed")
        raise HTTPException(status_code=500, detail=f"Certificate generation failed: {exc}")

    filename = f"EcoOracle_Certificate_{cached_response.report.invoice_id}_{audit_hash[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get(
    "/api/v1/compliance/verify/{audit_hash}",
    tags=["Compliance"],
    summary="Public verification endpoint — confirm authenticity of an EcoOracle certificate",
)
async def verify_certificate(audit_hash: str):
    """
    Public endpoint to verify the authenticity of an EcoOracle certificate.
    Returns minimal, non-sensitive verification data (Option A: Verification Seal).
    """
    from agents.nodes.audit_finalizer import _CERTIFICATE_CACHE

    cached = _CERTIFICATE_CACHE.get(audit_hash)
    if cached:
        r = cached.report
        verdict = r.verdict.value if hasattr(r.verdict, "value") else str(r.verdict)
        return {
            "verified": True,
            "audit_hash": audit_hash,
            "invoice_id": r.invoice_id,
            "commodity": r.crop_type,
            "verdict": verdict,
            "issued_at": r.created_at.isoformat() if r.created_at else None,
            "issuer": "EcoOracle Certification Authority",
        }

    # Fallback: try Supabase if not in cache (server may have restarted)
    if settings.supabase_configured:
        try:
            from services.supabase_client import SupabaseService
            svc = SupabaseService()
            result = (
                svc._client.table("compliance_audits")
                .select("audit_hash,invoice_id,crop_type,verdict,created_at")
                .eq("audit_hash", audit_hash)
                .single()
                .execute()
            )
            if result.data:
                d = result.data
                return {
                    "verified": True,
                    "audit_hash": audit_hash,
                    "invoice_id": d.get("invoice_id"),
                    "commodity": d.get("crop_type"),
                    "verdict": d.get("verdict"),
                    "issued_at": d.get("created_at"),
                    "issuer": "EcoOracle Certification Authority",
                }
        except Exception:
            pass

    raise HTTPException(
        status_code=404,
        detail={
            "verified": False,
            "audit_hash": audit_hash,
            "message": "No certificate found for this hash. It may be invalid or expired.",
        },
    )

@app.get("/debug/cache")
def debug_cache():
    from agents.nodes.audit_finalizer import _CERTIFICATE_CACHE
    return {"keys": list(_CERTIFICATE_CACHE.keys())}
