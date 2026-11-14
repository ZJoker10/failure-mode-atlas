"""Evidence: the schema and the two validators that enforce it.

There are two independent failure modes when you let a machine make claims about
a document, and they need two different checks:

1. STRUCTURAL — is every required field present and well-typed? A schema
   validator catches this. It is what most "no hallucination" claims stop at.

2. GROUNDING  — does the quoted string actually occur, verbatim, on the page
   being cited? A schema validator happily passes a beautiful, entirely invented
   quote. Only the grounding check catches that.

The product is the second check. The schema is table stakes.

Both run on every build. `atlas/build.py` refuses to write `atlas.json` if
either reports a problem, so an unsupported claim cannot reach the viewer.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .ingest import Document

# A quote shorter than this is not evidence, it is a keyword.
MIN_QUOTE_CHARS = 12
MIN_QUOTE_WORDS = 2

STRENGTHS = {"documented", "reconstructed"}

REQUIRED = (
    "id", "title", "trigger", "wrong_turn", "root_misconception", "concepts",
    "evidence", "probe", "correction", "marks_at_risk", "strength", "confidence",
)


@dataclass
class Problem:
    kind: str           # "structural" | "grounding"
    entry_id: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.entry_id}: {self.detail}"


def flatten(s: str) -> str:
    """Collapse all whitespace, preserving case.

    The same transform is applied to a quote and to the page it is checked
    against, so a quote that spans a PDF line break still verifies.
    """
    s = s.replace("\u00ad", "")           # soft hyphen
    return re.sub(r"\s+", " ", s).strip()


def normalise(s: str) -> str:
    """Case-insensitive form used for comparison.

    Extraction inserts line breaks and hyphenation that a human reading the page
    would not see, so quote matching is done on a whitespace-flattened form of
    both sides.
    """
    return flatten(s).lower()


def _page_from_ref(ref: str) -> int | None:
    m = re.search(r"(?:^|\D)(\d{1,3})\s*$", ref or "")
    return int(m.group(1)) if m else None


# --------------------------------------------------------------- structural

def validate_structure(entries: list[dict]) -> list[Problem]:
    problems: list[Problem] = []
    seen: set[str] = set()

    for e in entries:
        eid = str(e.get("id", "<missing id>"))

        for key in REQUIRED:
            if key not in e or e[key] in (None, "", [], {}):
                problems.append(Problem("structural", eid, f"missing required field '{key}'"))

        if eid in seen:
            problems.append(Problem("structural", eid, "duplicate id"))
        seen.add(eid)

        if e.get("strength") not in STRENGTHS:
            problems.append(
                Problem("structural", eid,
                        f"strength must be one of {sorted(STRENGTHS)}, got {e.get('strength')!r}")
            )

        conf = e.get("confidence")
        if not isinstance(conf, (int, float)) or isinstance(conf, bool):
            problems.append(Problem("structural", eid, "confidence must be a number"))
        elif not (0.0 <= float(conf) <= 1.0):
            problems.append(Problem("structural", eid, f"confidence out of range: {conf}"))

        marks = e.get("marks_at_risk")
        if not isinstance(marks, (int, float)) or isinstance(marks, bool):
            problems.append(Problem("structural", eid, "marks_at_risk must be a number"))
        elif not math.isfinite(float(marks)) or marks < 0:
            problems.append(Problem("structural", eid, f"marks_at_risk invalid: {marks}"))

        if not isinstance(e.get("concepts"), list) or not e["concepts"]:
            problems.append(Problem("structural", eid, "concepts must be a non-empty list"))

        ev = e.get("evidence")
        if not isinstance(ev, dict):
            problems.append(Problem("structural", eid, "evidence must be an object"))
            continue

        exam = ev.get("exam")
        if not isinstance(exam, dict):
            problems.append(Problem("structural", eid, "evidence.exam is mandatory"))
        else:
            for k in ("doc", "ref", "quote"):
                if not str(exam.get(k) or "").strip():
                    problems.append(
                        Problem("structural", eid, f"evidence.exam.{k} is empty — entry rejected")
                    )
            q = str(exam.get("quote") or "")
            if q and (len(q) < MIN_QUOTE_CHARS or len(q.split()) < MIN_QUOTE_WORDS):
                problems.append(
                    Problem("structural", eid,
                            f"evidence.exam.quote is too short to be evidence ({q!r})")
                )

        lecture = ev.get("lecture")
        if lecture is not None:
            if not isinstance(lecture, dict):
                problems.append(Problem("structural", eid, "evidence.lecture must be object or null"))
            else:
                for k in ("doc", "ref", "quote"):
                    if not str(lecture.get(k) or "").strip():
                        problems.append(
                            Problem("structural", eid, f"evidence.lecture.{k} is empty")
                        )
    return problems


# ----------------------------------------------------------------- grounding

def validate_grounding(entries: list[dict], docs: list[Document]) -> list[Problem]:
    """Every quote must appear verbatim on the page it cites."""
    problems: list[Problem] = []
    index: dict[str, Document] = {d.doc_id: d for d in docs}

    def check(entry_id: str, slot: str, ev: dict | None) -> None:
        if not ev:
            return
        doc_id = str(ev.get("doc") or "")
        ref = str(ev.get("ref") or "")
        quote = str(ev.get("quote") or "")

        doc = index.get(doc_id) or index.get(doc_id.replace(".pdf", ""))
        if doc is None:
            problems.append(Problem("grounding", entry_id, f"{slot}: unknown document {doc_id!r}"))
            return

        page_no = _page_from_ref(ref)
        if page_no is None:
            problems.append(Problem("grounding", entry_id, f"{slot}: cannot read page from ref {ref!r}"))
            return
        if not (1 <= page_no <= doc.n_pages):
            problems.append(
                Problem("grounding", entry_id,
                        f"{slot}: page {page_no} outside {doc_id} (has {doc.n_pages} pages)")
            )
            return

        page = doc.pages[page_no - 1]
        if page.scanned:
            problems.append(
                Problem("grounding", entry_id,
                        f"{slot}: page {page_no} of {doc_id} has no text layer to verify against")
            )
            return

        if normalise(quote) not in normalise(page.text):
            problems.append(
                Problem("grounding", entry_id,
                        f"{slot}: quote not found on {doc_id} p.{page_no} — "
                        f"{quote[:70]!r}")
            )

    for e in entries:
        eid = str(e.get("id", "<missing>"))
        ev = e.get("evidence") or {}
        check(eid, "exam", ev.get("exam"))
        check(eid, "lecture", ev.get("lecture"))

    return problems


def validate(entries: list[dict], docs: list[Document]) -> list[Problem]:
    return validate_structure(entries) + validate_grounding(entries, docs)


# ------------------------------------------------------------------- refusal

@dataclass
class Refusal:
    """A first-class outcome. The absence of evidence is a result, not an error."""

    question: str
    reason: str
    code: str

    def as_dict(self) -> dict:
        return {"refused": True, "question": self.question,
                "reason": self.reason, "code": self.code}


def refuse_no_cohort(question: str) -> Refusal:
    return Refusal(
        question=question,
        reason=(
            "No cohort data is present in this corpus. The exams contain questions and "
            "solutions; they contain no student responses, no marks distribution and no "
            "statistics. Any predicted score would be invented, so none is given."
        ),
        code="NO_COHORT_DATA",
    )


def refuse_no_corpus(question: str, path: str) -> Refusal:
    return Refusal(
        question=question,
        reason=(
            f"No readable course material was found at '{path}'. The atlas is built only "
            "from documents it can cite, so with an empty corpus there is nothing to report."
        ),
        code="NO_CORPUS",
    )
