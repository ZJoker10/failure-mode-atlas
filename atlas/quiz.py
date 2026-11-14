"""Study-profile quiz: ten questions, four profiles, one honest caveat.

What this is
------------
A routing device. Ten self-report questions put you on three axes, and the
profile you land in opens three atlas entries where that habit meets an
explicit warning in the exam wording. The point is to get a visitor from "where
do I start" to an entry they can actually read, in under a minute.

What this is not
----------------
A learning-style diagnosis. "Visual / auditory / kinaesthetic" has weak support
as a way to improve outcomes, and this corpus contains no student responses at
all. So nothing here claims to measure how you learn, predict your mark, or
match you to teaching. It records what you say you do, and the profile -> entry
mapping is an editorial choice by the authors, labelled `reconstructed`, in the
same vocabulary the atlas uses for every other inference.

The questions, the weights, the profile copy and the disclaimer live here once.
The viewer inlines all of it at build time (`__QUIZ__`) and the CLI prints the
same answer, so a change to a weight cannot reach one surface only. Scoring is
a weighted sum, deliberately boring: it is the one part of this project that
must never surprise anyone.
"""

from __future__ import annotations

from .rules import CONCEPTS

# --------------------------------------------------------------------- axes

# The positive end of each axis is the one named in the question wording, so a
# positive score always means "the first option" and is easy to audit.
AXES = (
    {
        "id": "representation",
        "positive": "figure-first",
        "negative": "symbol-first",
        "label": "How you represent a problem",
        "left": "symbols and equations",
        "right": "figures and geometry",
    },
    {
        "id": "approach",
        "positive": "method-first",
        "negative": "derivation-first",
        "label": "How you attack an unseen task",
        "left": "derive from definitions",
        "right": "follow a known method",
    },
    {
        "id": "warmup",
        "positive": "example-first",
        "negative": "attempt-first",
        "label": "How you warm up",
        "left": "attempt cold, then compare",
        "right": "study one worked example first",
    },
)

# ----------------------------------------------------------------- questions

QUESTIONS = (
    {
        "id": "q1",
        "stem": "A robot you have never seen appears on the sheet. Your first move:",
        "options": (
            {"label": "Sketch it and mark the joint axes", "w": {"representation": 1.0}},
            {"label": "Write down the given parameters symbolically", "w": {"representation": -1.0}},
            {"label": "Find a similar worked example in the notes", "w": {"warmup": 1.0}},
        ),
    },
    {
        "id": "q2",
        "stem": "You are asked to find all singular configurations. You:",
        "options": (
            {"label": "Run the standard test: compute det J and solve", "w": {"approach": 1.0}},
            {
                "label": "Reason about which motion the arm loses, then confirm with algebra",
                "w": {"approach": -1.0},
            },
            {"label": "Re-read the slide on singularities first", "w": {"warmup": 1.0}},
        ),
    },
    {
        "id": "q3",
        "stem": "Halfway through a long derivation, you stop. What helps most?",
        "options": (
            {"label": "Drawing the configuration where it breaks", "w": {"representation": 1.0}},
            {"label": "Rewriting the expression in a cleaner notation", "w": {"representation": -1.0}},
            {"label": "Re-reading the exact wording of the question", "w": {}},
        ),
    },
    {
        "id": "q4",
        "stem": "Your chapter notes are mostly:",
        "options": (
            {"label": "Numbered steps and conditions", "w": {"approach": 1.0}},
            {"label": "Definitions, then derivations from them", "w": {"approach": -1.0}},
            {"label": "Copied worked examples", "w": {"warmup": 1.0}},
        ),
    },
    {
        "id": "q5",
        "stem": "Before an unseen exercise, you prefer to:",
        "options": (
            {"label": "See one full worked solution first", "w": {"warmup": 1.0}},
            {"label": "Attempt it cold, then compare", "w": {"warmup": -1.0}},
            {"label": "Work out what is being asked, then decide", "w": {}},
        ),
    },
    {
        "id": "q6",
        "stem": "A computed result disagrees with the figure. You trust:",
        "options": (
            {"label": "The figure — go back and find the geometry error", "w": {"representation": 1.0}},
            {"label": "The algebra — the figure may be schematic", "w": {"representation": -1.0}},
            {"label": "Neither; recompute both", "w": {}},
        ),
    },
    {
        "id": "q7",
        "stem": "Memorising a method without its derivation feels:",
        "options": (
            {"label": "Fine — it has to work under time pressure", "w": {"approach": 1.0}},
            {"label": "Unsafe — I need to know why it works", "w": {"approach": -1.0}},
            {"label": "Depends on the marks at stake", "w": {}},
        ),
    },
    {
        "id": "q8",
        "stem": "The most useful hour the night before:",
        "options": (
            {"label": "Re-reading worked examples and solutions", "w": {"warmup": 1.0}},
            {"label": "A full paper under time, then mark it", "w": {"warmup": -1.0}},
            {"label": "Reviewing formula sheets", "w": {"representation": -0.5}},
        ),
    },
    {
        "id": "q9",
        "stem": "You remember a result best when:",
        "options": (
            {"label": "You can picture the robot configuration", "w": {"representation": 1.0}},
            {"label": "You can write the equation chain", "w": {"representation": -1.0}},
            {"label": "You can explain the steps out loud", "w": {}},
        ),
    },
    {
        "id": "q10",
        "stem": "\u201cProve that this Jacobian always has full rank.\u201d You:",
        "options": (
            {"label": "Recall the standard argument and adapt it", "w": {"approach": 1.0}},
            {"label": "Build the argument from the definition of rank", "w": {"approach": -1.0}},
            {"label": "Look for the theorem in the notes", "w": {"warmup": 1.0}},
        ),
    },
)

