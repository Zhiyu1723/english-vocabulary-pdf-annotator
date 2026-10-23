from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, RectangleObject
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, TableStyle

from lexicon import default_word_list, load_word_list
from validate_definitions import load_json, validate


NOTE_FONT = "Helvetica"
NOTE_FONT_SIZE = 6.0
NOTE_LEADING = 7.0
NOTE_COLOR = colors.HexColor("#194B3A")
NOTE_FILL = colors.HexColor("#FFF4B8")
NOTE_RULE = colors.HexColor("#4E7661")
SIDEBAR_WIDTH = 236.0
SIDEBAR_PAD = 12.0
NOTE_TITLE_FONT_SIZE = 7.2
NOTE_BODY_FONT_SIZE = 6.7
NOTE_BODY_LEADING = 7.8


def load_json_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def wrap_text(text: str, max_width: float, font: str, size: float) -> list[str]:
    tokens = text.split()
    if not tokens:
        return [""]
    lines: list[str] = []
    current = tokens[0]
    for token in tokens[1:]:
        trial = f"{current} {token}"
        if pdfmetrics.stringWidth(trial, font, size) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = token
    lines.append(current)
    return lines


def draw_source_mark(
    pdf_canvas: canvas.Canvas,
    source_width: float,
    page_height: float,
    target: tuple[float, float, float, float],
    number: int,
) -> None:
    pdf_canvas.saveState()
    pdf_canvas.setFillColor(NOTE_FILL)
    pdf_canvas.setFillAlpha(0.34)
    pdf_canvas.rect(
        target[0] - 0.6,
        page_height - target[3] - 0.8,
        max(1.0, target[2] - target[0] + 1.2),
        max(1.0, target[3] - target[1] + 1.6),
        stroke=0,
        fill=1,
    )
    pdf_canvas.setFillColor(NOTE_COLOR)
    pdf_canvas.setFont("Helvetica-Bold", 4.5)
    marker_x = min(source_width - 5.0, target[2] + 0.8)
    marker_y = page_height - target[1] + 1.8
    pdf_canvas.drawString(marker_x, marker_y, str(number))
    pdf_canvas.restoreState()


def layout_sidebar_notes(
    source_width: float,
    height: float,
    notes: list[tuple[int, dict, str]],
) -> tuple[list[dict], list[tuple[int, dict, str]]]:
    max_width = SIDEBAR_WIDTH - (2 * SIDEBAR_PAD) - 17.0
    cursor = 43.0
    placed: list[dict] = []
    overflow: list[tuple[int, dict, str]] = []

    groups: dict[tuple[int, float], list[tuple[int, dict, str]]] = {}
    for number, candidate, definition in notes:
        line_top = float(candidate.get("line_top", candidate["bbox"][1]))
        line_index = int(candidate.get("line_index", -1))
        key = (line_index, round(line_top, 1))
        groups.setdefault(key, []).append((number, candidate, definition))

    for key in sorted(groups, key=lambda item: (item[1], item[0])):
        group_notes = sorted(groups[key], key=lambda item: float(item[1]["bbox"][0]))
        rendered_notes: list[dict] = []
        group_height = 4.0
        for number, candidate, definition in group_notes:
            prefix = f"{number} {candidate['word']}"
            definition_text = f"({definition})"
            prefix_width = pdfmetrics.stringWidth(
                prefix, "Helvetica-Bold", NOTE_TITLE_FONT_SIZE
            )
            same_line_space = max_width - prefix_width - 3.0
            if pdfmetrics.stringWidth(
                definition_text, NOTE_FONT, NOTE_BODY_FONT_SIZE
            ) <= same_line_space:
                rendered = {
                    "number": number,
                    "candidate": candidate,
                    "prefix": prefix,
                    "prefix_width": prefix_width,
                    "definition": definition_text,
                    "definition_lines": [],
                    "height": NOTE_BODY_LEADING + 0.8,
                }
            else:
                definition_lines = wrap_text(
                    definition_text,
                    max_width - 8.0,
                    NOTE_FONT,
                    NOTE_BODY_FONT_SIZE,
                )
                rendered = {
                    "number": number,
                    "candidate": candidate,
                    "prefix": prefix,
                    "prefix_width": prefix_width,
                    "definition": "",
                    "definition_lines": definition_lines,
                    "height": NOTE_BODY_LEADING
                    + len(definition_lines) * NOTE_BODY_LEADING,
                }
            rendered_notes.append(rendered)
            group_height += rendered["height"]

        desired_top = min(
            float(candidate.get("line_top", candidate["bbox"][1]))
            for _number, candidate, _definition in group_notes
        ) - 2.0
        top = max(cursor, desired_top)
        if top + group_height > height - 10.0:
            overflow.extend(group_notes)
            continue
        placed.append(
            {
                "notes": rendered_notes,
                "source_notes": group_notes,
                "top": top,
                "desired_top": desired_top,
                "height": group_height,
            }
        )
        cursor = top + group_height + 0.8
    return placed, overflow


