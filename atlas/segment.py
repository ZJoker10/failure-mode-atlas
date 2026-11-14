"""Segment: exam PDF -> exercises -> task clauses, each carrying a page anchor.

Why this is fussy
-----------------
The corpus spans 2003-2026 and two formatting eras. Newer papers use
`Exercise N`; older ones ("Robotics I", 2009-2012) drop the heading entirely and
use bullets or roman numerals. Both are handled, and every clause records the
page it starts on so an evidence quote can be checked against that exact page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ingest import Document

# ---------------------------------------------------------------- primitives

TASK_VERBS = (
    "determine|compute|calculate|assign|derive|find|provide|sketch|draw|evaluate|"
    "solve|discuss|show|prove|demonstrate|justify|verify|explain|compare|give|"
    "write|obtain|design|choose|comment|analyse|analyze|state|list|specify|"
    "express|identify|report|plot|estimate|indicate|describe|is it possible|"
    "what|which|how many|why"
)
TASK_RE = re.compile(rf"\b(?:{TASK_VERBS})\b", re.I)

BULLET_RE = re.compile(r"^\s*[•·▪◦*-]\s+(.*)$")
LETTERED_RE = re.compile(r"^\s{0,4}([a-h])[\)\.]\s+(.*)$")
PAREN_LETTER_RE = re.compile(r"^\s{0,4}\(([a-h])\)\s*(.*)$")
ROMAN_RE = re.compile(r"^\s{0,4}([ivx]{1,4})[\)\.]\s+(.*)$")

EXERCISE_RE = re.compile(
    r"^\s*(?:Exercise|Question)\s*#?\s*(\d+)\s*"
    r"(?:[\[(][^\n\])]{0,40}[\])])?\s*$",
    re.M,
)
# Solution sections are introduced in several ways across 2003-2026. Only a
# standalone header line counts, because "solution" also appears inside ordinary
# prose ("express the solution (or solutions) ...") that belongs to the question.
SOLUTION_RE = re.compile(
    r"^\s*(?:Solution[s]?(?:\s+of[^\n]{0,60})?|Soluzion[ei](?:\s+[^\n]{0,40})?|"
    r"Svolgimento[^\n]{0,40})\s*$",
    re.M | re.I,
)


@dataclass
class Clause:
    """One thing the student is asked to do. The atom of the whole atlas."""

    ref: str            # "Robotics1_26.07.13 / Exercise 1 / a"
    label: str          # "a", "2", "clause 3"
    text: str           # verbatim, as extracted
    page: int           # 1-based page the clause starts on


@dataclass
class Exercise:
    exam_id: str
    number: int
    page_start: int
    page_end: int
    text: str
    clauses: list[Clause] = field(default_factory=list)
    has_solution: bool = False

    @property
    def ref(self) -> str:
        return f"{self.exam_id} / Exercise {self.number}"


# ---------------------------------------------------------------- page maths

def _page_offsets(doc: Document) -> list[int]:
    """Cumulative character offset of each page's start within doc.text."""
    offsets, run = [], 0
    for p in doc.pages:
        offsets.append(run)
        run += len(p.text) + 1  # +1 for the "\n" joiner used by Document.text
    return offsets


def _page_of(offsets: list[int], pos: int) -> int:
    page = 1
    for i, start in enumerate(offsets, start=1):
        if start <= pos:
            page = i
        else:
            break
    return page


# ------------------------------------------------------------------ clauses

def _dedent(block: str) -> str:
    lines = block.splitlines()
    indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    cut = min(indents) if indents else 0
    return "\n".join(l[cut:] if len(l) > cut else "" for l in lines)


def _clauses_from_block(block: str, page_start: int, base_ref: str) -> list[Clause]:
    """Prefer explicit item markers; fall back to task-verb sentences."""
    lines = block.splitlines()

    # 1. explicit markers, in the order the corpus prefers
    for pattern, kind in (
        (LETTERED_RE, "letter"),
        (PAREN_LETTER_RE, "letter"),
        (ROMAN_RE, "roman"),
        (BULLET_RE, "bullet"),
    ):
        items: list[tuple[str, list[str]]] = []
        for line in lines:
            m = pattern.match(line)
            if m:
                if kind == "bullet":
                    items.append((str(len(items) + 1), [m.group(1)]))
                else:
                    items.append((m.group(1), [m.group(2)]))
            elif items and line.strip():
                items[-1][1].append(line.strip())
        if len(items) >= 2:
            return [
                Clause(
                    ref=f"{base_ref} / {label}",
                    label=label,
                    text=" ".join(part).strip(),
                    page=page_start,
                )
                for label, part in items
            ]

    # 2. sentence fallback, keeping only sentences that ask for something
    flat = re.sub(r"\s+", " ", block).strip()
    sentences = re.split(r"(?<=[.?])\s+(?=[A-Z(])", flat)
    out, n = [], 0
    for s in sentences:
        s = s.strip()
        if len(s) < 25 or not TASK_RE.search(s):
            continue
        n += 1
        out.append(Clause(ref=f"{base_ref} / clause {n}", label=str(n), text=s, page=page_start))
    if not out:
        out.append(Clause(ref=f"{base_ref} / clause 1", label="1", text=flat[:400], page=page_start))
    return out


# ------------------------------------------------------------------ exercises

def segment_exam(doc: Document) -> list[Exercise]:
    text = doc.text
    offsets = _page_offsets(doc)

    # Everything after the solutions header is answers, not questions.
    sol = SOLUTION_RE.search(text)
    question_region = text[: sol.start()] if sol else text
    has_solution = sol is not None

    heads = list(EXERCISE_RE.finditer(question_region))
    exercises: list[Exercise] = []

    if heads:
        for i, m in enumerate(heads):
            start = m.end()
            end = heads[i + 1].start() if i + 1 < len(heads) else len(question_region)
            block = question_region[start:end]
            ex = Exercise(
                exam_id=doc.doc_id,
                number=int(m.group(1)),
                page_start=_page_of(offsets, m.start()),
                page_end=_page_of(offsets, max(start, end - 1)),
                text=_dedent(block).strip(),
                has_solution=has_solution,
            )
            ex.clauses = _clauses_from_block(
                _dedent(block), ex.page_start, ex.ref
            )
            exercises.append(ex)
        return exercises

    # Older papers: no `Exercise N` heading. Treat the body (minus the title
    # block) as one exercise and let the clause splitter carve it up.
    # The title block is skipped by measuring its length rather than deleting
    # it, so character offsets stay valid against `question_region`.
    skip = 0
    for line in question_region.splitlines(keepends=True):
        s = line.strip()
        is_title = (
            not s
            or re.fullmatch(r"Robotics\s+I{1,2}", s) is not None
            or re.fullmatch(r"[A-Z][a-z]+ \d{1,2}, \d{4}", s) is not None
        )
        if not is_title:
            break
        skip += len(line)

    body = question_region[skip:]
    if len(body.strip()) < 120:
        return []
    ex = Exercise(
        exam_id=doc.doc_id,
        number=1,
        page_start=_page_of(offsets, skip),
        page_end=doc.n_pages,
        text=_dedent(body).strip(),
        has_solution=has_solution,
    )
    ex.clauses = _clauses_from_block(_dedent(body), ex.page_start, ex.ref)
    exercises.append(ex)
    return exercises


def segment_corpus(docs: list[Document]) -> list[Exercise]:
    out: list[Exercise] = []
    for d in docs:
        if d.kind != "exams":
            continue
        out.extend(segment_exam(d))
    return out