NEUTRAL = 0.15  # |axis score| below this is reported as "no strong preference"

# ----------------------------------------------------------------- profiles

# `start` pairs a concept with the sentence that connects the habit to the
# entry. The concept is resolved to the highest-ranked entry carrying it, so the
# recommendation follows the atlas ranking instead of hard-coding an id that a
# later ranking change would silently contradict.
PROFILES = {
    "sketch_recipe": {
        "name": "Sketch first, then the recipe",
        "quadrant": "figure-first \u00b7 method-first",
        "blurb": (
            "You start from a drawing and you like a defined sequence of steps. On these papers that "
            "is strong on geometry and exposed exactly where the drawing is approximate and the marks "
            "sit in the algebra."
        ),
        "watch": (
            "The risk is a sketch that quietly omits an offset, and stopping at the first method that "
            "fits the problem."
        ),
        "start": (
            (
                "dh_frames",
                "You start from a drawing, so a frame that looks right and is one sign or one offset "
                "off is your natural failure — and the papers write an explicit clause against it.",
            ),
            (
                "singularity",
                "The lost direction is visible on your sketch. The marks are in the rank, the null "
                "space and the admissible velocity, which the drawing does not give you.",
            ),
            (
                "trajectory",
                "A drawn velocity profile is not a timing law. The bounds and the corner cases are "
                "where the marks are, and they are easy to skip once the picture looks right.",
            ),
        ),
    },
    "sketch_derive": {
        "name": "Picture first, then rebuild it",
        "quadrant": "figure-first \u00b7 derivation-first",
        "blurb": (
            "You reason from the picture and then rebuild the mathematics. That combination handles "
            "geometry questions well and is exposed wherever the paper wants an argument the picture "
            "cannot supply."
        ),
        "watch": (
            "Geometry gives you the answer; the paper asks for the justification. Do not let a correct "
            "sketch stand in for a proof."
        ),
        "start": (
            (
                "singularity",
                "Your geometry finds the singular configuration. The question asks for a basis of the "
                "null space and a rank, so the derivation is the deliverable.",
            ),
            (
                "statics",
                "Force directions are geometric, but the equilibrium argument and the transformation "
                "are algebraic, and that is where the marks are.",
            ),
            (
                "orientation",
                "A rotation picture does not choose the Euler branch. The inverse problem does, and it "
                "is checked.",
            ),
        ),
    },
    "symbol_recipe": {
        "name": "Symbols first, then the method",
        "quadrant": "symbol-first \u00b7 method-first",
        "blurb": (
            "You write the algebra down first and you work best from an ordered procedure. That is the "
            "fast route through these papers, and it is exposed where the procedure has branches."
        ),
        "watch": (
            "Procedures have cases. The papers award marks for the case you did not enumerate, and for "
            "the drawing you did not produce."
        ),
        "start": (
            (
                "inverse_kinematics",
                "Closed-form IK is a procedure with branches: the marks are in counting the solutions "
                "and in the singular cases, not in one successful evaluation.",
            ),
            (
                "trajectory",
                "Bounds, timing law, continuity up to a derivative: a checklist, and the papers put "
                "marks on the clause that gets forgotten.",
            ),
            (
                "dh_frames",
                "You may fill the parameter table correctly and still lose marks: several exercises "
                "require the frames drawn on the figure.",
            ),
        ),
    },
    "symbol_derive": {
        "name": "Definitions first, then derive",
        "quadrant": "symbol-first \u00b7 derivation-first",
        "blurb": (
            "You start from the definitions and build the result yourself. That is the most robust "
            "route these papers allow, and its exposure is time and enumeration: deriving one case "
            "is not the same as listing all of them."
        ),
        "watch": (
            "The paper is timed. A derivation that is correct but unfinished scores like an incorrect "
            "one, and singular cases are easy to derive past."
        ),
        "start": (
            (
                "jacobian",
                "Deriving J from the definition is your strong route. These questions ask for both the "
                "geometric and the analytic version and usually for their relation.",
            ),
            (
                "orientation",
                "T(\u03c6) is a derivation-shaped object; its singularities are exactly where that "
                "derivation stops being invertible.",
            ),
            (
                "inverse_kinematics",
                "Deriving the solutions is not the same as enumerating them. The papers ask how many "
                "there are, and which ones survive the joint limits.",
            ),
        ),
    },
}

