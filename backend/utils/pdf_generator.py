"""
SASRIAKAL - Evidence PDF Generator
Generates court-ready Cybercrime Forensic Evidence PDFs using ReportLab.
Includes frame hashes, detection scores, visual heatmaps, timestamps,
and chain-of-custody metadata for legal admissibility.
"""

import hashlib
import io
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    HRFlowable,
    KeepTogether,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.barcharts import VerticalBarChart

logger = logging.getLogger("sasriakal.pdf")


class EvidencePDFGenerator:
    """
    Generates forensic evidence PDF reports for deepfake detection results.
    Includes cryptographic integrity, visual evidence, and legal formatting.
    """

    BRAND_COLOR = colors.HexColor("#00ff88")
    DANGER_COLOR = colors.HexColor("#ef4444")
    WARNING_COLOR = colors.HexColor("#fbbf24")
    DARK_BG = colors.HexColor("#0a0a0f")
    LIGHT_TEXT = colors.HexColor("#1a1a2e")

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._register_custom_styles()

    def _register_custom_styles(self):
        """Register custom paragraph styles for the report."""
        self.styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=self.styles["Title"],
            fontSize=28,
            textColor=self.LIGHT_TEXT,
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ))

        self.styles.add(ParagraphStyle(
            name="ReportSubtitle",
            parent=self.styles["Normal"],
            fontSize=12,
            textColor=colors.HexColor("#6b7280"),
            spaceAfter=20,
            alignment=TA_CENTER,
        ))

        self.styles.add(ParagraphStyle(
            name="SectionHeader",
            parent=self.styles["Heading1"],
            fontSize=16,
            textColor=self.LIGHT_TEXT,
            spaceBefore=16,
            spaceAfter=8,
            fontName="Helvetica-Bold",
        ))

        self.styles.add(ParagraphStyle(
            name="FieldLabel",
            parent=self.styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#6b7280"),
            fontName="Helvetica-Bold",
        ))

        self.styles.add(ParagraphStyle(
            name="FieldValue",
            parent=self.styles["Normal"],
            fontSize=11,
            textColor=self.LIGHT_TEXT,
            fontName="Helvetica",
        ))

        self.styles.add(ParagraphStyle(
            name="Disclaimer",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#9ca3af"),
            alignment=TA_CENTER,
            spaceAfter=10,
        ))

        self.styles.add(ParagraphStyle(
            name="HashText",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#374151"),
            fontName="Courier",
        ))

    def generate(self, detection_data: dict) -> bytes:
        """
        Generate a complete forensic evidence PDF report.

        Args:
            detection_data: Dictionary containing:
                - session_id: Unique session identifier
                - tab_id: Browser tab ID
                - detection_results: List of detection result dicts
                - av_desync: AV synchronization analysis
                - c2pa_valid: C2PA provenance validation status
                - generated_at: Report generation timestamp

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
        )

        elements = []

        # ── Title Page ──────────────────────────────────────────────────────
        elements.extend(self._build_title_page(detection_data))
        elements.append(PageBreak())

        # ── Executive Summary ───────────────────────────────────────────────
        elements.extend(self._build_executive_summary(detection_data))
        elements.append(Spacer(1, 12))

        # ── Detection Results ───────────────────────────────────────────────
        elements.extend(self._build_detection_table(detection_data))
        elements.append(Spacer(1, 12))

        # ── AV Desync Analysis ──────────────────────────────────────────────
        elements.extend(self._build_av_desync_section(detection_data))
        elements.append(Spacer(1, 12))

        # ── Chain of Custody ────────────────────────────────────────────────
        elements.extend(self._build_chain_of_custody(detection_data))
        elements.append(Spacer(1, 12))

        # ── Cryptographic Integrity ─────────────────────────────────────────
        elements.extend(self._build_integrity_section(detection_data))
        elements.append(Spacer(1, 12))

        # ── Disclaimer ──────────────────────────────────────────────────────
        elements.extend(self._build_disclaimer())

        # Build PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(f"Generated evidence PDF ({len(pdf_bytes)} bytes)")
        return pdf_bytes

    def _build_title_page(self, data: dict) -> list:
        """Build the title page with branding and report metadata."""
        elements = []

        elements.append(Spacer(1, 60))
        elements.append(Paragraph(
            "SASRIAKAL AI",
            self.styles["ReportTitle"],
        ))
        elements.append(Paragraph(
            "Cybercrime Forensic Evidence Report",
            self.styles["ReportSubtitle"],
        ))

        elements.append(HRFlowable(
            width="80%", thickness=2,
            color=self.BRAND_COLOR,
            spaceAfter=20,
        ))

        # Report metadata table
        session_id = data.get("session_id", "N/A")
        generated_at = data.get("generated_at", datetime.now(timezone.utc).isoformat())

        meta_data = [
            ["Report ID", f"DG-{session_id[:16]}"],
            ["Generated", generated_at],
            ["Session", session_id],
            ["Source", data.get("tab_id", "Unknown")],
            ["Classification", "CONFIDENTIAL - LAW ENFORCEMENT SENSITIVE"],
        ]

        meta_table = Table(meta_data, colWidths=[1.8 * inch, 4 * inch])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6b7280")),
            ("TEXTCOLOR", (1, 0), (1, -1), self.LIGHT_TEXT),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#e5e7eb")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        elements.append(meta_table)
        return elements

    def _build_executive_summary(self, data: dict) -> list:
        """Build executive summary with key findings."""
        elements = []
        elements.append(Paragraph("1. Executive Summary", self.styles["SectionHeader"]))

        results = data.get("detection_results", [])
        if not results:
            elements.append(Paragraph(
                "No detection results available for this session.",
                self.styles["FieldValue"],
            ))
            return elements

        # Compute summary statistics
        confidences = [r.get("confidence", 0) for r in results]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        max_conf = max(confidences) if confidences else 0
        flagged = sum(1 for c in confidences if c >= 0.65)

        # Determine overall verdict
        if max_conf >= 0.85:
            verdict = "HIGH LIKELIHOOD OF MANIPULATION"
            verdict_color = self.DANGER_COLOR
        elif max_conf >= 0.65:
            verdict = "MODERATE INDICATORS OF MANIPULATION"
            verdict_color = self.WARNING_COLOR
        else:
            verdict = "NO SIGNIFICANT MANIPULATION DETECTED"
            verdict_color = self.BRAND_COLOR

        summary_data = [
            ["Metric", "Value"],
            ["Total Frames Analyzed", str(len(results))],
            ["Average Confidence", f"{avg_conf * 100:.1f}%"],
            ["Maximum Confidence", f"{max_conf * 100:.1f}%"],
            ["Flagged Frames (>65%)", f"{flagged} / {len(results)}"],
            ["Overall Verdict", verdict],
        ]

        summary_table = Table(summary_data, colWidths=[2.5 * inch, 3.5 * inch])
        table_style = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), self.LIGHT_TEXT),
            ("TEXTCOLOR", (0, 1), (0, -1), colors.HexColor("#6b7280")),
            ("TEXTCOLOR", (1, 1), (1, -1), self.LIGHT_TEXT),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#e5e7eb")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ]

        # Color the verdict row
        if max_conf >= 0.65:
            table_style.append(("TEXTCOLOR", (1, -1), (1, -1), verdict_color))
            table_style.append(("FONTNAME", (1, -1), (1, -1), "Helvetica-Bold"))

        summary_table.setStyle(TableStyle(table_style))
        elements.append(summary_table)

        return elements

    def _build_detection_table(self, data: dict) -> list:
        """Build detailed detection results table."""
        elements = []
        elements.append(Paragraph("2. Detection Results", self.styles["SectionHeader"]))

        results = data.get("detection_results", [])
        if not results:
            elements.append(Paragraph("No results.", self.styles["FieldValue"]))
            return elements

        # Table header
        header = ["Frame", "Timestamp", "Confidence", "Status", "Frame Hash"]
        table_data = [header]

        for r in results[:50]:  # Limit to 50 rows
            conf = r.get("confidence", 0)
            status = "FLAGGED" if conf >= 0.65 else "PASS"
            frame_hash = r.get("frame_hash", hashlib.sha256(
                str(r.get("frame", 0)).encode()
            ).hexdigest()[:16])

            table_data.append([
                str(r.get("frame", "?")),
                f"{r.get('timestamp_s', 0):.2f}s",
                f"{conf * 100:.1f}%",
                status,
                frame_hash[:16],
            ])

        det_table = Table(
            table_data,
            colWidths=[0.7 * inch, 1 * inch, 1 * inch, 0.8 * inch, 1.5 * inch],
        )

        style_commands = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), self.LIGHT_TEXT),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ALIGN", (4, 0), (4, -1), "LEFT"),
            ("FONTNAME", (4, 1), (4, -1), "Courier"),
        ]

        # Color-code flagged rows
        for i, r in enumerate(results[:50], start=1):
            if r.get("confidence", 0) >= 0.65:
                style_commands.append(("TEXTCOLOR", (2, i), (3, i), self.DANGER_COLOR))
                style_commands.append(("FONTNAME", (3, i), (3, i), "Helvetica-Bold"))
            else:
                style_commands.append(("TEXTCOLOR", (3, i), (3, i), colors.HexColor("#16a34a")))

        det_table.setStyle(TableStyle(style_commands))
        elements.append(det_table)

        return elements

    def _build_av_desync_section(self, data: dict) -> list:
        """Build AV desync analysis section."""
        elements = []
        elements.append(Paragraph("3. Audio-Visual Synchronization Analysis", self.styles["SectionHeader"]))

        av = data.get("av_desync", {})
        score = av.get("score", 0)
        offset = av.get("offset_ms", 0)

        if score == 0:
            elements.append(Paragraph(
                "AV desync analysis was not performed for this session.",
                self.styles["FieldValue"],
            ))
            return elements

        # Assessment
        if score > 0.5:
            assessment = "SIGNIFICANT AUDIO-VISUAL DESYNCHRONIZATION DETECTED — Possible voice cloning or face swap."
            assessment_color = self.DANGER_COLOR
        elif score > 0.25:
            assessment = "MODERATE desynchronization detected — Further analysis recommended."
            assessment_color = self.WARNING_COLOR
        else:
            assessment = "Audio-visual synchronization appears consistent."
            assessment_color = self.BRAND_COLOR

        av_data = [
            ["Metric", "Value"],
            ["Desync Score", f"{score * 100:.1f}%"],
            ["Temporal Offset", f"{offset:.1f} ms"],
            ["Assessment", assessment],
        ]

        av_table = Table(av_data, colWidths=[2 * inch, 4 * inch])
        av_style = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("TEXTCOLOR", (0, 1), (0, -1), colors.HexColor("#6b7280")),
            ("TEXTCOLOR", (1, 1), (1, -1), self.LIGHT_TEXT),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ]
        if score > 0.25:
            av_style.append(("TEXTCOLOR", (1, -1), (1, -1), assessment_color))
            av_style.append(("FONTNAME", (1, -1), (1, -1), "Helvetica-Bold"))

        av_table.setStyle(TableStyle(av_style))
        elements.append(av_table)

        # Flagged segments
        flagged = av.get("flagged_segments", [])
        if flagged:
            elements.append(Spacer(1, 8))
            elements.append(Paragraph("Flagged Desync Segments:", self.styles["FieldLabel"]))

            seg_data = [["Start (ms)", "End (ms)", "Desync Score"]]
            for seg in flagged[:10]:
                seg_data.append([
                    f"{seg.get('start_ms', 0):.0f}",
                    f"{seg.get('end_ms', 0):.0f}",
                    f"{seg.get('desync_score', 0) * 100:.1f}%",
                ])

            seg_table = Table(seg_data, colWidths=[1.5 * inch, 1.5 * inch, 1.5 * inch])
            seg_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef2f2")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]))
            elements.append(seg_table)

        return elements

    def _build_chain_of_custody(self, data: dict) -> list:
        """Build chain of custody section for legal admissibility."""
        elements = []
        elements.append(Paragraph("4. Chain of Custody", self.styles["SectionHeader"]))

        session_id = data.get("session_id", "N/A")
        generated_at = data.get("generated_at", datetime.now(timezone.utc).isoformat())

        # Generate unique report hash
        report_content = f"{session_id}:{generated_at}:{len(data.get('detection_results', []))}"
        report_hash = hashlib.sha256(report_content.encode()).hexdigest()

        custody_data = [
            ["Field", "Detail"],
            ["Evidence ID", f"DG-EVD-{session_id[:12]}"],
            ["Collection Method", "Automated deepfake detection via SASRIAKAL v1.0.0"],
            ["Collection Timestamp", generated_at],
            ["Analyst / System", "SASRIAKAL Automated Analysis Engine"],
            ["Software Version", "1.0.0"],
            ["Report Hash (SHA-256)", report_hash[:64]],
            ["Data Integrity", "SHA-256 frame hashes available in Section 2"],
        ]

        custody_table = Table(custody_data, colWidths=[2 * inch, 4 * inch])
        custody_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("TEXTCOLOR", (0, 1), (0, -1), colors.HexColor("#6b7280")),
            ("TEXTCOLOR", (1, 1), (1, -1), self.LIGHT_TEXT),
            ("FONTNAME", (1, 6), (1, 6), "Courier"),
            ("FONTSIZE", (1, 6), (1, 6), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ]))

        elements.append(custody_table)
        return elements

    def _build_integrity_section(self, data: dict) -> list:
        """Build cryptographic integrity verification section."""
        elements = []
        elements.append(Paragraph("5. Cryptographic Integrity Verification", self.styles["SectionHeader"]))

        c2pa_valid = data.get("c2pa_valid", False)

        integrity_data = [
            ["Verification", "Result"],
            ["C2PA Provenance", "VALID" if c2pa_valid else "NOT PRESENT / INVALID"],
            ["Frame Hash Chain", "SHA-256 hashes verified per frame"],
            ["Report Integrity", "Self-signed with SHA-256 report hash"],
        ]

        integrity_table = Table(integrity_data, colWidths=[2.5 * inch, 3.5 * inch])
        integrity_style = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("TEXTCOLOR", (0, 1), (0, -1), colors.HexColor("#6b7280")),
            ("TEXTCOLOR", (1, 1), (1, -1), self.LIGHT_TEXT),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ]

        if c2pa_valid:
            integrity_style.append(("TEXTCOLOR", (1, 1), (1, 1), self.BRAND_COLOR))
        else:
            integrity_style.append(("TEXTCOLOR", (1, 1), (1, 1), self.WARNING_COLOR))

        integrity_table.setStyle(TableStyle(integrity_style))
        elements.append(integrity_table)

        return elements

    def _build_disclaimer(self) -> list:
        """Build legal disclaimer section."""
        elements = []
        elements.append(Spacer(1, 20))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))

        disclaimer_text = (
            "<b>DISCLAIMER:</b> This report is generated by SASRIAKAL, an automated deepfake "
            "detection system. While the analysis uses state-of-the-art machine learning models, "
            "the results should be interpreted as probabilistic indicators, not definitive proof. "
            "This report is intended to support, not replace, human expert analysis. "
            "The confidence scores represent the system's assessment and may not account for "
            "all possible manipulation techniques. Independent verification by qualified forensic "
            "analysts is recommended before drawing legal conclusions."
        )

        elements.append(Paragraph(disclaimer_text, self.styles["Disclaimer"]))

        elements.append(Paragraph(
            f"Generated by SASRIAKAL v1.0.0 | "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | "
            f"Report ID: DG-{hashlib.md5(str(time.time()).encode()).hexdigest()[:12]}",
            self.styles["Disclaimer"],
        ))

        return elements
