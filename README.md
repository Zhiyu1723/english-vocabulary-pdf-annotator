# English Vocabulary PDF Annotator

A Codex skill that adds concise English explanations to unfamiliar ordinary words in English PDFs.

## What it does

- Uses the bundled learner word list as the only vocabulary.
- Checks each word and common inflected forms against that list.
- Leaves proper nouns untouched.
- Adds line-aligned notes beside the first occurrence of each unfamiliar ordinary word.
- Keeps the original PDF pages and layout.
- Does not append a glossary or other summary page.

## Installation

Clone this repository into the Codex personal skills directory:

```powershell
git clone https://github.com/Zhiyu1723/english-vocabulary-pdf-annotator.git "$env:USERPROFILE\.codex\skills\english-vocabulary-pdf-annotator"
```

Restart Codex if the skill is not discovered immediately.

## Runtime

The helper scripts require Python packages `pdfplumber`, `pypdf`, and `reportlab`. The Codex desktop runtime normally provides them.

## Usage

Attach an English PDF and ask:

> Annotate this English PDF using my installed word list.

The skill writes a separate `.annotated.pdf` and leaves the source file unchanged.
