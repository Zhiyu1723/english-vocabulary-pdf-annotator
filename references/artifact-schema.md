# Artifact schema

## `scan.json`

`scripts/scan_pdf.py` creates this file. Its important fields are:

```json
{
  "source_pdf": "/absolute/input.pdf",
  "source_sha256": "...",
  "eligible": true,
  "eligibility_evidence": ["page 1: extractable English text"],
  "lexicon_size": 3125,
  "candidates": [
    {
      "id": "p001-w0007-photosynthesis",
      "word": "photosynthesis",
      "normalized": "photosynthesis",
      "page": 1,
      "line_index": 6,
      "bbox": [123.4, 201.2, 191.8, 210.1],
      "line_top": 200.8,
      "line_bottom": 211.0,
      "font_size": 10.5,
      "line": "Plants use photosynthesis to make food.",
      "context": "Plants use photosynthesis to make food."
    }
  ]
}
```

The candidate list contains one first occurrence per normalized unfamiliar surface form. Keep its `id`, `page`, and `bbox` unchanged when creating definitions.

## `definitions.json`

```json
{
  "entries": [
    {
      "id": "p001-w0007-photosynthesis",
      "word": "photosynthesis",
      "definition_en": "how green plants make food from light"
    }
  ],
  "proper_nouns": [
    {
      "id": "p001-w0002-amazon",
      "word": "Amazon",
      "reason": "organization name"
    }
  ]
}
```

All entry fields are required. `word` is the dictionary headword used to share an explanation, not necessarily the exact form at the first scan id. Merge every known inflection through `id` and `also_ids`. `definition_en` must be a short English phrase that does not repeat the headword or any merged form. Its words must pass the bundled vocabulary check.

Every unfamiliar ordinary word must have a definition entry. A proper noun instead goes under `proper_nouns` with its scan id, displayed word, and a short English reason. Proper nouns receive no annotation. The `proper_nouns` array may be omitted when empty.

If scan ids represent inflections of one headword, keep one id in the definition entry and list every additional id in `also_ids`. This applies to noun plurals and verb forms such as third-person, past, participle, and gerund forms. The renderer places the shared explanation at each listed first occurrence.

```json
{
  "id": "p001-w0007-talk",
  "also_ids": ["p003-w0012-talked", "p005-w0009-talking"],
  "word": "talk",
  "definition_en": "to say words"
}
```

This file is internal annotation data. The renderer does not append it or any glossary to the PDF.
