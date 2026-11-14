"""Ingest: PDF -> page-mapped text, with an honest coverage report.

Design notes
------------
* We never invent text. If a page has no extractable text layer it is recorded
  as `scanned` and contributes nothing. Silent failure is the one thing this
  project cannot afford.
* `pdftotext -layout` preserves the column/indent structure that the segmenter
  depends on. Extraction artefacts from embedded math fonts are kept verbatim
  rather than cleaned, because every quote we publish must survive a literal
  substring search against this same text layer.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

MIN_TEXT_CHARS_PER_PAGE = 80  # below this, treat the page as image-only


@dataclass
class Page:
    index: int          # 1-based page number in the source document
    text: str
    chars: int
    scanned: bool


@dataclass
class Document:
    doc_id: str         # stable, human-readable: "Robotics1_26.07.13"
    kind: str           # "exam" | "slide" | "syllabus" | "exercise"
    path: str           # relative to corpus root
    pages: list[Page]

    @property
    def n_pages(self) -> int:
        return len(self.pages)

    @property
    def n_scanned(self) -> int:
        return sum(1 for p in self.pages if p.scanned)

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.pages)


def _pdfinfo_pages(path: Path) -> int:
    out = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True).stdout
    m = re.search(r"^Pages:\s*(\d+)", out, re.M)
    return int(m.group(1)) if m else 0


def _pdftotext_pages(path: Path) -> list[str]:
    """One entry per page, split on form feed."""
    out = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        text=True,
        errors="replace",
    ).stdout
    pages = out.split("\f")
    if pages and pages[-1].strip() == "":
        pages.pop()
    return pages


def read_pdf(path: Path, doc_id: str, kind: str, corpus_root: Path) -> Document:
    pages: list[Page] = []
    for i, raw in enumerate(_pdftotext_pages(path), start=1):
        text = raw.rstrip()
        chars = len(text.strip())
        pages.append(
            Page(
                index=i,
                text=text,
                chars=chars,
                scanned=chars < MIN_TEXT_CHARS_PER_PAGE,
            )
        )
    return Document(
        doc_id=doc_id,
        kind=kind,
        path=str(path.relative_to(corpus_root)),
        pages=pages,
    )


def doc_id_of(path: Path) -> str:
    return path.stem


def load_corpus(corpus_root: Path, cache_dir: Path | None = None) -> list[Document]:
    """Read every PDF under corpus_root/<kind>/, caching the parsed pages."""
    docs: list[Document] = []
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)

    for kind in ("exams", "slides", "syllabus", "exercises", "exams_it"):
        folder = corpus_root / kind
        if not folder.is_dir():
            continue
        for pdf in sorted(folder.glob("*.pdf")):
            doc_id = doc_id_of(pdf)
            cache = cache_dir / f"{kind}__{doc_id}.json" if cache_dir else None

            if cache is not None and cache.exists():
                blob = json.loads(cache.read_text())
                docs.append(
                    Document(
                        doc_id=blob["doc_id"],
                        kind=blob["kind"],
                        path=blob["path"],
                        pages=[Page(**p) for p in blob["pages"]],
                    )
                )
                continue

            doc = read_pdf(pdf, doc_id, kind, corpus_root)
            if cache is not None:
                cache.write_text(json.dumps(asdict(doc), ensure_ascii=False))
            docs.append(doc)
    return docs


def coverage(docs: list[Document]) -> dict:
    """The numbers the README is obligated to publish."""
    exams = [d for d in docs if d.kind == "exams"]
    slides = [d for d in docs if d.kind == "slides"]

    def block(sel: list[Document]) -> dict:
        pages = sum(d.n_pages for d in sel)
        scanned = sum(d.n_scanned for d in sel)
        return {
            "documents": len(sel),
            "pages": pages,
            "pages_with_text": pages - scanned,
            "pages_scanned_or_empty": scanned,
            "pct_pages_readable": round(100 * (pages - scanned) / pages, 1) if pages else 0.0,
        }

    return {
        "exams": block(exams),
        "slides": block(slides),
        "ocr_pages": 0,  # nothing was OCR'd; scanned pages are reported, not guessed
        "note": (
            "Scanned pages are counted as unreadable and excluded from analysis. "
            "No OCR was run, so no text on those pages is claimed anywhere."
        ),
    }
