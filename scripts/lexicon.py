from __future__ import annotations

import re
from pathlib import Path


WORD_RE = re.compile(r"[A-Za-z]+(?:['\u2019.-][A-Za-z]+)*")
ALPHA_RE = re.compile(r"[A-Za-z]+")

CONTRACTIONS = {
    "aren't": ("are", "not"),
    "can't": ("can", "not"),
    "couldn't": ("could", "not"),
    "didn't": ("did", "not"),
    "doesn't": ("does", "not"),
    "don't": ("do", "not"),
    "hadn't": ("had", "not"),
    "hasn't": ("has", "not"),
    "haven't": ("have", "not"),
    "he'd": ("he", "would"),
    "he'll": ("he", "will"),
    "he's": ("he", "be"),
    "i'd": ("i", "would"),
    "i'll": ("i", "will"),
    "i'm": ("i", "be"),
    "i've": ("i", "have"),
    "isn't": ("is", "not"),
    "it'd": ("it", "would"),
    "it'll": ("it", "will"),
    "it's": ("it", "be"),
    "let's": ("let", "us"),
    "mightn't": ("might", "not"),
    "mustn't": ("must", "not"),
    "needn't": ("need", "not"),
    "shan't": ("shall", "not"),
    "she'd": ("she", "would"),
    "she'll": ("she", "will"),
    "she's": ("she", "be"),
    "shouldn't": ("should", "not"),
    "that's": ("that", "be"),
    "there's": ("there", "be"),
    "they'd": ("they", "would"),
    "they'll": ("they", "will"),
    "they're": ("they", "be"),
    "they've": ("they", "have"),
    "wasn't": ("was", "not"),
    "we'd": ("we", "would"),
    "we'll": ("we", "will"),
    "we're": ("we", "be"),
    "we've": ("we", "have"),
    "weren't": ("were", "not"),
    "what's": ("what", "be"),
    "where's": ("where", "be"),
    "who's": ("who", "be"),
    "won't": ("will", "not"),
    "wouldn't": ("would", "not"),
    "you'd": ("you", "would"),
    "you'll": ("you", "will"),
    "you're": ("you", "be"),
    "you've": ("you", "have"),
}

IRREGULAR_LEMMAS = {
    "am": "be",
    "are": "be",
    "been": "be",
    "being": "be",
    "is": "be",
    "was": "be",
    "were": "be",
    "became": "become",
    "began": "begin",
    "begun": "begin",
    "bent": "bend",
    "better": "good",
    "best": "good",
    "bought": "buy",
    "brought": "bring",
    "built": "build",
    "came": "come",
    "children": "child",
    "chose": "choose",
    "chosen": "choose",
    "criteria": "criterion",
    "data": "datum",
    "did": "do",
    "does": "do",
    "done": "do",
    "drank": "drink",
    "drunk": "drink",
    "drove": "drive",
    "driven": "drive",
    "ate": "eat",
    "eaten": "eat",
    "fell": "fall",
    "fallen": "fall",
    "felt": "feel",
    "feet": "foot",
    "fought": "fight",
    "found": "find",
    "flew": "fly",
    "flown": "fly",
    "forgot": "forget",
    "forgotten": "forget",
    "gave": "give",
    "geese": "goose",
    "given": "give",
    "went": "go",
    "gone": "go",
    "grew": "grow",
    "grown": "grow",
    "had": "have",
    "has": "have",
    "heard": "hear",
    "hid": "hide",
    "hidden": "hide",
    "held": "hold",
    "kept": "keep",
    "knew": "know",
    "known": "know",
    "led": "lead",
    "left": "leave",
    "lice": "louse",
    "lost": "lose",
    "made": "make",
    "meant": "mean",
    "men": "man",
    "met": "meet",
    "mice": "mouse",
    "paid": "pay",
    "people": "person",
    "phenomena": "phenomenon",
    "oxen": "ox",
    "ran": "run",
    "rose": "rise",
    "risen": "rise",
    "said": "say",
    "sang": "sing",
    "sung": "sing",
    "saw": "see",
    "seen": "see",
    "sold": "sell",
    "sent": "send",
    "shone": "shine",
    "shook": "shake",
    "shaken": "shake",
    "showed": "show",
    "shown": "show",
    "slept": "sleep",
    "spoke": "speak",
    "spoken": "speak",
    "spent": "spend",
    "stood": "stand",
    "stole": "steal",
    "stolen": "steal",
    "swam": "swim",
    "swum": "swim",
    "took": "take",
    "taken": "take",
    "taught": "teach",
    "teeth": "tooth",
    "thought": "think",
    "threw": "throw",
    "thrown": "throw",
    "told": "tell",
    "understood": "understand",
    "woke": "wake",
    "woken": "wake",
    "women": "woman",
    "wore": "wear",
    "worn": "wear",
    "won": "win",
    "worse": "bad",
    "worst": "bad",
    "wrote": "write",
    "written": "write",
}

JOINED_ENTRY_REPAIRS = {
    "bike(=bicycle)bill": ("bike", "bicycle", "bill"),
    "ceremonycertain": ("ceremony", "certain"),
    "commercialcommit": ("commercial", "commit"),
    "exerciseexhaust": ("exercise", "exhaust"),
    "insteadinstitute": ("instead", "institute"),
    "policeman/policewomanpolicy": ("policeman", "policewoman", "policy"),
    "wolfwoman": ("wolf", "woman"),
    "yourselfyouth": ("yourself", "youth"),
}