DISCLAIMER = (
    "This is not a validated learning-style instrument, and nothing here is a claim about how you "
    "learn. Visual/auditory/kinaesthetic categories have little support as a way to improve "
    "outcomes, and this corpus contains no student responses. The quiz records what you say you "
    "do; the profile-to-entry mapping is an editorial choice by the authors, labelled "
    "reconstructed, not a cohort finding."
)

SHORT = (
    "Ten questions about how you study. Not a validated learning-style test: the profile records "
    "what you say you do, and the full caveat is on the result."
)

WARMUP_NOTES = {
    "neutral": (
        "You mix worked examples with cold attempts. Make the ratio explicit: attempt first, then "
        "compare, even when the example is right there."
    ),
    "example-first": (
        "You prefer to see one worked solution before attempting. That is fine for calibration, "
        "but the paper will not show you one: do at least one cold attempt per topic."
    ),
    "attempt-first": (
        "You prefer attempting cold. Keep it \u2014 but read the official solution even when your answer "
        "looks right, because the marks are in the justification, not the number."
    ),
}

PRIVACY = (
    "Your answers are not sent anywhere and not stored on a server. They live in the URL fragment "
    "so a result can be linked; closing the tab forgets them."
)

# ------------------------------------------------------------------ scoring


def _axis_max() -> dict[str, float]:
    """Largest achievable |score| per axis, so every axis lands in [-1, 1]."""
    out = {a["id"]: 0.0 for a in AXES}
    for q in QUESTIONS:
        for axe in out:
            out[axe] += max((abs(o["w"].get(axe, 0.0)) for o in q["options"]), default=0.0)
    return out


MAX = _axis_max()


def decode(answers: str) -> tuple[int, ...] | None:
    """'0120120120' -> (0,1,2,...). None if it cannot be a full answer set."""
    s = str(answers).strip()
    if len(s) != len(QUESTIONS) or any(ch not in "012" for ch in s):
        return None
    return tuple(int(ch) for ch in s)


