"""
Connection test script — validates SentinelHub OAuth2 and Oxlo API connectivity.
Run with: python scripts/test_connections.py
"""
from __future__ import annotations

import sys
import json
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import settings


def test_sentinelhub():
    print("\n── SentinelHub Connection Test ───────────────────────────────────")
    if not settings.sentinel_hub_configured:
        print("  ⚠️  SKIPPED — SH_CLIENT_ID / SH_CLIENT_SECRET not set")
        return False

    try:
        from sentinelhub import SHConfig, SentinelHubCatalog, BBox, CRS

        config = SHConfig()
        config.sh_client_id = settings.sh_client_id
        config.sh_client_secret = settings.sh_client_secret
        if settings.sh_instance_id:
            config.instance_id = settings.sh_instance_id

        print(f"  Client ID : {settings.sh_client_id[:8]}...")
        print(f"  Instance  : {settings.sh_instance_id or 'N/A'}")

        # Small test bbox (Huila, Colombia)
        bbox = BBox(bbox=[-76.06, 1.97, -76.04, 1.99], crs=CRS.WGS84)
        catalog = SentinelHubCatalog(config=config)

        results = list(
            catalog.search(
                collection="sentinel-2-l2a",
                bbox=bbox,
                time=("2024-01-01", "2024-03-31"),
                filter=f"eo:cloud_cover < {settings.max_cloud_cover_pct}",
            )
        )

        print(f"  ✅ Connected! Found {len(results)} scenes in test query.")
        if results:
            first = results[0]
            props = first.get("properties", {})
            print(f"     Best scene: {props.get('datetime', 'N/A')[:10]}  "
                  f"cloud={props.get('eo:cloud_cover', 'N/A')}%")
        return True

    except Exception as exc:
        print(f"  ❌ SentinelHub test FAILED: {exc}")
        return False


def test_oxlo():
    print("\n── Oxlo.ai Connection Test ───────────────────────────────────────")
    if not settings.oxlo_configured:
        print("  ⚠️  SKIPPED — OXLO_API_KEY not set")
        return False

    try:
        import httpx

        key_preview = settings.oxlo_api_key[:12] + "..."
        print(f"  API Key   : {key_preview}")
        print(f"  Base URL  : {settings.oxlo_base_url}")

        # Minimal connectivity check (HEAD on base URL, or GET /health if available)
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                settings.oxlo_base_url,
                headers={"Authorization": f"Bearer {settings.oxlo_api_key}"},
            )

        print(f"  HTTP Status: {resp.status_code}")
        if resp.status_code < 500:
            print("  ✅ Oxlo API reachable (update OXLO_BASE_URL path when contract is known)")
            return True
        else:
            print(f"  ⚠️  Got {resp.status_code} — check OXLO_BASE_URL in .env")
            return False

    except Exception as exc:
        print(f"  ❌ Oxlo test FAILED: {exc}")
        print("     (This is expected if the base URL is still a placeholder)")
        return False


def test_full_mock_pipeline():
    print("\n── Mock Pipeline Test (no real API keys needed) ──────────────────")
    try:
        from schemas.inputs import FarmMetadata, CropType
        from agents.agent_manager import run_compliance_check
        from datetime import date

        with open(Path(__file__).parent.parent / "tests" / "fixtures" / "sample_farm.geojson") as f:
            geojson = json.load(f)

        metadata = FarmMetadata(
            crop_type=CropType.COFFEE,
            harvest_date=date(2024, 6, 15),
            invoice_id="INV-TEST-001",
            reported_tons=8.5,
        )

        print("  Running full agent pipeline (mock mode)...")
        # Force mock mode by temporarily disabling Oxlo endpoint check
        import os
        os.environ["OXLO_API_KEY"] = ""  # blank key triggers mock fallback in clients

        # reload settings cache
        from core.config import get_settings
        get_settings.cache_clear()
        import core.config as cfg_mod
        cfg_mod.settings = get_settings()

        state = run_compliance_check(raw_geojson=geojson, metadata=metadata)

        response = state.get("final_response")
        if response:
            print(f"  ✅ Pipeline OK!")
            print(f"     Verdict    : {response.report.verdict}")
            print(f"     Risk Score : {response.report.risk_score}")
            print(f"     Audit Hash : {response.audit_hash[:16]}...")
        else:
            print("  ❌ Pipeline completed but no final_response in state")
        return response is not None

    except Exception as exc:
        print(f"  ❌ Mock pipeline FAILED: {exc}")
        import traceback; traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 65)
    print("  EcoOracle — Connection & Pipeline Tests")
    print("=" * 65)

    results = {
        "sentinelhub": test_sentinelhub(),
        "oxlo": test_oxlo(),
        "mock_pipeline": test_full_mock_pipeline(),
    }

    print("\n── Summary ───────────────────────────────────────────────────────")
    for name, ok in results.items():
        icon = "✅" if ok else ("⚠️ " if ok is False and name != "mock_pipeline" else "❌")
        print(f"  {icon}  {name}")

    print()
    sys.exit(0 if results["mock_pipeline"] else 1)