def draw_sidebar(
    pdf_canvas: canvas.Canvas,
    source_width: float,
    height: float,
    page_number: int,
    groups: list[dict],
) -> None:
    edge = source_width + 3.0
    pdf_canvas.saveState()
    pdf_canvas.setFillColor(colors.HexColor("#F7F9F7"))
    pdf_canvas.rect(edge, 0, SIDEBAR_WIDTH - 3.0, height, stroke=0, fill=1)
    pdf_canvas.setStrokeColor(NOTE_RULE)
    pdf_canvas.setLineWidth(0.55)
    pdf_canvas.line(edge, 5.0, edge, height - 5.0)

    pdf_canvas.setFillColor(NOTE_COLOR)
    pdf_canvas.setFont("Helvetica-Bold", 8.0)
    pdf_canvas.drawString(edge + SIDEBAR_PAD, height - 18.0, "Vocabulary notes")
    pdf_canvas.setFillColor(colors.HexColor("#53645D"))
    pdf_canvas.setFont("Helvetica", 6.3)
    pdf_canvas.drawString(edge + SIDEBAR_PAD, height - 28.0, f"Source page {page_number}")

    for group in groups:
        top = group["top"]
        card_height = group["height"]
        x = edge + SIDEBAR_PAD
        y_bottom = height - top - card_height
        pdf_canvas.setFillColor(colors.HexColor("#EDF3EE"))
        pdf_canvas.roundRect(
            x - 2.0,
            y_bottom,
            SIDEBAR_WIDTH - (2 * SIDEBAR_PAD) + 4.0,
            card_height,
            2.0,
            stroke=0,
            fill=1,
        )
        pdf_canvas.setFillColor(NOTE_RULE)
        pdf_canvas.rect(x - 2.0, y_bottom, 1.4, card_height, stroke=0, fill=1)

        baseline = height - top - 7.5
        for note in group["notes"]:
            pdf_canvas.setFillColor(NOTE_COLOR)
            pdf_canvas.setFont("Helvetica-Bold", NOTE_TITLE_FONT_SIZE)
            pdf_canvas.drawString(x + 2.0, baseline, note["prefix"])
            if note["definition"]:
                pdf_canvas.setFont(NOTE_FONT, NOTE_BODY_FONT_SIZE)
                pdf_canvas.drawString(
                    x + 2.0 + note["prefix_width"] + 3.0,
                    baseline,
                    note["definition"],
                )
                baseline -= note["height"]
            else:
                baseline -= NOTE_BODY_LEADING
                pdf_canvas.setFont(NOTE_FONT, NOTE_BODY_FONT_SIZE)
                for line in note["definition_lines"]:
                    pdf_canvas.drawString(x + 10.0, baseline, line)
                    baseline -= NOTE_BODY_LEADING
            baseline -= 0.8
    pdf_canvas.restoreState()


def make_overlay(
    source_width: float,
    height: float,
    page_number: int,
    notes: list[tuple[int, dict, str]],
) -> tuple[PdfReader, list[tuple[int, dict, str]]]:
    stream = io.BytesIO()
    total_width = source_width + SIDEBAR_WIDTH
    pdf_canvas = canvas.Canvas(stream, pagesize=(total_width, height))
    pdf_canvas.setTitle("Annotated source page")
    placed, overflow = layout_sidebar_notes(source_width, height, notes)
    for group in placed:
        for number, candidate, _definition in group["source_notes"]:
            target = tuple(float(value) for value in candidate["bbox"])
            draw_source_mark(pdf_canvas, source_width, height, target, number)
    for number, candidate, _definition in overflow:
        target = tuple(float(value) for value in candidate["bbox"])
        draw_source_mark(pdf_canvas, source_width, height, target, number)
    draw_sidebar(pdf_canvas, source_width, height, page_number, placed)

    pdf_canvas.save()
    stream.seek(0)
    return PdfReader(stream), overflow


