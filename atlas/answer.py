"""Answer: the guard, the retrieval, and the refusal text.

Two front ends sit on this module -- the CLI (`atlas.cli ask`) and the viewer's
Ask screen -- and they must answer identically. So the rules live here once and
are imported, never re-implemented. The viewer inlines `COHORT_PATTERNS`,
`STOP` and `NO_COHORT_REASON` at build time from this file, which means a
pattern added here changes both surfaces and cannot drift.

Retrieval is keyword overlap, not generation: `ranked_matches` can only return
entries that already exist and are already grounded.
"""

from __future__ import annotations

import re

from .rules import CONCEPTS

# Anything that asks for a prediction about students. The corpus holds exam
# papers and solutions; it holds no responses, no marks, no cohort.
COHORT_PATTERNS = (
    r"\b(will|would)\b[^?]{0,50}\b(score|scored|pass|fail|grade)\b",
    r"\bwhat\b[^?]{0,25}\b(score|grade|mark)s?\b[^?]{0,20}\b(will|would|did|do)\b",
    r"\bwhat('s| is) (the |their |my )?(score|grade|mark)s?\b",
    r"\bhow (well|badly)\b[^?]{0,40}\b(students?|they|class|cohort)\b",
    r"\b(did|do|have)\b[^?]{0,20}\b(students?|they|class)\b[^?]{0,40}"
    r"\b(badly|poorly|struggle|struggled)\b",
    r"\bpass(ing)? rate\b",
    r"\bfail(ing)? rate\b",
    r"\b(how many|what percentage|what proportion)\b[^?]{0,40}"
    r"\b(students?|candidates?)\b[^?]{0,40}\b(pass|fail|scored?)\b",
    r"\b(grade|marks?|score) distribution\b",
    r"\b(average|mean|median) (mark|score|grade)s?\b",
    r"\bpredict\b[^?]{0,40}\b(score|outcome|performance|grade|result)\b",
)

NO_COHORT_REASON = (
    "No cohort data is present in this corpus. The exams contain questions and "
    "solutions; they contain no student responses, no marks distribution and no "
    "statistics. Any predicted score would be invented, so none is given."
)

STOP = set(
    "a an the is are was were do does did to of in on for with and or what which how why "
    "students student marks mark lose losing wrong mistake mistakes failure mode modes "
    "about does give me tell show please their they them this that these those".split()
)


def wants_cohort_prediction(question: str) -> bool:
    q = question.lower()
    return any(re.search(p, q) for p in COHORT_PATTERNS)


def terms_of(question: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", question.lower()) if w not in STOP}


def score_entry(entry: dict, terms: set[str]) -> int:
    hay = " ".join(
        [
            entry["title"],
            entry["trigger"],
            entry["wrong_turn"],
            entry["root_misconception"],
            " ".join(CONCEPTS[c]["label"] for c in entry["concepts"] if c in CONCEPTS),
            entry.get("rule_id", ""),
        ]
    ).lower()
    return sum(1 for t in terms if t in hay)


def ranked_matches(question: str, entries: list[dict], k: int = 3) -> list[tuple[int, dict]]:
    """Top-k entries by keyword overlap. Ties keep atlas order, which is rank order."""
    terms = terms_of(question)
    ranked = sorted(
        ((score_entry(e, terms), e) for e in entries), key=lambda t: t[0], reverse=True
    )
    return [(s, e) for s, e in ranked if s > 0][:k]