def encode(answers) -> str:
    return "".join(str(int(a)) for a in answers)


def score(answers) -> dict[str, float]:
    totals = {a["id"]: 0.0 for a in AXES}
    for q, choice in zip(QUESTIONS, answers):
        w = q["options"][int(choice)]["w"]
        for axe, v in w.items():
            totals[axe] += float(v)
    return {k: totals[k] / MAX[k] if MAX[k] else 0.0 for k in totals}


def neutral(value: float) -> bool:
    return abs(value) < NEUTRAL


def profile_id(answers) -> str:
    s = score(answers)
    figure = s["representation"] >= 0
    method = s["approach"] >= 0
    if figure and method:
        return "sketch_recipe"
    if figure:
        return "sketch_derive"
    if method:
        return "symbol_recipe"
    return "symbol_derive"


def warmup_key(value: float) -> str:
    if neutral(value):
        return "neutral"
    return "example-first" if value > 0 else "attempt-first"


def warmup_note(answers) -> str:
    return WARMUP_NOTES[warmup_key(score(answers)["warmup"])]


def ranked_entries(concept: str, entries: list[dict]) -> list[dict]:
    """Entries carrying `concept`, in atlas order (the atlas is already ranked)."""
    return [e for e in entries if concept in e.get("concepts", ())]


def recommendations(answers, entries: list[dict]) -> list[dict]:
    """Profile -> concrete entries, with the sentence that connects them."""
    pid = profile_id(answers)
    out = []
    for concept, why in PROFILES[pid]["start"]:
        pool = ranked_entries(concept, entries)
        if not pool:
            continue
        e = pool[0]
        out.append(
            {
                "concept": concept,
                "concept_label": CONCEPTS.get(concept, {}).get("label", concept),
                "why": why,
                "id": e["id"],
                "title": e["title"],
                "marks_at_risk": e["marks_at_risk"],
                "strength": e["strength"],
                "quote": e["evidence"]["exam"]["quote"],
                "ref": e["evidence"]["exam"]["ref"],
            }
        )
    return out


def result(answers, entries: list[dict]) -> dict:
    """Everything a surface needs to render one result, as plain JSON data."""
    p = PROFILES[profile_id(answers)]
    s = score(answers)
    return {
        "answers": encode(answers),
        "profile": profile_id(answers),
        "name": p["name"],
        "quadrant": p["quadrant"],
        "blurb": p["blurb"],
        "watch": p["watch"],
        "scores": s,
        "axes": [
            {
                **a,
                "value": s[a["id"]],
                "neutral": neutral(s[a["id"]]),
            }
            for a in AXES
        ],
        "warmup_key": warmup_key(s["warmup"]),
        "warmup_note": warmup_note(answers),
        "no_strong_preference": neutral(s["representation"]) and neutral(s["approach"]),
        "recommendations": recommendations(answers, entries),
        "disclaimer": DISCLAIMER,
        "privacy": PRIVACY,
        "mapping_strength": "reconstructed",
    }


def payload() -> dict:
    """The quiz as data, for the viewer and for tests. No logic is duplicated."""
    return {
        "axes": [dict(a) for a in AXES],
        "questions": [
            {
                "id": q["id"],
                "stem": q["stem"],
                "options": [
                    {"label": o["label"], "w": dict(o["w"])} for o in q["options"]
                ],
            }
            for q in QUESTIONS
        ],
        # `start` is a tuple of (concept, why); JSON has no tuples, so normalise
        # here rather than in the viewer's test.
        "profiles": {
            k: {**v, "start": [list(pair) for pair in v["start"]]}
            for k, v in PROFILES.items()
        },
        "max": MAX,
        "neutral": NEUTRAL,
        "short": SHORT,
        "warmup": WARMUP_NOTES,
        "disclaimer": DISCLAIMER,
        "privacy": PRIVACY,
        "length": len(QUESTIONS),
        "mapping_strength": "reconstructed",
    }
