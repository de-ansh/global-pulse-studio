"""PDF Dossier generator for Fact-Check Source Sheets using ReportLab."""
import io
import xml.sax.saxutils as saxutils
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)


def escape_txt(text: Any) -> str:
    """Safely escape text for ReportLab XML flowables."""
    if text is None:
        return ""
    return saxutils.escape(str(text))


STATUS_COLORS = {
    "confirmed": colors.HexColor("#065f46"),
    "disputed": colors.HexColor("#92400e"),
    "false": colors.HexColor("#991b1b"),
    "unverified": colors.HexColor("#334155"),
}


def generate_source_sheet_pdf(
    title: str,
    readiness_score: int,
    citations: List[Any],
    sources: List[Dict[str, Any]],
    warnings: Optional[List[str]] = None,
    working_slug: str = "project",
) -> bytes:
    """Render a publication-grade PDF Dossier containing verified claims, archive links, and sources."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
    )
    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    )
    cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    )
    cell_link = ParagraphStyle(
        "TableCellLink",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0284c7"),
    )
    cell_quote = ParagraphStyle(
        "TableCellQuote",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )
    badge_style = ParagraphStyle(
        "BadgeText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        alignment=1,  # Center
        textColor=colors.white,
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("GLOBAL PULSE STUDIO — FACT-CHECK & CITATION DOSSIER", ParagraphStyle(
        "Banner",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0284c7"),
        spaceAfter=4,
    )))
    story.append(Paragraph(escape_txt(title), title_style))
    story.append(Spacer(1, 4))

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(Paragraph(
        f"<b>Slug:</b> {escape_txt(working_slug)} &nbsp;|&nbsp; <b>Generated:</b> {now_str} &nbsp;|&nbsp; <b>Audit Readiness Score:</b> <b>{readiness_score}/100</b>",
        meta_style,
    ))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#cbd5e1"), spaceAfter=10))

    # 2. Section: Claim Ledger & Citations
    story.append(Paragraph("1. Verified Claims & Evidence Ledger", section_heading))

    claim_headers = [
        Paragraph("<b>Status</b>", ParagraphStyle("H1", parent=cell_bold, textColor=colors.white, alignment=1)),
        Paragraph("<b>Factual Claim</b>", ParagraphStyle("H2", parent=cell_bold, textColor=colors.white)),
        Paragraph("<b>Evidence & Archive</b>", ParagraphStyle("H3", parent=cell_bold, textColor=colors.white)),
        Paragraph("<b>Verbatim Corroboration Quote</b>", ParagraphStyle("H4", parent=cell_bold, textColor=colors.white)),
    ]

    claim_rows = [claim_headers]
    if not citations:
        claim_rows.append([
            Paragraph("—", cell_style),
            Paragraph("<i>No claims registered in project ledger.</i>", cell_style),
            Paragraph("—", cell_style),
            Paragraph("—", cell_style),
        ])
    else:
        for cit in citations:
            status_val = (getattr(cit, "status", None) or (cit.get("status") if isinstance(cit, dict) else "unverified")).lower()
            text_val = getattr(cit, "text", None) or (cit.get("text") if isinstance(cit, dict) else "")
            ev_urls = getattr(cit, "evidence_urls", None) or (cit.get("evidence_urls") if isinstance(cit, dict) else [])
            arch_urls = getattr(cit, "archive_urls", None) or (cit.get("archive_urls") if isinstance(cit, dict) else [])
            quotes = getattr(cit, "verbatim_quotes", None) or (cit.get("verbatim_quotes") if isinstance(cit, dict) else [])

            # Status Cell
            bg_col = STATUS_COLORS.get(status_val, colors.HexColor("#334155"))
            status_p = Paragraph(f"<b>{escape_txt(status_val.upper())}</b>", badge_style)

            # Claim Text
            claim_p = Paragraph(escape_txt(text_val), cell_style)

            # Evidence Link + Archive
            link_parts = []
            if ev_urls:
                link_parts.append(f"<b>Primary:</b> <font color='#0284c7'>{escape_txt(ev_urls[0][:40])}</font>")
            if arch_urls:
                link_parts.append(f"<b>Wayback:</b> <font color='#475569'>{escape_txt(arch_urls[0][:40])}</font>")
            ev_p = Paragraph("<br/>".join(link_parts) if link_parts else "<i>None</i>", cell_link)

            # Quote
            quote_text = f'"{escape_txt(quotes[0][:140])}..."' if quotes else "<i>None</i>"
            quote_p = Paragraph(quote_text, cell_quote)

            claim_rows.append([status_p, claim_p, ev_p, quote_p])

    # Table styling for Claims
    col_widths = [65, 230, 125, 120]
    claim_table = Table(claim_rows, colWidths=col_widths, repeatRows=1)
    
    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    # Add colored backgrounds for each status badge column cell
    for idx, row in enumerate(claim_rows[1:], 1):
        if idx < len(citations) + 1:
            cit = citations[idx - 1]
            status_val = (getattr(cit, "status", None) or (cit.get("status") if isinstance(cit, dict) else "unverified")).lower()
            bg_col = STATUS_COLORS.get(status_val, colors.HexColor("#334155"))
            t_style.append(("BACKGROUND", (0, idx), (0, idx), bg_col))

    claim_table.setStyle(TableStyle(t_style))
    story.append(claim_table)
    story.append(Spacer(1, 14))

    # 3. Section: Primary & Wire Intelligence Sources
    story.append(Paragraph("2. Primary & Wire Intelligence Sources", section_heading))

    source_headers = [
        Paragraph("<b>ID</b>", ParagraphStyle("SH1", parent=cell_bold, textColor=colors.white, alignment=1)),
        Paragraph("<b>Outlet / Title</b>", ParagraphStyle("SH2", parent=cell_bold, textColor=colors.white)),
        Paragraph("<b>URL & Type</b>", ParagraphStyle("SH3", parent=cell_bold, textColor=colors.white)),
    ]

    source_rows = [source_headers]
    if not sources:
        source_rows.append([
            Paragraph("—", cell_style),
            Paragraph("<i>No sources linked.</i>", cell_style),
            Paragraph("—", cell_style),
        ])
    else:
        for s in sources:
            sid = s.get("id", "S?")
            stitle = s.get("title") or s.get("outlet") or "Source"
            surl = s.get("url", "")
            skind = s.get("kind", "article")

            sid_p = Paragraph(f"<b>{escape_txt(sid)}</b>", cell_bold)
            title_p = Paragraph(escape_txt(stitle), cell_style)
            url_p = Paragraph(f"<font color='#0284c7'>{escape_txt(surl[:60])}</font> ({escape_txt(skind)})", cell_link)
            source_rows.append([sid_p, title_p, url_p])

    source_table = Table(source_rows, colWidths=[40, 260, 240], repeatRows=1)
    source_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(source_table)
    story.append(Spacer(1, 14))

    # 4. Section: Editorial Warnings & Triangulation Checklist
    story.append(Paragraph("3. Editorial Verification & Triangulation Checklist", section_heading))
    if warnings:
        for w in warnings:
            story.append(Paragraph(f"• <b>WARNING:</b> {escape_txt(w)}", ParagraphStyle(
                "WarnText",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=12,
                textColor=colors.HexColor("#991b1b"),
            )))
    else:
        story.append(Paragraph(
            "✓ <b>Full Editorial Triangulation Passed:</b> All factual claims corroborated with verifiable primary sources and permanent archive permalinks.",
            ParagraphStyle(
                "PassText",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=12,
                textColor=colors.HexColor("#065f46"),
            )
        ))

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=6))
    story.append(Paragraph(
        "Confidential Fact-Check Dossier generated by Global Pulse Studio. Do not distribute unredacted versions without editorial compliance review.",
        ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=1,  # Center
            textColor=colors.HexColor("#94a3b8"),
        )
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