def normalize_word(value: str) -> str:
    value = value.replace("\u2019", "'").replace("\u2018", "'")
    value = value.replace("\u2010", "-").replace("\u2011", "-")
    value = value.replace("\u2012", "-").replace("\u2013", "-").replace("\u2014", "-")
    value = value.casefold().strip()
    value = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", value)
    value = re.sub(r"-+", "-", value)
    return value


def display_word(value: str) -> str:
    match = WORD_RE.search(value)
    if match:
        return match.group(0)
    return value.strip()


def _add_undouble(value: str, suffix: str) -> list[str]:
    if not value.endswith(suffix):
        return []
    stem = value[: -len(suffix)]
    candidates: list[str] = []
    if stem:
        candidates.append(stem)
        if stem[-1:] == stem[-2:-1]:
            candidates.append(stem[:-1])
    return candidates


def lemma_candidates(value: str) -> set[str]:
    word = normalize_word(value)
    candidates = {word}
    if not word:
        return candidates

    if word.endswith("'s"):
        candidates.add(word[:-2])
    if word.endswith("s'") and len(word) > 2:
        candidates.add(word[:-2])

    if word in IRREGULAR_LEMMAS:
        candidates.add(IRREGULAR_LEMMAS[word])

    expansion = CONTRACTIONS.get(word)
    if expansion:
        candidates.update(normalize_word(part) for part in expansion)

    if word.endswith("ies") and len(word) > 4:
        candidates.add(word[:-3] + "y")
    if word.endswith("ves") and len(word) > 4:
        candidates.add(word[:-3] + "f")
        candidates.add(word[:-3] + "fe")
    if word.endswith("oes") and len(word) > 4:
        candidates.add(word[:-2])
    if word.endswith("es") and len(word) > 3:
        candidates.add(word[:-2])
    if word.endswith("s") and len(word) > 2 and not word.endswith("ss"):
        candidates.add(word[:-1])

    if word.endswith("ied") and len(word) > 4:
        candidates.add(word[:-3] + "y")
    if word.endswith("ed") and len(word) > 3:
        candidates.add(word[:-2])
        candidates.add(word[:-1])
        candidates.update(_add_undouble(word, "ed"))

    if word.endswith("ing") and len(word) > 4:
        candidates.add(word[:-3])
        candidates.add(word[:-3] + "e")
        candidates.update(_add_undouble(word, "ing"))

    if word.endswith("ier") and len(word) > 4:
        candidates.add(word[:-3] + "y")
    if word.endswith("iest") and len(word) > 5:
        candidates.add(word[:-4] + "y")
    if word.endswith("er") and len(word) > 3:
        candidates.add(word[:-2])
        candidates.add(word[:-1])
        candidates.update(_add_undouble(word, "er"))
    if word.endswith("est") and len(word) > 4:
        candidates.add(word[:-3])
        candidates.add(word[:-2])
        candidates.update(_add_undouble(word, "est"))

    candidates.discard("")
    return candidates


def _extract_entry_forms(entry: str) -> set[str]:
    forms: set[str] = set()
    whole = normalize_word(entry)
    if whole and not any(ch in whole for ch in "()/="):
        forms.add(whole)
    for run in ALPHA_RE.findall(entry):
        normalized = normalize_word(run)
        if normalized:
            forms.add(normalized)
    return forms


def _recover_joined_entries(forms: set[str]) -> set[str]:
    recovered = set(forms)
    core = {word for word in forms if len(word) >= 3 and "-" not in word and "'" not in word}
    for word in sorted(forms, key=len, reverse=True):
        if len(word) < 8 or not word.isalpha():
            continue
        for split in range(3, len(word) - 2):
            left, right = word[:split], word[split:]
            if left in core and right in core:
                recovered.add(left)
                recovered.add(right)
                break
    return recovered


def load_word_list(path: str | Path) -> set[str]:
    forms: set[str] = set()
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        for line in stream:
            entry = line.strip()
            if entry:
                forms.update(_extract_entry_forms(entry))
                forms.update(JOINED_ENTRY_REPAIRS.get(normalize_word(entry), ()))
    return _recover_joined_entries(forms)


def is_known_word(value: str, lexicon: set[str]) -> bool:
    word = normalize_word(value)
    if not word:
        return True
    if word in lexicon:
        return True

    expansion = CONTRACTIONS.get(word)
    if expansion:
        expanded = [normalize_word(part) for part in expansion]
        if all(part in lexicon for part in expanded):
            return True

    return any(candidate in lexicon for candidate in lemma_candidates(word))


def definition_words(definition: str) -> list[str]:
    return [normalize_word(token) for token in WORD_RE.findall(definition) if token]


def default_word_list() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "word-list.txt"


def selftest() -> None:
    lexicon = load_word_list(default_word_list())
    assert "photosynthesis" not in lexicon
    assert "plant" in lexicon
    assert "according" in lexicon and "to" in lexicon
    assert "advertisement" in lexicon
    assert "bicycle" in lexicon and "bill" in lexicon
    assert "policewoman" in lexicon and "policy" in lexicon
    assert "wolf" in lexicon and "woman" in lexicon
    assert is_known_word("plants", lexicon)
    assert is_known_word("studied", lexicon) or is_known_word("study", lexicon)
    assert is_known_word("running", lexicon) or is_known_word("run", lexicon)
    assert is_known_word("don't", lexicon) or (
        "do" in lexicon and "not" in lexicon
    )
    assert not is_known_word("photosynthesis", lexicon)


if __name__ == "__main__":
    selftest()
    print("lexicon selftest: PASS")
