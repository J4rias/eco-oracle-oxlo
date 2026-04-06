"""Oxlo.ai REST client for YOLOv9 (vision) and DeepSeek R1 (reasoning)."""
from __future__ import annotations

import base64
import logging
from typing import Any

import httpx
import openai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import settings
from core.exceptions import ConfigurationError, OxloAPIError, OxloRateLimitError
from schemas.outputs import DeforestationDetection, LegalRationale, VisionReport

logger = logging.getLogger(__name__)

# ── Shared retry decorator ─────────────────────────────────────────────────────

_HTTP_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class _OxloRateLimit(Exception):
    """Internal signal for 429 from Oxlo."""


def _oxlo_retry():
    return retry(
        retry=retry_if_exception_type(_OxloRateLimit),
        wait=wait_exponential(multiplier=2, min=3, max=30),
        stop=stop_after_attempt(4),
    )


def _get_headers() -> dict[str, str]:
    if not settings.oxlo_configured:
        raise ConfigurationError("OXLO_API_KEY is not set in .env")
    return {
        "Authorization": f"Bearer {settings.oxlo_api_key}",
        "Content-Type": "application/json",
    }


# ── Vision Client (YOLOv9) ────────────────────────────────────────────────────


class OxloVisionClient:
    """
    Calls the Oxlo YOLOv9 vision endpoint.
    """

    ENDPOINT = "/detect"

    def __init__(self) -> None:
        self._base = settings.oxlo_base_url.rstrip("/")
        self._headers = _get_headers()

    @_oxlo_retry()
    def analyze(self, image_bytes: bytes, image_name: str = "sentinel.png") -> VisionReport:
        """
        Send satellite image to Oxlo YOLOv9 for change/deforestation detection.

        Args:
            image_bytes: PNG/JPEG bytes of the satellite image.
            image_name: Filename hint sent to the API.

        Returns:
            Parsed VisionReport.
        """
        payload = self._build_request_payload(image_bytes, image_name)
        url = f"{self._base}{self.ENDPOINT}"

        try:
            with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
                resp = client.post(url, headers=self._headers, json=payload)

            if resp.status_code == 429:
                logger.warning("Oxlo Vision API returned 429 — retrying...")
                raise _OxloRateLimit()

            if resp.status_code >= 400:
                raise OxloAPIError(
                    f"Oxlo Vision API error {resp.status_code}",
                    {"url": url, "body": resp.text[:500]},
                )

            return self._parse_vision_response(resp.json())

        except OxloAPIError:
            raise
        except _OxloRateLimit:
            raise
        except Exception as exc:
            logger.exception("Unexpected error calling Oxlo Vision API")
            raise OxloAPIError(f"Vision API call failed: {exc}") from exc

    # ── Mock fallback for development ──────────────────────────────────────────

    def analyze_mock(self, image_bytes: bytes) -> VisionReport:
        """Return a deterministic mock response when OXLO_API_KEY is absent."""
        logger.warning("OxloVisionClient: running in MOCK mode")
        from datetime import date as _date

        mock_detection = DeforestationDetection(
            label="deforestation",
            confidence=0.82,
            bbox=[0.1, 0.1, 0.4, 0.4],
            estimated_area_ha=3.5,
            detection_date=_date(2021, 8, 14),
        )
        return VisionReport(
            model="yolov9-mock",
            detections=[mock_detection],
            deforestation_detected=True,
            earliest_deforestation_date=_date(2021, 8, 14),
            max_confidence=0.82,
            raw_response={"mock": True},
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_request_payload(self, image_bytes: bytes, image_name: str) -> dict[str, Any]:
        """
        Build the request JSON for YOLOv9 detect endpoint.
        """
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "model": settings.oxlo_vision_model,
            "image": encoded,
            "confidence": 0.25, # parameter allows tuning
        }

    def _parse_vision_response(self, data: dict[str, Any]) -> VisionReport:
        """
        Parse the raw Oxlo YOLOv9 JSON into VisionReport.
        """
        raw_detections = data.get("detections", [])
        from datetime import date as _date

        detections: list[DeforestationDetection] = []
        for det in raw_detections:
            det_date_str = det.get("detection_date")
            detection = DeforestationDetection(
                label=det.get("label", "unknown"),
                confidence=float(det.get("confidence", 0.0)),
                bbox=det.get("bbox", [0, 0, 0, 0]),
                estimated_area_ha=det.get("area_ha"),
                detection_date=_date.fromisoformat(det_date_str) if det_date_str else None,
            )
            detections.append(detection)

        deforestation_dets = [d for d in detections if "deforest" in d.label.lower()]
        earliest = None
        if deforestation_dets:
            dates = [d.detection_date for d in deforestation_dets if d.detection_date]
            earliest = min(dates) if dates else None

        max_conf = max((d.confidence for d in detections), default=0.0)

        return VisionReport(
            model=data.get("model", settings.oxlo_vision_model),
            detections=detections,
            deforestation_detected=bool(deforestation_dets),
            earliest_deforestation_date=earliest,
            max_confidence=max_conf,
            raw_response=data,
        )


# ── Reasoning Client (DeepSeek R1) ────────────────────────────────────────────


class OxloReasoningClient:
    """
    Calls the Oxlo DeepSeek R1 reasoning endpoint.

    ASSUMPTION: OpenAI-compatible /chat/completions interface.
    Update `ENDPOINT` and `_build_messages` if Oxlo uses a different schema.
    """

    ENDPOINT = "/reasoning/chat"

    def __init__(self) -> None:
        self._base = settings.oxlo_base_url.rstrip("/")
        if not settings.oxlo_configured:
            raise ConfigurationError("OXLO_API_KEY is not set in .env")
        
        self.openai_client = openai.OpenAI(
            base_url=self._base,
            api_key=settings.oxlo_api_key
        )

    def reason(self, prompt: str, system_prompt: str = "") -> str:
        """
        Send a structured prompt to DeepSeek R1 and return the response text.

        Args:
            prompt: The user-facing prompt with vision report + metadata.
            system_prompt: Optional system instructions.

        Returns:
            Raw text response from the reasoning model.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.openai_client.chat.completions.create(
                model=settings.oxlo_reasoning_model,
                messages=messages,
                temperature=0.1,
                max_tokens=2048,
                top_p=0.95
            )
            return response.choices[0].message.content

        except openai.RateLimitError:
            logger.warning("Oxlo Reasoning API returned 429 — rate limit exceeded.")
            raise OxloRateLimitError("Oxlo Reasoning API rate limit exceeded.")
        except Exception as exc:
            logger.exception("Unexpected error calling Oxlo Reasoning API")
            raise OxloAPIError(f"Reasoning API call failed: {exc}") from exc

    def reason_mock(self, prompt: str) -> str:
        """Return a deterministic mock rationale for development."""
        logger.warning("OxloReasoningClient: running in MOCK mode")
        return (
            "## EUDR Compliance Assessment\n\n"
            "**Verdict**: NON-COMPLIANT\n\n"
            "The YOLOv9 model detected deforestation activity dated **August 14, 2021**, "
            "which is **after** the EUDR cutoff of December 31, 2020 (Article 3.1). "
            "The lot is therefore ineligible for EU market access.\n\n"
            "**Volume coherence**: The reported 12.5 metric tons of Café aligns with "
            "the estimated productivity of the 15.3 ha polygon (≈ 0.82 t/ha). ✅\n\n"
            "**EUDR Articles cited**: Art. 3.1, Art. 4, Annex I."
        )
