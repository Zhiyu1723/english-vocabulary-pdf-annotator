from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pdfplumber

from lexicon import (
    default_word_list,
    display_word,
    is_known_word,
    load_word_list,
    normalize_word,
)


TEXT_RE = re.compile(r"[A-Za-z]{2,}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def line_groups(words: list[dict]) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if not lines or abs(word["top"] - lines[-1][0]["top"]) > 3.0:
            lines.append([word])
        else:
            lines[-1].append(word)
    return lines


def scan_pdf(pdf_path: Path, word_list_path: Path) -> dict:
    lexicon = load_word_list(word_list_path)
    first_candidates: dict[str, dict] = {}
    occurrences: Counter[str] = Counter()
    evidence: list[str] = []
    page_texts: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)

        for page_index, page in enumerate(pdf.pages):
            text = page.extract_text(layout=False) or ""
            page_texts.append(text)
            if TEXT_RE.search(text) and len(evidence) < 5:
                evidence.append(f"page {page_index + 1}: extractable English text")

            words = page.extract_words(
                use_text_flow=True,
                keep_blank_chars=False,
                extra_attrs=["size", "fontname"],
            )
            for line_index, line in enumerate(line_groups(words)):
                line_text = " ".join(word["text"] for word in line)
                line_top = min(float(word["top"]) for word in line)
                line_bottom = max(float(word["bottom"]) for word in line)
                for word_index, word in enumerate(line):
                    normalized = normalize_word(word["text"])
                    if not normalized or is_known_word(normalized, lexicon):
                        continue
                    occurrences[normalized] += 1
                    if normalized in first_candidates:
                        continue
                    slug = re.sub(r"[^a-z0-9]+", "-", normalized)[:42].strip("-")
                    candidate_id = f"p{page_index + 1:03d}-w{word_index + 1:04d}-{slug}"
                    first_candidates[normalized] = {
                        "id": candidate_id,
                        "word": display_word(word["text"]),
                        "normalized": normalized,
                        "page": page_index + 1,
                        "page_index": page_index,
                        "line_index": line_index,
                        "bbox": [
                            round(float(word["x0"]), 2),
                            round(float(word["top"]), 2),
                            round(float(word["x1"]), 2),
                            round(float(word["bottom"]), 2),
                        ],
                        "font_size": round(float(word.get("size") or 0), 2),
                        "line_top": round(line_top, 2),
                        "line_bottom": round(line_bottom, 2),
                        "line": line_text,
                        "context": line_text,
                    }

    for normalized, count in occurrences.items():
        first_candidates[normalized]["occurrences"] = count

    return {
        "source_pdf": str(pdf_path.resolve()),
        "source_sha256": sha256_file(pdf_path),
        "word_list": str(word_list_path.resolve()),
        "word_list_sha256": sha256_file(word_list_path),
        "page_count": page_count,
        "eligible": bool(evidence),
        "eligibility_evidence": evidence,
        "lexicon_size": len(lexicon),
        "candidate_count": len(first_candidates),
        "candidates": list(first_candidates.values()),
        "page_text_chars": [len(text) for text in page_texts],
    }


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def selftest() -> None:
    import tempfile

    from reportlab.pdfgen import canvas

    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "sample.pdf"
        output = Path(temp_dir) / "scan.json"
        pdf = canvas.Canvas(str(source), pagesize=(400, 300))
        pdf.drawString(30, 250, "Our Living World")
        pdf.drawString(30, 220, "Plants use photosynthesis to make food.")
        pdf.save()
        result = scan_pdf(source, default_word_list())
        assert result["eligible"]
        assert result["page_count"] == 1
        assert any(item["normalized"] == "photosynthesis" for item in result["candidates"])
        write_json(output, result)
        assert json.loads(output.read_text(encoding="utf-8"))["eligible"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find unfamiliar English words in a PDF using the learner word list."
    )
    parser.add_argument("pdf", nargs="?", type=Path)
    parser.add_argument("--output", type=Path, default=Path("work/scan.json"))
    parser.add_argument("--word-list", type=Path, default=default_word_list())
    parser.add_argument("--selftest", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.selftest:
        selftest()
        print("scan_pdf selftest: PASS")
        return 0

    if args.pdf is None:
        print("ERROR: provide a PDF path", file=sys.stderr)
        return 2
    if not args.pdf.is_file():
        print(f"ERROR: PDF not found: {args.pdf}", file=sys.stderr)
        return 2
    if not args.word_list.is_file():
        print(f"ERROR: word list not found: {args.word_list}", file=sys.stderr)
        return 2

    result = scan_pdf(args.pdf.resolve(), args.word_list.resolve())
    write_json(args.output, result)
    print(
        f"pages={result['page_count']} candidates={result['candidate_count']} "
        f"eligible={str(result['eligible']).lower()} output={args.output}"
    )
    if not result["eligible"]:
        print(
            "ERROR: the PDF has no extractable English text. OCR is required "
            "before it can be annotated.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
