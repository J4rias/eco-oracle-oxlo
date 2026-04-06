"""
Certificate Service — Generates a legally-formatted EUDR Compliance PDF certificate.
Uses ReportLab for layout and qrcode for the verification QR.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
import base64
from typing import TYPE_CHECKING

import qrcode
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.config import settings

if TYPE_CHECKING:
    from schemas.outputs import ComplianceResponse

logger = logging.getLogger(__name__)

# ── Design constants ───────────────────────────────────────────────────────────
_DARK = colors.HexColor("#0D1117")
_GREEN = colors.HexColor("#2EA043")
_GREEN_LIGHT = colors.HexColor("#3FB950")
_AMBER = colors.HexColor("#D29922")
_RED = colors.HexColor("#DA3633")
_GRAY = colors.HexColor("#8B949E")
_LIGHT_GRAY = colors.HexColor("#F0F6FC")
_BORDER = colors.HexColor("#30363D")
_WHITE = colors.white

# Issuer details (MVP placeholder — replace with real org data via .env in production)
_ISSUER = {
    "name": "EcoOracle Certification Authority",
    "org": "EcoOracle Intelligence Systems S.A.S",
    "country": "Colombia",
    "reg": "EUDR-CA-2024-001",
    "contact": "compliance@eco-oracle.ai",
}


def _verdict_color(verdict: str) -> colors.HexColor:
    if verdict == "PASS":
        return _GREEN
    if verdict == "FAIL":
        return _RED
    return _AMBER


def _risk_label(score: int) -> tuple[str, colors.HexColor]:
    if score <= 30:
        return "LOW RISK", _GREEN
    if score <= 70:
        return "MODERATE RISK", _AMBER
    return "CRITICAL RISK", _RED


def _url_to_image(data_url: str | None, width: int = 50 * mm) -> Image | None:
    """Decodes a Data URL (base64) and returns a ReportLab Image."""
    if not data_url or not data_url.startswith("data:image"):
        return None
    try:
        header, encoded = data_url.split(",", 1)
        image_data = base64.b64decode(encoded)
        buf = io.BytesIO(image_data)
        return Image(buf, width=width, height=width)
    except Exception as exc:
        logger.warning("Failed to decode image for PDF: %s", exc)
        return None


def _generate_qr_image(url: str, size: int = 80) -> Image:
    """Generate a QR code pointing to the verification URL and return a ReportLab Image."""
    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    pil_img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    return Image(buf, width=size, height=size)


def generate_certificate(response: "ComplianceResponse") -> bytes:
    """
    Generate a professional EUDR Compliance Certificate PDF.

    Args:
        response: The full ComplianceResponse from the analysis pipeline.

    Returns:
        PDF bytes ready to stream as a download.
    """
    report = response.report
    evidence = response.evidence
    audit_hash = response.audit_hash

    verify_url = f"{settings.app_public_url.rstrip('/')}/verify/{audit_hash}"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"EUDR Compliance Certificate — {report.invoice_id}",
        author=_ISSUER["org"],
        subject="EU Deforestation Regulation Compliance Certificate",
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Section builder helpers ────────────────────────────────────────────────
    def h1(text: str) -> Paragraph:
        return Paragraph(text, ParagraphStyle(
            "H1", fontSize=22, textColor=_DARK, spaceAfter=4,
            fontName="Helvetica-Bold", leading=26,
        ))

    def h2(text: str, color=_DARK) -> Paragraph:
        return Paragraph(text, ParagraphStyle(
            "H2", fontSize=12, textColor=color, spaceAfter=2,
            fontName="Helvetica-Bold", leading=16,
        ))

    def body(text: str) -> Paragraph:
        return Paragraph(text, ParagraphStyle(
            "Body", fontSize=9, textColor=_DARK, leading=14, alignment=TA_JUSTIFY,
        ))

    def label(text: str, color=_GRAY) -> Paragraph:
        return Paragraph(text, ParagraphStyle(
            "Label", fontSize=8, textColor=color, leading=11, fontName="Helvetica",
        ))

    def small(text: str) -> Paragraph:
        return Paragraph(text, ParagraphStyle(
            "Small", fontSize=7.5, textColor=_GRAY, leading=11, fontName="Helvetica",
        ))

    def mono(text: str) -> Paragraph:
        return Paragraph(text, ParagraphStyle(
            "Mono", fontSize=7, textColor=_DARK, fontName="Courier", leading=10,
        ))

    def section_header(title: str) -> list:
        return [
            Spacer(1, 5 * mm),
            HRFlowable(width="100%", thickness=1, color=_BORDER),
            Spacer(1, 2 * mm),
            Paragraph(f"<font color='#{_GREEN.hexval()[2:]}'>▌</font> {title}", ParagraphStyle(
                "SH", fontSize=11, fontName="Helvetica-Bold", textColor=_DARK, leading=14,
            )),
            Spacer(1, 3 * mm),
        ]

    # ══════════════════════════════════════════════════════════════════
    # PAGE 1: HEADER + VERDICT + METADATA
    # ══════════════════════════════════════════════════════════════════

    # ── Header Bar ────────────────────────────────────────────────────────────
    verdict = report.verdict.value if hasattr(report.verdict, "value") else str(report.verdict)
    v_color = _verdict_color(verdict)
    risk_label, risk_color = _risk_label(report.risk_score)

    header_data = [
        [
            Paragraph(
                f"<b><font size='18' color='#{_GREEN.hexval()[2:]}'>EcoOracle</font></b>"
                f"<br/><font size='8' color='#{_GRAY.hexval()[2:]}'>EUDR Intelligence Platform</font>",
                ParagraphStyle("HDR", leading=22),
            ),
            Paragraph(
                f"<b><font size='14' color='#{v_color.hexval()[2:]}'>{verdict}</font></b>"
                f"<br/><font size='7' color='#{_GRAY.hexval()[2:]}'>EU Deforestation Regulation 2023/1115</font>",
                ParagraphStyle("HDR_V", leading=20, alignment=TA_RIGHT),
            ),
        ]
    ]
    header_table = Table(header_data, colWidths=["60%", "40%"])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, -1), _DARK),
        ("LEFTPADDING", (0, 0), (0, -1), 10),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 3 * mm))

    # ── Document Title ─────────────────────────────────────────────────────────
    story.append(Paragraph(
        "COMPLIANCE CERTIFICATE",
        ParagraphStyle("Title", fontSize=16, fontName="Helvetica-Bold",
                       textColor=_DARK, spaceAfter=6, alignment=TA_CENTER),
    ))
    story.append(Paragraph(
        f"Regulation (EU) 2023/1115 — EU Deforestation Regulation (EUDR)",
        ParagraphStyle("SubTitle", fontSize=9, textColor=_GRAY, alignment=TA_CENTER),
    ))
    story.append(Spacer(1, 4 * mm))

    # ── Metadata Table ─────────────────────────────────────────────────────────
    issued_at = report.created_at.strftime("%B %d, %Y at %H:%M UTC") if report.created_at else "N/A"
    acq_date = evidence.acquisition_date.strftime("%B %d, %Y") if evidence.acquisition_date else "N/A"
    cloud_pct = f"{evidence.cloud_cover_pct:.1f}%" if evidence.cloud_cover_pct is not None else "N/A"
    ndmi_status = evidence.ndmi_stats.get("status", "N/A") if evidence.ndmi_stats else "N/A"
    ndmi_mean = f"{evidence.ndmi_stats.get('mean', 0):.2f}" if evidence.ndmi_stats else "N/A"

    bbox = evidence.bounding_box
    bbox_str = f"[{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]" if bbox else "N/A"
    centroid = evidence.centroid
    centroid_str = f"({centroid[0]:.4f}°, {centroid[1]:.4f}°)" if centroid else "N/A"

    meta_rows = [
        ["INVOICE ID", report.invoice_id, "COMMODITY", report.crop_type],
        ["HARVEST DATE", str(report.harvest_date), "REPORTED VOLUME", f"{report.reported_tons} metric tons"],
        ["POLYGON AREA", f"{report.polygon_area_ha:.2f} ha", "CLOUD COVER", cloud_pct],
        ["SCENE DATE", acq_date, "MOISTURE STATUS", f"{ndmi_mean} ({ndmi_status})"],
        ["CENTROID (lon, lat)", centroid_str, "BOUNDING BOX", bbox_str],
        ["CERTIFICATE DATE", issued_at, "RISK SCORE", f"{report.risk_score}/100 — {risk_label}"],
    ]

    meta_style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), _GRAY),
        ("TEXTCOLOR", (2, 0), (2, -1), _GRAY),
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT_GRAY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_LIGHT_GRAY, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]
    meta_table = Table(
        [[label(c) if i % 2 == 0 else body(c) for i, c in enumerate(row)] for row in meta_rows],
        colWidths=["22%", "28%", "22%", "28%"],
    )
    meta_table.setStyle(TableStyle(meta_style))
    story.append(meta_table)

    import re
    # ── Legal Grounds ──────────────────────────────────────────────────────────
    story.extend(section_header("LEGAL BASIS"))
    rationale_text = re.sub(
        r'(\*\*|__)(.*?)\1', 
        r'<b>\2</b>', 
        report.legal_rationale.detailed_rationale,
        flags=re.DOTALL
    )
    # Also clean up unparsed markdown artifacts like markdown blocks
    rationale_text = rationale_text.replace("```markdown", "").replace("```", "")

    # Truncate to avoid PDF overflow — show first 2500 chars
    if len(rationale_text) > 2500:
        rationale_text = rationale_text[:2500] + "... [full rationale in digital record]"
    story.append(body(rationale_text))

    # Articles cited
    if report.legal_rationale.eudr_articles_cited:
        story.append(Spacer(1, 3 * mm))
        articles_text = "  |  ".join(report.legal_rationale.eudr_articles_cited)
        story.append(Paragraph(
            f"<b>EUDR Articles Referenced:</b> {articles_text}",
            ParagraphStyle("Arts", fontSize=8.5, textColor=_GREEN, fontName="Helvetica-Bold"),
        ))

    # Volume coherence
    story.extend(section_header("VOLUME COHERENCE"))
    coh_color = _GREEN if report.legal_rationale.volume_coherence_ok else _RED
    coh_symbol = "✓ VERIFIED" if report.legal_rationale.volume_coherence_ok else "✗ DISCREPANCY"
    story.append(Paragraph(
        f"<font color='#{coh_color.hexval()[2:]}'><b>{coh_symbol}</b></font> — "
        f"{report.legal_rationale.volume_coherence_notes}",
        ParagraphStyle("Coh", fontSize=8.5, leading=13, textColor=_DARK),
    ))

    # ── Satellite Evidence ─────────────────────────────────────────────────────
    story.extend(section_header("SATELLITE EVIDENCE"))
    
    img_rgb = _url_to_image(evidence.sentinel_image_url, width=54 * mm)
    img_ndvi = _url_to_image(evidence.ndvi_image_url, width=54 * mm)
    img_ndmi = _url_to_image(evidence.ndmi_image_url, width=54 * mm)

    if img_rgb or img_ndvi or img_ndmi:
        evidence_data = [
            [img_rgb or "N/A", img_ndvi or "N/A", img_ndmi or "N/A"],
            [label("TRUE COLOR (RGB)"), label("BIOMASS (NDVI)"), label("MOISTURE (NDMI)")],
        ]
        evidence_table = Table(evidence_data, colWidths=["33.3%", "33.3%", "33.3%"])
        evidence_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 1), (-1, 1), 2),
        ]))
        story.append(evidence_table)
    else:
        story.append(body("[No visual evidence metadata present in report]"))
    
    story.append(Spacer(1, 3 * mm))
    small("Spectral analysis captured by Sentinel-2 L2A satellite clusters. Images are calibrated and normalized for ground-truth verification.")

    # ── Digital Fingerprint + QR ───────────────────────────────────────────────
    story.extend(section_header("DIGITAL FINGERPRINT & VERIFICATION"))

    qr_img = _generate_qr_image(verify_url, size=72)
    hash_display = "\n".join([audit_hash[i:i+32] for i in range(0, len(audit_hash), 32)])
    fingerprint_data = [[
        [
            Paragraph("<b>SHA-256 AUDIT HASH</b>", ParagraphStyle(
                "FPH", fontSize=8, fontName="Helvetica-Bold", textColor=_GRAY,
            )),
            Spacer(1, 2 * mm),
            mono(hash_display),
            Spacer(1, 3 * mm),
            Paragraph("<b>VERIFICATION URL</b>", ParagraphStyle(
                "FPH2", fontSize=8, fontName="Helvetica-Bold", textColor=_GRAY,
            )),
            Paragraph(
                f"<a href='{verify_url}' color='#4493f8'>{verify_url}</a>", 
                ParagraphStyle("Link", fontSize=7.5, textColor=_GRAY, leading=10, fontName="Helvetica", wordWrap='CJK')
            ),
            Spacer(1, 2 * mm),
            small("Scan the QR code or click the URL to independently verify this certificate."),
        ],

        qr_img,
    ]]
    fp_table = Table(fingerprint_data, colWidths=["72%", "28%"])
    fp_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT_GRAY),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
    ]))
    story.append(fp_table)

    # ── Issuer Footer ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 5 * mm))
    HRFlowable(width="100%", thickness=0.5, color=_BORDER)
    issuer_data = [[
        Paragraph(
            f"<b>{_ISSUER['name']}</b><br/>"
            f"<font color='#{_GRAY.hexval()[2:]}'>{_ISSUER['org']} · {_ISSUER['country']}</font><br/>"
            f"<font color='#{_GRAY.hexval()[2:]}'>Reg. No. {_ISSUER['reg']} · {_ISSUER['contact']}</font>",
            ParagraphStyle("Issuer", fontSize=7.5, leading=12, textColor=_DARK),
        ),
        Paragraph(
            f"<font color='#{_GRAY.hexval()[2:]}'>This certificate is machine-generated and cryptographically<br/>"
            "signed via SHA-256 audit hash. It is valid only if the<br/>"
            "verification URL confirms an active record in the registry.</font>",
            ParagraphStyle("Disclaimer", fontSize=7, leading=10, textColor=_GRAY, alignment=TA_RIGHT),
        ),
    ]]
    issuer_table = Table(issuer_data, colWidths=["50%", "50%"])
    issuer_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, -1), _DARK),
        ("LEFTPADDING", (0, 0), (0, -1), 10),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 10),
    ]))
    story.append(issuer_table)

    # ── Build PDF ──────────────────────────────────────────────────────────────
    try:
        doc.build(story)
    except Exception as exc:
        logger.exception("PDF generation failed")
        raise RuntimeError(f"Certificate generation failed: {exc}") from exc

    return buf.getvalue()
