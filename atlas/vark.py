"""VARK: twelve questions, four counts, one saved preference.

VARK asks how you *prefer* to take material in. It is a preference
questionnaire, not a diagnosis: it does not measure ability, it does not predict
marks, and the evidence that matching teaching to a preferred modality improves
outcomes is weak. What it is good for is a concrete, arguable design decision —
which of four presentations of the same extracted content to show first.

The questions live here once. The Studio page inlines them at request time and
the CLI can score a saved answer set, so the letter weights cannot drift between
surfaces.
"""

from __future__ import annotations

LETTERS = ("V", "A", "R", "K")

NAMES = {
    "V": "Visual",
    "A": "Aural",
    "R": "Read/write",
    "K": "Kinesthetic",
}

HINTS = {
    "V": "diagrams, figures, layout, colour",
    "A": "spoken explanation, discussion, audio",
    "R": "written notes, lists, definitions",
    "K": "worked examples, doing it, movement",
}

CAVEAT = (
    "VARK records a preference, not a diagnosis. It says how you like material presented; it does "
    "not predict your marks, and matching a modality is not shown to raise them. The report changes "
    "presentation only — the extracted sentences and page references are the same for everyone."
)

SHORT = "Twelve questions about how you like material presented. Preference, not diagnosis."

QUESTIONS = (
    {
        "id": "q1",
        "stem": "A new topic lands in front of you. You start with:",
        "options": (
            {"letter": "V", "label": "the diagrams and figures"},
            {"letter": "A", "label": "someone explaining it, or a recording"},
            {"letter": "R", "label": "the headings and the written text"},
            {"letter": "K", "label": "a worked example you can try"},
        ),
    },
    {
        "id": "q2",
        "stem": "A definition will not stick. What helps?",
        "options": (
            {"letter": "K", "label": "using it in a concrete case"},
            {"letter": "V", "label": "drawing it as a diagram"},
            {"letter": "A", "label": "saying it out loud in your own words"},
            {"letter": "R", "label": "rewriting it until the sentence is clean"},
        ),
    },
    {
        "id": "q3",
        "stem": "You are revising for two hours. What you need:",
        "options": (
            {"letter": "R", "label": "lists and written notes"},
            {"letter": "K", "label": "breaks, movement, something to do with your hands"},
            {"letter": "V", "label": "colour, layout, space to spread pages out"},
            {"letter": "A", "label": "quiet, or background sound"},
        ),
    },
    {
        "id": "q4",
        "stem": "In a lecture, you follow best when:",
        "options": (
            {"letter": "A", "label": "the lecturer explains it aloud"},
            {"letter": "V", "label": "the slides have diagrams"},
            {"letter": "K", "label": "there is a demonstration or a lab"},
            {"letter": "R", "label": "there is a handout to annotate"},
        ),
    },
    {
        "id": "q5",
        "stem": "A process with five steps. You learn it by:",
        "options": (
            {"letter": "V", "label": "a flowchart"},
            {"letter": "R", "label": "a numbered list in writing"},
            {"letter": "K", "label": "doing it once, badly"},
            {"letter": "A", "label": "hearing it described as a story"},
        ),
    },
    {
        "id": "q6",
        "stem": "You have to remember a formula. You:",
        "options": (
            {"letter": "K", "label": "apply it to a problem"},
            {"letter": "R", "label": "write it out several times"},
            {"letter": "V", "label": "picture where it sits on the page"},
            {"letter": "A", "label": "repeat it aloud"},
        ),
    },
    {
        "id": "q7",
        "stem": "Something went wrong in your answer. You:",
        "options": (
            {"letter": "R", "label": "read the solution and compare line by line"},
            {"letter": "V", "label": "redraw the setup and look at it"},
            {"letter": "A", "label": "talk it through with someone"},
            {"letter": "K", "label": "redo it with your hands"},
        ),
    },
    {
        "id": "q8",
        "stem": "Best use of a five-minute gap:",
        "options": (
            {"letter": "A", "label": "listen to a recap"},
            {"letter": "K", "label": "walk and recall"},
            {"letter": "R", "label": "skim your notes"},
            {"letter": "V", "label": "flick through the figures"},
        ),
    },
    {
        "id": "q9",
        "stem": "A dense page of text. You:",
        "options": (
            {"letter": "V", "label": "look for a picture or a table first"},
            {"letter": "R", "label": "read it and highlight"},
            {"letter": "A", "label": "read it aloud, or use text-to-speech"},
            {"letter": "K", "label": "skip to the example and come back"},
        ),
    },
    {
        "id": "q10",
        "stem": "You are choosing study material. You pick:",
        "options": (
            {"letter": "K", "label": "one with exercises"},
            {"letter": "A", "label": "one with recordings or explainers"},
            {"letter": "V", "label": "one with diagrams and charts"},
            {"letter": "R", "label": "one with detailed written notes"},
        ),
    },
    {
        "id": "q11",
        "stem": "In group study, your role is:",
        "options": (
            {"letter": "V", "label": "drawing on the board"},
            {"letter": "A", "label": "explaining out loud"},
            {"letter": "K", "label": "setting up the practical part"},
            {"letter": "R", "label": "taking notes and writing the summary"},
        ),
    },
    {
        "id": "q12",
        "stem": "You know you understand something when:",
        "options": (
            {"letter": "R", "label": "you can write it precisely"},
            {"letter": "V", "label": "you can picture it"},
            {"letter": "A", "label": "you can explain it aloud"},
            {"letter": "K", "label": "you can do it"},
        ),
    },
)


def decode(answers) -> tuple[int, ...] | None:
    """(2, 0, 1, ...) with one index per question; None if malformed."""
    seq = tuple(int(a) for a in answers) if not isinstance(answers, (str, bytes)) else None
    if seq is None or len(seq) != len(QUESTIONS):
        return None
    if any(not 0 <= a < 4 for a in seq):
        return None
    return seq


def score(answers) -> dict[str, int]:
    seq = decode(answers)
    if seq is None:
        raise ValueError(f"need {len(QUESTIONS)} answers, each 0-3")
    counts = {k: 0 for k in LETTERS}
    for question, choice in zip(QUESTIONS, seq):
        counts[question["options"][choice]["letter"]] += 1
    return counts


def profile(answers) -> dict:
    counts = score(answers)
    best = max(counts.values())
    top = [k for k in LETTERS if counts[k] == best]
    rest = max((counts[k] for k in LETTERS if k not in top), default=0)
    second = [k for k in LETTERS if k not in top and counts[k] == rest and rest > 0]
    label = " + ".join(NAMES[k] for k in top)
    if len(top) > 1:
        label = "Multimodal: " + label
    return {
        "answers": list(decode(answers)),
        "scores": counts,
        "dominant": top[0],
        "dominant_all": top,
        "secondary": second,
        "multimodal": len(top) > 1 or (bool(second) and counts[second[0]] == best - 1),
        "label": label,
        "hint": " · ".join(HINTS[k] for k in top),
    }


def payload() -> dict:
    return {
        "version": 1,
        "questions": [
            {
                "id": q["id"],
                "stem": q["stem"],
                "options": [dict(o) for o in q["options"]],
            }
            for q in QUESTIONS
        ],
        "letters": list(LETTERS),
        "names": dict(NAMES),
        "hints": dict(HINTS),
        "caveat": CAVEAT,
        "short": SHORT,
        "length": len(QUESTIONS),
    }