def expand_page(page: object, amount: float) -> None:
    for box_name in ("/MediaBox", "/CropBox"):
        box = page.get(box_name)
        if box is None:
            continue
        page[NameObject(box_name)] = RectangleObject(
            [
                float(box.left),
                float(box.bottom),
                float(box.right) + amount,
                float(box.top),
            ]
        )


def build_overflow_notes(
    notes: list[tuple[int, int, dict, str]],
) -> PdfReader:
    stream = io.BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Continued word notes",
        author="English Vocabulary PDF Annotator",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "NotesTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#173E31"),
        alignment=TA_LEFT,
        spaceAfter=2 * mm,
    )
    subtitle_style = ParagraphStyle(
        "NotesSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#53645D"),
        spaceAfter=5 * mm,
    )
    body_style = ParagraphStyle(
        "NotesBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.8,
        leading=10,
        textColor=colors.HexColor("#1E2924"),
    )
    number_style = ParagraphStyle(
        "NotesNumber",
        parent=body_style,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#173E31"),
    )
    header_style = ParagraphStyle(
        "NotesHeader",
        parent=body_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    data = [
        [
            Paragraph("No.", header_style),
            Paragraph("Page", header_style),
            Paragraph("Word", header_style),
            Paragraph("Explanation", header_style),
        ]
    ]
    for number, page_number, candidate, definition in sorted(notes):
        data.append(
            [
                Paragraph(str(number), number_style),
                Paragraph(str(page_number), body_style),
                Paragraph(escape(str(candidate["word"])), number_style),
                Paragraph(escape(f"({definition})"), body_style),
            ]
        )

    table = LongTable(
        data,
        colWidths=[12 * mm, 13 * mm, 43 * mm, 106 * mm],
        repeatRows=1,
        splitByRow=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#244D3E")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F4F7F2")],
                ),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D4CB")),
                ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor("#829A8B")),
            ]
        )
    )
    document.build(
        [
            Paragraph("Continued word notes", title_style),
            Paragraph(
                "Numbered notes that did not fit in their source page sidebar.",
                subtitle_style,
            ),
            table,
        ]
    )
    stream.seek(0)
    return PdfReader(stream)


