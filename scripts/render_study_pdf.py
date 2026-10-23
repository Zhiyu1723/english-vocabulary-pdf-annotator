from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, RectangleObject
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from lexicon import default_word_list, load_word_list
from validate_definitions import load_json, validate


NOTE_FONT = "Helvetica"
NOTE_COLOR = colors.HexColor("#194B3A")
NOTE_FILL = colors.HexColor("#FFF4B8")
NOTE_RULE = colors.HexColor("#4E7661")
SIDEBAR_WIDTH = 236.0
SIDEBAR_PAD = 12.0
NOTE_PROFILES = [
    {
        "name": "normal",
        "title_size": 7.2,
        "body_size": 6.7,
        "leading": 7.8,
        "card_pad": 4.0,
        "note_gap": 0.8,
        "cards": True,
    },
    {
        "name": "compact",
        "title_size": 6.6,
        "body_size": 6.1,
        "leading": 6.9,
        "card_pad": 2.4,
        "note_gap": 0.4,
        "cards": True,
    },
    {
        "name": "tight",
        "title_size": 6.1,
        "body_size": 5.7,
        "leading": 6.3,
        "card_pad": 1.2,
        "note_gap": 0.15,
        "cards": False,
    },
]


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
    profile: dict,
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
        group_height = float(profile["card_pad"])
        for number, candidate, definition in group_notes:
            prefix = f"{number} {candidate['word']}"
            definition_text = f"({definition})"
            prefix_width = pdfmetrics.stringWidth(
                prefix, "Helvetica-Bold", float(profile["title_size"])
            )
            same_line_space = max_width - prefix_width - 3.0
            if pdfmetrics.stringWidth(
                definition_text, NOTE_FONT, float(profile["body_size"])
            ) <= same_line_space:
                rendered = {
                    "number": number,
                    "candidate": candidate,
                    "prefix": prefix,
                    "prefix_width": prefix_width,
                    "definition": definition_text,
                    "definition_lines": [],
                    "height": float(profile["leading"]) + 0.35,
                }
            else:
                definition_lines = wrap_text(
                    definition_text,
                    max_width - 8.0,
                    NOTE_FONT,
                    float(profile["body_size"]),
                )
                rendered = {
                    "number": number,
                    "candidate": candidate,
                    "prefix": prefix,
                    "prefix_width": prefix_width,
                    "definition": "",
                    "definition_lines": definition_lines,
                    "height": float(profile["leading"])
                    + len(definition_lines) * float(profile["leading"]),
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
        cursor = top + group_height + float(profile["note_gap"])
    return placed, overflow


def draw_sidebar(
    pdf_canvas: canvas.Canvas,
    source_width: float,
    height: float,
    page_number: int,
    groups: list[dict],
    profile: dict,
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
        if profile["cards"]:
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

        baseline = height - top - float(profile["leading"])
        for note in group["notes"]:
            pdf_canvas.setFillColor(NOTE_COLOR)
            pdf_canvas.setFont("Helvetica-Bold", float(profile["title_size"]))
            pdf_canvas.drawString(x + 2.0, baseline, note["prefix"])
            if note["definition"]:
                pdf_canvas.setFont(NOTE_FONT, float(profile["body_size"]))
                pdf_canvas.drawString(
                    x + 2.0 + note["prefix_width"] + 3.0,
                    baseline,
                    note["definition"],
                )
                baseline -= note["height"]
            else:
                baseline -= float(profile["leading"])
                pdf_canvas.setFont(NOTE_FONT, float(profile["body_size"]))
                for line in note["definition_lines"]:
                    pdf_canvas.drawString(x + 10.0, baseline, line)
                    baseline -= float(profile["leading"])
            baseline -= float(profile["note_gap"])
    pdf_canvas.restoreState()


def make_overlay(
    source_width: float,
    height: float,
    page_number: int,
    notes: list[tuple[int, dict, str]],
) -> tuple[PdfReader, str]:
    stream = io.BytesIO()
    total_width = source_width + SIDEBAR_WIDTH
    pdf_canvas = canvas.Canvas(stream, pagesize=(total_width, height))
    pdf_canvas.setTitle("Annotated source page")
    placed: list[dict] | None = None
    selected_profile: dict | None = None
    overflow: list[tuple[int, dict, str]] = []
    for profile in NOTE_PROFILES:
        candidate_placed, candidate_overflow = layout_sidebar_notes(
            source_width,
            height,
            notes,
            profile,
        )
        if not candidate_overflow:
            placed = candidate_placed
            selected_profile = profile
            break
        overflow = candidate_overflow
    if placed is None or selected_profile is None:
        overflow_words = ", ".join(
            str(candidate["word"]) for _number, candidate, _definition in overflow[:8]
        )
        raise ValueError(
            f"page {page_number} has too many notes to fit in any supported layout; "
            f"shorten definitions or merge more inflected forms ({overflow_words})"
        )
    for group in placed:
        for number, candidate, _definition in group["source_notes"]:
            target = tuple(float(value) for value in candidate["bbox"])
            draw_source_mark(pdf_canvas, source_width, height, target, number)
    draw_sidebar(
        pdf_canvas,
        source_width,
        height,
        page_number,
        placed,
        selected_profile,
    )

    pdf_canvas.save()
    stream.seek(0)
    return PdfReader(stream), str(selected_profile["name"])


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
    sidebar_page_count = 0
    layout_modes: set[str] = set()

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
        overlay, layout_mode = make_overlay(width, height, page_index + 1, notes)
        layout_modes.add(layout_mode)
        expand_page(pypdf_page, SIDEBAR_WIDTH)
        pypdf_page.merge_page(overlay.pages[0], over=True)
        sidebar_page_count += 1

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
    if len(reopened.pages) != original_page_count:
        raise ValueError(
            f"unexpected page count: expected {original_page_count}, "
            f"found {len(reopened.pages)}"
        )

    return {
        "output": str(output.resolve()),
        "source_page_count": original_page_count,
        "output_page_count": len(reopened.pages),
        "sidebar_page_count": sidebar_page_count,
        "layout_modes": sorted(layout_modes),
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

        dense_notes = [
            (
                index + 1,
                {
                    "word": f"term{index + 1}",
                    "bbox": [20, 80 + index * 2, 50, 88 + index * 2],
                    "line_top": 80 + index * 2,
                },
                "a short meaning",
            )
            for index in range(20)
        ]
        _dense_overlay, dense_mode = make_overlay(400, 300, 1, dense_notes)
        assert dense_mode in {"compact", "tight"}


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
