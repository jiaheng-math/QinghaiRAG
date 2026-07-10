from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

REPORT_TITLE = "QinghaiRAG Technical Report"
REPORT_VERSION = "1.0.0-rc1"


def _inline_markup(text: str) -> str:
    normalized = (
        text.strip()
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2011", "-")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    escaped = html.escape(normalized)
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(
        r"\[([^]]+)]\((https?://[^)]+)\)",
        r'<link href="\2" color="#1769aa">\1</link>',
        escaped,
    )
    escaped = re.sub(
        r"&lt;(https?://[^&]+)&gt;",
        r'<link href="\1" color="#1769aa">\1</link>',
        escaped,
    )
    return escaped


def _styles() -> dict[str, ParagraphStyle]:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            textColor=colors.HexColor("#16324F"),
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "cover_meta": ParagraphStyle(
            "CoverMeta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#40566E"),
            leftIndent=20 * mm,
            rightIndent=20 * mm,
            spaceAfter=3,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#16324F"),
            spaceBefore=12,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=15,
            textColor=colors.HexColor("#24557A"),
            spaceBefore=9,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="STSong-Light",
            fontSize=8.7,
            leading=11.6,
            textColor=colors.HexColor("#1D2733"),
            spaceAfter=5,
            allowWidows=0,
            allowOrphans=0,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="STSong-Light",
            fontSize=8.5,
            leading=11.2,
            leftIndent=12,
            firstLineIndent=-7,
            bulletIndent=2,
            spaceAfter=2,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontName="Courier",
            fontSize=6.8,
            leading=8.8,
            leftIndent=7,
            rightIndent=7,
            borderColor=colors.HexColor("#D8E1EA"),
            borderWidth=0.5,
            borderPadding=6,
            backColor=colors.HexColor("#F5F7FA"),
            spaceBefore=4,
            spaceAfter=7,
        ),
        "table": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName="STSong-Light",
            fontSize=6.6,
            leading=8.2,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=6.5,
            leading=8,
            textColor=colors.white,
        ),
    }


def _table_flowable(rows: list[str], styles: dict[str, ParagraphStyle], width: float):
    parsed = [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in rows]
    if len(parsed) > 1 and all(re.fullmatch(r":?-{3,}:?", cell) for cell in parsed[1]):
        parsed.pop(1)
    column_count = max(len(row) for row in parsed)
    parsed = [row + [""] * (column_count - len(row)) for row in parsed]
    data = []
    for row_index, row in enumerate(parsed):
        style = styles["table_header"] if row_index == 0 else styles["table"]
        data.append([Paragraph(_inline_markup(cell), style) for cell in row])
    table = LongTable(
        data,
        colWidths=[width / column_count] * column_count,
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#24557A")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C5D1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def markdown_to_story(markdown: str, content_width: float):
    styles = _styles()
    lines = markdown.splitlines()
    story = []
    paragraph: list[str] = []
    table_rows: list[str] = []
    code_lines: list[str] = []
    in_code = False
    cover_complete = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            story.append(Paragraph(_inline_markup(" ".join(paragraph)), styles["body"]))
            paragraph = []

    def flush_table() -> None:
        nonlocal table_rows
        if table_rows:
            story.extend([_table_flowable(table_rows, styles, content_width), Spacer(1, 6)])
            table_rows = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            flush_table()
            if in_code:
                story.append(Preformatted("\n".join(code_lines), styles["code"]))
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            table_rows.append(stripped)
            continue
        flush_table()
        if not stripped:
            flush_paragraph()
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            story.extend(
                [
                    Spacer(1, 40 * mm),
                    Paragraph(_inline_markup(stripped[2:]), styles["cover_title"]),
                    Spacer(1, 10 * mm),
                ]
            )
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            if not cover_complete:
                story.append(PageBreak())
                cover_complete = True
            story.append(Paragraph(_inline_markup(stripped[3:]), styles["h1"]))
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            story.append(Paragraph(_inline_markup(stripped[4:]), styles["h2"]))
            continue
        if not cover_complete:
            flush_paragraph()
            story.append(Paragraph(_inline_markup(stripped), styles["cover_meta"]))
            story.append(Spacer(1, 2))
            continue
        bullet = re.match(r"^[-*] (.+)$", stripped)
        numbered = re.match(r"^(\d+)\. (.+)$", stripped)
        if bullet or numbered:
            flush_paragraph()
            marker = "•" if bullet else f"{numbered.group(1)}."
            text = bullet.group(1) if bullet else numbered.group(2)
            story.append(Paragraph(_inline_markup(text), styles["bullet"], bulletText=marker))
            continue
        paragraph.append(stripped)

    flush_paragraph()
    flush_table()
    if code_lines:
        story.append(Preformatted("\n".join(code_lines), styles["code"]))
    return story


def _draw_page(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    if doc.page > 1:
        canvas.setStrokeColor(colors.HexColor("#D8E1EA"))
        canvas.setLineWidth(0.4)
        canvas.line(18 * mm, height - 15 * mm, width - 18 * mm, height - 15 * mm)
        canvas.setFillColor(colors.HexColor("#60758A"))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(18 * mm, height - 11.5 * mm, REPORT_TITLE)
        canvas.drawRightString(width - 18 * mm, height - 11.5 * mm, REPORT_VERSION)
    canvas.setFillColor(colors.HexColor("#60758A"))
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(width / 2, 10 * mm, str(doc.page))
    canvas.restoreState()


def render_pdf(markdown_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=16 * mm,
        title="QinghaiRAG Technical Report",
        author="QinghaiRAG contributors",
        subject="Dataset design, governance, benchmark construction, and retrieval baselines",
    )
    story = markdown_to_story(markdown_path.read_text(encoding="utf-8"), document.width)
    document.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)


def render_pngs(pdf_path: Path, render_dir: Path) -> int:
    import fitz

    render_dir.mkdir(parents=True, exist_ok=True)
    for old_preview in render_dir.glob("page-*.png"):
        old_preview.unlink()
    document = fitz.open(pdf_path)
    for index, page in enumerate(document, start=1):
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
        pixmap.save(render_dir / f"page-{index:02d}.png")
    return len(document)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the QinghaiRAG technical report PDF")
    parser.add_argument("--input", type=Path, default=Path("docs/TECHNICAL_REPORT.md"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/pdf/QinghaiRAG_Technical_Report_1.0.0-rc1.pdf"),
    )
    parser.add_argument("--render-dir", type=Path, default=None)
    args = parser.parse_args()
    render_pdf(args.input, args.output)
    pages = render_pngs(args.output, args.render_dir) if args.render_dir else 0
    print(f"Rendered {args.output}; preview_pages={pages}")


if __name__ == "__main__":
    main()