def render(
    source: Path,
    scan: dict,
    definitions: dict,
    output: Path,
    word_list: Path,
) -> dict:
    if source.resolve() == output.resolve():
        raise ValueError("output must not overwrite the source PDF")
    if not scan.get("eligible"):
        raise ValueError("scan.json has no extractable English text")

    lexicon = load_word_list(word_list)
    report = validate(scan, definitions, lexicon)
    if not report["ok"]:
        raise ValueError("definitions failed validation: " + "; ".join(report["errors"][:5]))

    candidates = {candidate["id"]: candidate for candidate in scan["candidates"]}
    by_page: dict[int, list[tuple[dict, str]]] = {}
    covered_ids: set[str] = set()
    for entry in definitions["entries"]:
        ids = [entry["id"], *entry.get("also_ids", [])]
        for item_id in ids:
            candidate = candidates[item_id]
            by_page.setdefault(int(candidate["page_index"]), []).append(
                (candidate, str(entry["definition_en"]).strip())
            )
            covered_ids.add(item_id)

    numbered_by_page: dict[int, list[tuple[int, dict, str]]] = {}
    note_number = 0
    for page_index in sorted(by_page):
        ordered = sorted(
            by_page[page_index],
            key=lambda item: (float(item[0]["bbox"][1]), float(item[0]["bbox"][0])),
        )
        for candidate, definition in ordered:
            note_number += 1
            numbered_by_page.setdefault(page_index, []).append(
                (note_number, candidate, definition)
            )

    reader = PdfReader(str(source))
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    original_page_count = len(reader.pages)
    overflow_notes: list[tuple[int, int, dict, str]] = []
    sidebar_page_count = 0

    for page_index in range(original_page_count):
        pypdf_page = writer.pages[page_index]
        rotation = int(pypdf_page.get("/Rotate", 0) or 0) % 360
        if rotation:
            raise ValueError(
                f"page {page_index + 1} has rotation {rotation}; visual annotation "
                "placement is not supported on rotated pages"
            )
        notes = numbered_by_page.get(page_index, [])
        if not notes:
            continue
        width = float(pypdf_page.mediabox.width)
        height = float(pypdf_page.mediabox.height)
        overlay, overflow = make_overlay(width, height, page_index + 1, notes)
        expand_page(pypdf_page, SIDEBAR_WIDTH)
        pypdf_page.merge_page(overlay.pages[0], over=True)
        sidebar_page_count += 1
        overflow_notes.extend(
            (number, page_index + 1, candidate, definition)
            for number, candidate, definition in overflow
        )

    continuation_page_count = 0
    if overflow_notes:
        continuation = build_overflow_notes(overflow_notes)
        continuation_page_count = len(continuation.pages)
        for page in continuation.pages:
            writer.add_page(page)

    if reader.metadata:
        writer.add_metadata(
            {
                str(key): str(value)
                for key, value in reader.metadata.items()
                if key and value is not None
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output.with_name(output.name + ".tmp")
    with temp_path.open("wb") as stream:
        writer.write(stream)
    os.replace(temp_path, output)

    reopened = PdfReader(str(output))
    expected_page_count = original_page_count + continuation_page_count
    if len(reopened.pages) != expected_page_count:
        raise ValueError(
            f"unexpected page count: expected {expected_page_count}, "
            f"found {len(reopened.pages)}"
        )

    return {
        "output": str(output.resolve()),
        "source_page_count": original_page_count,
        "output_page_count": len(reopened.pages),
        "sidebar_page_count": sidebar_page_count,
        "continued_note_page_count": continuation_page_count,
        "annotated_ids": len(covered_ids),
        "validation_warnings": report["warnings"],
    }


def selftest() -> None:
    from reportlab.pdfgen import canvas as test_canvas

    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "source.pdf"
        output = Path(temp_dir) / "study.pdf"
        pdf = test_canvas.Canvas(str(source), pagesize=(400, 300))
        pdf.setFont("Helvetica", 11)
        pdf.drawString(30, 250, "Our Living World")
        pdf.drawString(30, 220, "Plants use photosynthesis to make food.")
        pdf.save()

        scan = {
            "eligible": True,
            "candidates": [
                {
                    "id": "p001-w0004-photosynthesis",
                    "word": "photosynthesis",
                    "normalized": "photosynthesis",
                    "page": 1,
                    "page_index": 0,
                    "bbox": [72, 73, 137, 85],
                    "font_size": 11,
                    "line": "Plants use photosynthesis to make food.",
                    "context": "Plants use photosynthesis to make food.",
                }
            ],
        }
        definitions = {
            "entries": [
                {
                    "id": "p001-w0004-photosynthesis",
                    "word": "photosynthesis",
                    "definition_en": "how green plants make food from light",
                }
            ]
        }
        result = render(source, scan, definitions, output, default_word_list())
        assert result["output_page_count"] == result["source_page_count"]
        assert result["sidebar_page_count"] == 1
        assert output.is_file()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an annotated English PDF without a glossary."
    )
    parser.add_argument("pdf", nargs="?", type=Path)
    parser.add_argument("--scan", type=Path)
    parser.add_argument("--definitions", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--word-list", type=Path, default=default_word_list())
    parser.add_argument("--selftest", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.selftest:
        selftest()
        print("render_study_pdf selftest: PASS")
        return 0
    if not all((args.pdf, args.scan, args.definitions, args.output)):
        print(
            "ERROR: provide PDF, --scan, --definitions and --output",
            file=sys.stderr,
        )
        return 2

    result = render(
        args.pdf.resolve(),
        load_json_file(args.scan),
        load_json_file(args.definitions),
        args.output.resolve(),
        args.word_list.resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
