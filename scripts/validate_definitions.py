from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lexicon import (
    default_word_list,
    definition_words,
    is_known_word,
    lemma_candidates,
    load_word_list,
    normalize_word,
)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def validate(scan: dict, definitions: dict, lexicon: set[str]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    candidates = {
        candidate["id"]: candidate for candidate in scan.get("candidates", [])
    }
    entries = definitions.get("entries")
    if not isinstance(entries, list):
        return {
            "ok": False,
            "errors": ["definitions.json must contain an entries array"],
            "warnings": [],
            "covered_ids": [],
            "entry_count": 0,
        }

    covered: dict[str, str] = {}
    seen_words: set[str] = set()
    proper_noun_ids: set[str] = set()

    proper_nouns = definitions.get("proper_nouns", [])
    if proper_nouns is None:
        proper_nouns = []
    if not isinstance(proper_nouns, list):
        errors.append("proper_nouns must be an array")
        proper_nouns = []
    for index, item in enumerate(proper_nouns, start=1):
        label = f"proper noun {index}"
        if not isinstance(item, dict):
            errors.append(f"{label}: must be an object")
            continue
        item_id = str(item.get("id", "")).strip()
        if item_id not in candidates:
            errors.append(f"{label}: unknown scan id {item_id!r}")
            continue
        if item_id in proper_noun_ids:
            errors.append(f"{label}: duplicate scan id {item_id!r}")
        if not str(item.get("reason", "")).strip():
            errors.append(f"{label}: missing reason")
        proper_noun_ids.add(item_id)

    for index, entry in enumerate(entries, start=1):
        label = f"entry {index}"
        primary_id = str(entry.get("id", "")).strip()
        if not primary_id:
            errors.append(f"{label}: missing id")
            continue
        ids = [primary_id]
        also_ids = entry.get("also_ids", [])
        if also_ids is None:
            also_ids = []
        if not isinstance(also_ids, list) or not all(
            isinstance(value, str) and value.strip() for value in also_ids
        ):
            errors.append(f"{label}: also_ids must be an array of ids")
            also_ids = []
        ids.extend(value.strip() for value in also_ids)

        for item_id in ids:
            if item_id not in candidates:
                errors.append(f"{label}: unknown scan id {item_id!r}")
                continue
            if item_id in covered:
                errors.append(
                    f"{label}: scan id {item_id!r} is also covered by {covered[item_id]!r}"
                )
            else:
                covered[item_id] = primary_id

        if primary_id not in candidates:
            continue

        target = candidates[primary_id]
        target_normalized = normalize_word(str(entry.get("word", "")))
        if not target_normalized:
            errors.append(f"{label}: missing word")
        if target_normalized in seen_words:
            errors.append(f"{label}: duplicate definition headword {entry.get('word')!r}")
        seen_words.add(target_normalized)

        definition = str(entry.get("definition_en", "")).strip()
        words = definition_words(definition)
        if not words:
            errors.append(f"{label}: definition_en is empty")
        if len(words) > 20:
            errors.append(
                f"{label}: definition_en has {len(words)} words; keep it at 20 or fewer"
            )
        elif len(words) > 12:
            warnings.append(
                f"{label}: definition_en has {len(words)} words; a shorter phrase is preferred"
            )

        covered_forms: set[str] = set()
        for item_id in ids:
            candidate = candidates.get(item_id)
            if candidate:
                covered_forms.add(normalize_word(str(candidate["word"])))
        related = (
            not target_normalized
            or target_normalized in covered_forms
            or any(
                target_normalized in lemma_candidates(form)
                or form in lemma_candidates(target_normalized)
                for form in covered_forms
            )
        )
        if not related:
            warnings.append(
                f"{label}: verify that {entry.get('word')!r} is the shared "
                f"dictionary headword for {sorted(covered_forms)}"
            )

        forbidden = lemma_candidates(target_normalized)
        if target_normalized:
            forbidden.add(target_normalized)
        for form in covered_forms:
            forbidden.add(form)
            forbidden.update(lemma_candidates(form))
        for word in words:
            if word in forbidden:
                errors.append(
                    f"{label}: definition_en repeats the target word {word!r}"
                )
            if not is_known_word(word, lexicon):
                errors.append(
                    f"{label}: definition_en uses a word outside the permitted list: {word!r}"
                )

    for item_id in sorted(set(covered) & proper_noun_ids):
        errors.append(
            f"scan id {item_id!r} is both defined and classified as a proper noun"
        )

    uncovered = sorted(set(candidates) - set(covered) - proper_noun_ids)
    for item_id in uncovered:
        errors.append(f"scan id {item_id!r} has no definition")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "entry_count": len(entries),
        "candidate_count": len(candidates),
        "covered_ids": sorted(covered),
        "proper_noun_ids": sorted(proper_noun_ids),
        "uncovered_ids": uncovered,
    }


def selftest() -> None:
    lexicon = load_word_list(default_word_list())
    scan = {
        "candidates": [
            {
                "id": "p001-w0001-photosynthesis",
                "word": "photosynthesis",
                "normalized": "photosynthesis",
            },
            {
                "id": "p001-w0002-amazon",
                "word": "Amazon",
                "normalized": "amazon",
            },
            {
                "id": "p001-w0003-talk",
                "word": "talk",
                "normalized": "talk",
            },
            {
                "id": "p001-w0004-talked",
                "word": "talked",
                "normalized": "talked",
            },
            {
                "id": "p001-w0005-transients",
                "word": "transients",
                "normalized": "transients",
            },
        ]
    }
    valid = {
        "entries": [
            {
                "id": "p001-w0001-photosynthesis",
                "word": "photosynthesis",
                "definition_en": "how green plants make food from light",
            },
            {
                "id": "p001-w0003-talk",
                "also_ids": ["p001-w0004-talked"],
                "word": "talk",
                "definition_en": "to say words",
            },
            {
                "id": "p001-w0005-transients",
                "word": "transient",
                "definition_en": "short events that soon disappear",
            }
        ],
        "proper_nouns": [
            {
                "id": "p001-w0002-amazon",
                "word": "Amazon",
                "reason": "organization name",
            }
        ],
    }
    invalid = json.loads(json.dumps(valid))
    invalid["entries"][0]["definition_en"] = "a zzqx process"
    assert validate(scan, valid, lexicon)["ok"]
    assert not validate(scan, invalid, lexicon)["ok"]
    wrongly_annotated = json.loads(json.dumps(valid))
    wrongly_annotated["entries"].append(
        {
            "id": "p001-w0002-amazon",
            "word": "Amazon",
            "definition_en": "a river",
        }
    )
    assert not validate(scan, wrongly_annotated, lexicon)["ok"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate definitions against the installed learner word list."
    )
    parser.add_argument("--scan", type=Path)
    parser.add_argument("--definitions", type=Path)
    parser.add_argument("--word-list", type=Path, default=default_word_list())
    parser.add_argument("--report", type=Path)
    parser.add_argument("--selftest", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.selftest:
        selftest()
        print("validate_definitions selftest: PASS")
        return 0
    if args.scan is None or args.definitions is None:
        print("ERROR: provide --scan and --definitions", file=sys.stderr)
        return 2

    lexicon = load_word_list(args.word_list)
    report = validate(load_json(args.scan), load_json(args.definitions), lexicon)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")

    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    for error in report["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)
    print(
        f"entries={report['entry_count']} candidates={report['candidate_count']} "
        f"ok={str(report['ok']).lower()}"
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
