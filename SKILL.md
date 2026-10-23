---
name: english-vocabulary-pdf-annotator
description: Use when the user provides any English-language PDF and wants unfamiliar ordinary words explained from a fixed learner word list. Works for general, technical, academic, news, and simplified English PDFs; annotates only non-proper words absent from the bundled list and does not append a glossary.
metadata:
  short-description: Annotate any English PDF against the learner's word list
---

# English Vocabulary PDF Annotator

Produce a new study edition of the PDF. Preserve every source page, its text, images, tables, and layout. At the first occurrence of each ordinary word that is not known from the bundled word list, add a short English explanation in parentheses. Do not append a vocabulary list, glossary, index, or other summary page.

Do not annotate proper nouns. Exclude person names, place names, organization and institution names, brands and product names, named events or works, language and nationality names, and similar proper names from all annotations and note pages.

Treat the installed [word-list.txt](assets/word-list.txt) as the authoritative vocabulary. Do not silently replace it with a general dictionary or with a newer list unless the user explicitly supplies one.

## Eligibility and success conditions

Apply this workflow to every English-language PDF the user supplies. Do not require the PDF to call itself simplified, easy, graded, or learner-oriented, and do not require any special phrase in the title or metadata.

A successful result:

- keeps the source PDF unchanged and writes a separate `.annotated.pdf`;
- explains each distinct unfamiliar word only at its first occurrence;
- writes no annotation for any proper noun;
- considers a word known when either its normalized surface form or a supported inflected form maps to the word list;
- uses only words or matching forms from the bundled list in every English explanation;
- gives concise explanations, normally 3-10 words;
- appends no word list or glossary after the source pages;
- contains no clipped, overlapping, crossing-leader, or unreadable annotations.

## Workflow

1. Read the full PDF text and confirm that its main readable content is English. Record which pages contain extractable text.
2. Use the available Python runtime to scan the PDF:

   ```bash
   python scripts/scan_pdf.py INPUT.pdf --output work/scan.json
   ```

   The scan compares surface forms and conservative inflections against the bundled list. Do not mark a word unfamiliar merely because a substring of it appears in the list.

3. Review `scan.json` in reading order. When inflected forms share one meaning, group their scan ids under the dictionary headword you judge correct and reuse one explanation. Keep genuinely different words separate. Classify proper nouns and record their scan ids under `proper_nouns`; do not create definitions for them.
4. Write `definitions.json` from the remaining scan entries. Use [references/artifact-schema.md](references/artifact-schema.md) for the exact fields.
5. For every English explanation:
   - use only vocabulary forms allowed by the bundled list;
   - make the meaning clear from the surrounding context;
   - avoid the target word and circular definitions;
   - keep it as short as clarity allows.

6. Validate the complete definition set before touching the PDF:

   ```bash
   python scripts/validate_definitions.py --scan work/scan.json --definitions definitions.json
   ```

   Resolve every missing entry and every vocabulary violation. The only permitted omission is a scan id explicitly recorded as a proper noun. Do not weaken the check.
7. Render the study edition:

   ```bash
   python scripts/render_study_pdf.py INPUT.pdf --scan work/scan.json --definitions definitions.json --output OUTPUT.pdf
   ```

8. Open or render the output and inspect:
   - the first page with an annotation;
   - every page containing dense annotations;
   - the final source page and any continuation note pages;
   - any page with rotated text, unusual columns, or large figures.

   If an annotation covers source text, shorten its explanation or rerun the renderer after improving placement. Never accept an annotation merely because it was written successfully.

9. Verify the output reopens, every source page is preserved, no glossary or other end-of-PDF word list exists, and the source file is untouched.

## Recognition boundary

The scanner is deliberately conservative. It handles common plurals, tense endings, gerunds, comparison forms, possessives, contractions, and common irregular forms. For an unfamiliar irregular form not handled by the scanner, inspect the word list and decide manually; record that decision in `scan.json` only when needed.

Capitalization alone does not make a word unfamiliar. Hyphenated compounds are known only when their full normalized form or a supported variant is in the list.

Capitalization alone also does not prove that a word is a proper noun: an ordinary word may be capitalized at the start of a sentence or in a title. Judge proper-noun status from the surrounding context. When a candidate is likely a name and the context is genuinely ambiguous, skip it rather than annotating it.

## Annotation layout

Keep the original page content at its existing size and position. For pages with unfamiliar words, extend the page to the right and add a narrow vocabulary-note column. Highlight each target word and show a small number beside it. Group notes that belong to the same source line into one compact side-column card, aligned vertically with that line. This keeps every explanation close to its source line even when a line contains several unfamiliar words.

Do not draw lines or arrows between words and notes. The highlighted word, matching number, and line-aligned card provide the association without cluttering the source page or crossing other text.

If a page has more notes than the side column can hold, put only the remaining numbered notes on a continuation note page after all source pages. These pages are part of the annotations, not a glossary. Keep every target marked and preserve the same numbering.

## Failure handling

- If pages are scanned images with no text layer, OCR is required before scanning. Report any OCR uncertainty and do not invent word positions.
- If the PDF is encrypted and cannot be read without a password, stop and request the password or an unlocked copy.
- If the source has rotated pages that the renderer cannot place reliably, keep the original pages and use a slightly displaced callout only after visual inspection, or report the unsupported pages.
- If an explanation cannot be expressed with the permitted vocabulary, shorten it or choose a different known synonym. Do not borrow outside English vocabulary.
