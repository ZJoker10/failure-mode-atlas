"""Rules: the design-tell lexicon.

The claim this project makes is narrow and testable:

    A professor's exam encodes what he expects to go wrong, and some of that
    leaks into the wording. An instruction that only makes sense if a specific
    error is anticipated is *documented* evidence of that anticipated error.

"so that all constant DH parameters are nonnegative" is not a neutral
instruction. It exists because students pick sign conventions that make them
negative. The instruction is quotable; the inference from it is named and
auditable (rule DT-01) rather than hidden inside a model.

Every rule below is one such inference. RULES is the whole intellectual
content of the product; the pipeline only counts and cites.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    patterns: tuple[str, ...]
    trigger: str            # what in the exam fires it
    wrong_turn: str         # what the student actually does
    misconception: str      # the belief underneath
    probe: str              # smallest question that would detect it
    correction: str         # the teaching move
    concepts: tuple[str, ...]
    # "documented" only when the exam wording itself pre-empts the error.
    # "reconstructed" when the link from wording to student behaviour is ours.
    strength: str
    # Phrases that make the pattern fire for the wrong reason. "joint range"
    # also occurs in encoder-sizing questions, which say nothing about workspace
    # being cut by joint stops, so those clauses are dropped. This is the
    # precision knob, and every entry it removes is counted in coverage.
    veto: tuple[str, ...] = ()

    def search(self, text: str) -> list[str]:
        """Return exact matched spans, longest first (they are our quotes)."""
        if self.veto and any(v.lower() in text.lower() for v in self.veto):
            return []
        hits: list[str] = []
        for pat in self.patterns:
            for m in re.finditer(pat, text, re.I):
                hits.append(m.group(0))
        # longest match is usually the most informative quote
        return sorted(set(hits), key=len, reverse=True)


# ---------------------------------------------------------------------------
# Concept taxonomy. Keys are stable ids; `kw` drives detection in exam text;
# `slide_kw` drives the cross-reference into the lecture decks.
# ---------------------------------------------------------------------------

CONCEPTS: dict[str, dict] = {
    "dh_frames": {
        "label": "DH frame assignment",
        "kw": (r"\bDH\b", r"denavit", r"\bframes?\b", r"table of parameters",
               r"reference frames?", r"\bRF\b"),
        "slide_kw": ("Denavit", "DH", "frame assignment", "table of parameters"),
        # The exams ask for the *standard* convention, so a cross-reference to
        # the modified-convention appendix would point at the wrong material.
        "avoid": ("modified",),
    },
    "direct_kinematics": {
        "label": "Direct kinematics",
        "kw": (r"direct kinematics", r"forward kinematics", r"\bk\(q\)",
               r"position of (point|the end)", r"end-effector position"),
        "slide_kw": ("direct kinematics", "forward kinematics", "position of"),
    },
    "inverse_kinematics": {
        "label": "Inverse kinematics",
        "kw": (r"inverse kinematics", r"inverse problem", r"closed form",
               r"k\^?\{?-1\}?", r"all .{0,20}solutions"),
        "slide_kw": ("inverse kinematics", "closed form", "inverse problem"),
    },
    "jacobian": {
        "label": "Differential kinematics / Jacobian",
        "kw": (r"jacobian", r"\bJ\s*\(q\)", r"differential kinematics",
               r"velocity of (point|the)"),
        "slide_kw": ("Jacobian", "differential kinematics", "velocity"),
    },
    "singularity": {
        "label": "Singular configurations",
        "kw": (r"singular", r"null space", r"\brank\b", r"singularit"),
        "slide_kw": ("singular", "singularity", "rank", "null space"),
    },
    "statics": {
        "label": "Statics / force transformation",
        "kw": (r"static", r"torque", r"wrench", r"statically balanc"),
        "slide_kw": ("statics", "torque", "force", "wrench"),
    },
    "orientation": {
        "label": "Orientation / Euler angles",
        "kw": (r"euler", r"\bRPY\b", r"rotation matrix", r"\bXYZ\b",
               r"orientation", r"yaw|pitch|roll"),
        "slide_kw": ("Euler", "RPY", "rotation matrix", "orientation"),
    },
    "trajectory": {
        "label": "Trajectory planning (joint space)",
        "kw": (r"trajector", r"polynomial", r"rest-to-rest", r"minimum time",
               r"cubic|quintic", r"boundary conditions"),
        "slide_kw": ("trajectory", "polynomial", "minimum time", "cubic"),
    },
    "trajectory_cartesian": {
        "label": "Trajectory planning (Cartesian)",
        "kw": (r"cartesian (path|trajectory)", r"path planning",
               r"obstacle", r"via point"),
        "slide_kw": ("Cartesian", "path planning", "obstacle", "via point"),
    },
    "kinematic_control": {
        "label": "Kinematic control",
        "kw": (r"kinematic control", r"control law", r"closed-loop"),
        "slide_kw": ("kinematic control", "control law", "feedback"),
    },
    "actuators": {
        "label": "Actuators / transmissions",
        "kw": (r"motor", r"encoder", r"reduction", r"gearbox", r"transmission"),
        "slide_kw": ("actuator", "motor", "encoder", "transmission"),
    },
}


# Which lecture deck is the authoritative place to learn each concept. This map
# is curated from the deck titles themselves (09_DirectKinematics is where direct
# kinematics lives), not from the exam text, and it is used only to *narrow* the
# search for a lecture quote. The page and the quote inside that deck are still
# found mechanically, so a mismatched pointer is checkable by opening the deck.
PREFERRED_DECK: dict[str, str] = {
    "dh_frames": "09_DirectKinematics",
    "direct_kinematics": "09_DirectKinematics",
    "inverse_kinematics": "10_InverseKinematics",
    "jacobian": "11_DifferentialKinematics",
    "singularity": "11_DifferentialKinematics",
    "statics": "12b_StaticsForceTransformations",
    "orientation": "08_EulerRPYHomogeneous",
    "trajectory": "13_TrajectoryPlanning",
    "trajectory_cartesian": "14_TrajectoryPlanningCartesian",
    "kinematic_control": "15_KinematicControl",
    "actuators": "03_CompsActuators",
}


# ---------------------------------------------------------------------------
# The rule book. Order is irrelevant; ids are stable and appear in the atlas.
# ---------------------------------------------------------------------------

RULES: tuple[Rule, ...] = (

    Rule(
        id="DT-01",
        name="Sign gauge pre-empted",
        patterns=(r"nonnegative", r"non-negative", r"all constant DH parameters"),
        trigger="The task constrains the sign of the DH parameters before the student starts.",
        wrong_turn="Assigns z-axes in the opposite direction, so d or a come out negative, "
                   "then flips a sign somewhere downstream to compensate.",
        misconception="DH parameters are whatever the diagram shows; the convention is "
                      "decoration rather than a gauge choice you must declare.",
        probe="For this arm, which DH entries can be made nonnegative, and which axis "
              "direction did you have to reverse to do it?",
        correction="Fix the z-axis direction rule first, then read the table off. Verify the "
                   "sign of every d and a against the drawn axis before writing k(q).",
        concepts=("dh_frames",),
        strength="documented",
    ),

    Rule(
        id="DT-02",
        name="Singular cases flagged",
        patterns=(r"taking into account the singular", r"including the singular",
                  r"in the singular case"),
        trigger="The task tells the student that singular cases change the answer.",
        wrong_turn="Reports the generic solution only, or divides by a term that vanishes "
                   "at the singularity and calls the infinite result 'undefined'.",
        misconception="A solution derived by inversion is valid everywhere; edge cases are "
                      "a detail to mention, not a change of structure.",
        probe="At the configuration you just solved for, which matrix entry is zero, and "
              "what happens to your formula when it is?",
        correction="Enumerate the singular set first, then solve on each branch. State rank "
                   "and a null-space basis at the singularity instead of inverting.",
        concepts=("singularity", "inverse_kinematics"),
        strength="documented",
    ),

    Rule(
        id="DT-03",
        name="Singularity existence probed",
        patterns=(r"is it possible to (?:encounter|have|reach)[^?]{0,60}singular",
                  r"can (?:the|this)[^?]{0,40}singular"),
        trigger="A yes/no question asks whether a singularity can occur at all.",
        wrong_turn="Answers 'no' because the determinant looked non-zero in the numeric "
                   "example, or answers 'yes' without naming the configuration.",
        misconception="Singularity is a property of the numbers in front of you rather than "
                      "a property of the structure.",
        probe="Which symbolic entry of J can vanish for some q, regardless of the numeric "
              "values you were given?",
        correction="Work symbolically to the determinant, then look for the factor that can "
                   "be zero. The answer is a set of configurations, not a yes/no.",
        concepts=("singularity",),
        strength="documented",
    ),

    Rule(
        id="DT-04",
        name="Symbolic form demanded",
        patterns=(r"in symbolic form", r"symbolic(?:ally)?", r"symbolic expression"),
        trigger="The task requires a symbolic expression, not a number.",
        wrong_turn="Substitutes the numeric link lengths at the first opportunity, then "
                   "cannot simplify, factor or find the singular set later.",
        misconception="Numbers make it concrete, so numbering early is safer.",
        probe="Write k(q) with the link lengths still as symbols; where does l2 appear "
              "twice?",
        correction="Carry symbols to the end. Numbers are a final check, never an "
                   "intermediate step, because the structure is what is being marked.",
        concepts=("direct_kinematics", "jacobian"),
        strength="documented",
    ),

    Rule(
        id="DT-05",
        name="Minimum-norm solution specified",
        patterns=(r"minimum norm", r"minim(?:um|al) norm", r"least[- ]norm"),
        trigger="Among infinitely many joint velocities producing the same v, one is required.",
        wrong_turn="Picks any particular solution (often the one the elimination happened to "
                   "leave) and reports it as 'the' solution.",
        misconception="An underdetermined system still has an answer, and any answer is it.",
        probe="Your q̇ has a component in the null space of J. What is that component and "
              "what is it doing to the norm?",
        correction="Project the particular solution onto the row space: use the "
                   "pseudoinverse and say explicitly that the null-space part is set to zero.",
        concepts=("jacobian", "singularity"),
        strength="documented",
    ),

    Rule(
        id="DT-06",
        name="Closed form required",
        patterns=(r"closed form", r"analytical(?:ly)?", r"in closed"),
        trigger="The task asks for an analytic inverse, not an iterative one.",
        wrong_turn="Sets up Newton's iteration and stops when the residual is small, "
                   "delivering a point rather than a solution set.",
        misconception="A sufficiently good numeric answer is the same object as the "
                      "closed form.",
        probe="How many distinct q map to your p_d, and which equation did you use to "
              "separate them?",
        correction="Isolate q1 from the position equation, then solve the remaining planar "
                   "sub-problem. The count of branches is part of the answer.",
        concepts=("inverse_kinematics",),
        strength="documented",
    ),

    Rule(
        id="DT-07",
        name="All branches requested",
        patterns=(r"all (?:the )?(?:possible )?(?:inverse kinematics )?solutions",
                  r"all solutions", r"every solution"),
        trigger="The wording asks for the complete solution set.",
        wrong_turn="Stops at the first root the quadratic returns, or drops the branch that "
                   "would require a negative joint angle.",
        misconception="The solution you found is the solution; other roots are artefacts of "
                      "the algebra.",
        probe="Your quadratic had two roots — where did the second one go?",
        correction="Enumerate branches explicitly and budget for them. Count solutions "
                   "before computing them, so a missing one is visible.",
        concepts=("inverse_kinematics",),
        strength="documented",
    ),

    Rule(
        id="DT-08",
        name="Justification demanded",
        patterns=(r"\bshow that\b", r"\bprove\b", r"\bjustify\b", r"\bdemonstrate\b",
                  r"\bverify\b"),
        trigger="A 'show that' / 'justify' imperative whose conclusion is already given.",
        wrong_turn="Substitutes a number, sees it works, and writes 'verified'. Or restates "
                   "the claim in different words.",
        misconception="Matching the stated answer is the same as establishing it.",
        probe="Show me the step where the conclusion follows — what would break if the "
              "claim were false?",
        correction="Prove the general case symbolically; use the numeric instance only as a "
                   "check. 'Show that' is a proof obligation, not a spot-check.",
        concepts=("direct_kinematics", "jacobian", "singularity"),
        strength="documented",
    ),

    Rule(
        id="DT-09",
        name="Boundary conditions pinned",
        patterns=(r"rest-to-rest", r"zero (?:initial|final) (?:velocity|acceleration)",
                  r"boundary conditions", r"q̇\(0\) = q̈\(0\) = q̇\(T\)"),
        trigger="Velocity and acceleration are pinned at both ends.",
        wrong_turn="Fits position only and produces a trajectory with a velocity jump at the "
                   "endpoints, or forgets that a cubic cannot zero acceleration too.",
        misconception="Boundary conditions on position are the ones that matter; velocity "
                      "follows along.",
        probe="How many boundary conditions did you impose, and how many free coefficients "
              "does your polynomial have?",
        correction="Count degrees of freedom against conditions before choosing the degree. "
                   "Cubic zeroes velocity; quintic is needed to zero acceleration too.",
        concepts=("trajectory",),
        strength="documented",
    ),

    Rule(
        id="DT-10",
        name="Rank and null space demanded",
        patterns=(r"null space", r"\brank\b", r"basis for the null"),
        trigger="The task asks for rank and a null-space basis, not just 'J is singular'.",
        wrong_turn="Computes det(J) = 0, declares a singularity, and moves on without "
                   "producing rank or any basis.",
        misconception="Singular means the determinant vanished; the structure of what "
                      "collapsed is extra.",
        probe="If det(J) = 0, what is rank(J) here, and name one vector J sends to zero.",
        correction="Compute rank explicitly and exhibit a null vector. The null space is the "
                   "self-motion — that is the physically meaningful output.",
        concepts=("singularity", "jacobian"),
        strength="documented",
    ),

    Rule(
        id="DT-11",
        name="Minimum time under bounds",
        patterns=(r"minimum time", r"in minimum time", r"time[- ]optimal"),
        trigger="Minimum-time motion subject to acceleration or velocity bounds.",
        wrong_turn="Times the motion by picking a comfortable duration, or uses a symmetric "
                   "profile that satisfies the bound on one joint only.",
        misconception="A feasible trajectory is a minimal one if it looks tight.",
        probe="Which joint saturates its bound first, and for how long?",
        correction="Each joint has its own minimal time under its own bound. The coordinated "
                   "time is the maximum, then the slower joint is scaled to fill it.",
        concepts=("trajectory",),
        strength="documented",
    ),

    Rule(
        id="DT-12",
        name="Coordination required",
        patterns=(r"coordinated (?:motion|task|trajectory)", r"coordinated"),
        trigger="Two joints or two robots must arrive together.",
        wrong_turn="Plans each joint independently to its own minimum time, so they finish at "
                   "different instants and the path is not what was asked.",
        misconception="Synchronising is a detail of presentation; each axis is a separate "
                      "problem.",
        probe="Joint 2 finishes after joint 1 — what is the end-effector doing in between?",
        correction="Plan per joint, take the maximum duration, then time-scale every other "
                   "joint to match. Coordination is a constraint, not a tidy-up.",
        concepts=("trajectory",),
        strength="documented",
    ),

    Rule(
        id="DT-13",
        name="Joint limits active",
        patterns=(r"joint (?:range|limit)", r"under (?:joint )?range limits",
                  r"limited range"),
        trigger="The workspace question is posed with finite joint ranges.",
        wrong_turn="Draws the reachable workspace from link lengths alone, giving an annulus "
                   "that the joint limits actually cut away.",
        misconception="Workspace is a geometric property of the arm, independent of the "
                      "joints' travel.",
        probe="Which part of your annulus is unreachable because q2 cannot exceed its stop?",
        correction="Intersect the geometric workspace with the image of the joint box. Report "
                   "the boundary that comes from limits, not from link lengths.",
        concepts=("inverse_kinematics", "dh_frames"),
        strength="documented",
        # Encoder sizing also talks about "joint range" (700 degrees, gear
        # reduction, bits of resolution) without saying anything about the
        # workspace being cut by a joint stop.
        veto=("encoder", "resolution", "reduction ratio"),
    ),

    Rule(
        id="DT-14",
        name="Frame placement pinned",
        patterns=(r"place the origin of the last DH frame",
                  r"putting the origin of the reference frame",
                  r"origin of the (?:last|final) (?:DH )?frame"),
        trigger="The task dictates where a frame origin must sit.",
        wrong_turn="Places the last frame at the flange instead of the specified point, then "
                   "inherits an offset that contaminates every later answer.",
        misconception="Frame origins are arbitrary as long as the transform is right.",
        probe="Your origin sits at the flange — what is the constant offset to P, and which "
              "matrix absorbed it?",
        correction="Place origins to the stated rule first; frame choice is a convention you "
                   "must honour, and every downstream matrix depends on it.",
        concepts=("dh_frames",),
        strength="documented",
    ),

    Rule(
        id="DT-15",
        name="Zero configuration probe",
        patterns=(r"in the zero configuration", r"at the zero configuration",
                  r"zero configuration"),
        trigger="A quantity is requested specifically at q = 0.",
        wrong_turn="Uses the general formula but forgets that at q = 0 the rotation blocks "
                   "collapse, so terms that cancel numerically are dropped by hand.",
        misconception="The zero configuration is a trivial case, so the general expression "
                      "can be evaluated loosely.",
        probe="At q = 0, which columns of J become mutually parallel — and what does that do "
              "to the rank?",
        correction="Evaluate symbolically at q = 0 rather than substituting early. Cancellation "
                   "is exactly where the mark is lost, because the structure disappears.",
        concepts=("jacobian", "statics"),
        strength="reconstructed",
    ),

    Rule(
        id="DT-16",
        name="Static balance requested",
        patterns=(r"statically balanc", r"static balance", r"joint torques"),
        trigger="Torques are requested for a held configuration under gravity.",
        wrong_turn="Balances forces at the end-effector instead of transforming the wrench "
                   "back through J^T, or forgets gravity acts at each centre of mass.",
        misconception="Static equilibrium is a force balance at the point where the load is.",
        probe="Where does the payload weight enter your torque expression, and what happened "
              "to each link's own weight?",
        correction="Write τ = J^T F for the external wrench and add the gravity term per "
                   "link. Statics is a transformation, not a free-body diagram.",
        concepts=("statics", "jacobian"),
        strength="documented",
    ),

    Rule(
        id="DT-17",
        name="Orientation inverse singular",
        patterns=(r"representation singularity", r"singular situation[^.]{0,40}(?:angle|orientation)",
                  r"euler angles[^.]{0,40}singular"),
        trigger="The task asks for angle extraction and then asks about singularity.",
        wrong_turn="Uses asin where atan2 is required, so the angle set collapses at ±90° "
                   "and the two branches are never separated.",
        misconception="Euler extraction is a formula; its branch structure is not part of "
                      "the answer.",
        probe="At pitch = 90°, which two angles become indistinguishable, and what does your "
              "extraction return?",
        correction="Use atan2 throughout and handle the gimbal-lock branch explicitly. The "
                   "singularity is a property of the parameterisation, not of R.",
        concepts=("orientation", "singularity"),
        strength="documented",
    ),
)

RULES_BY_ID = {r.id: r for r in RULES}


def concepts_in(text: str) -> list[str]:
    """Which concepts does this text exercise? Ordered by strength of match."""
    scored: list[tuple[int, str]] = []
    for cid, spec in CONCEPTS.items():
        score = sum(1 for pat in spec["kw"] if re.search(pat, text, re.I))
        if score:
            scored.append((score, cid))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [cid for _, cid in scored]


def rules_in(text: str) -> list[tuple[Rule, str]]:
    """Return (rule, longest exact quote) for each rule that fires."""
    out: list[tuple[Rule, str]] = []
    for rule in RULES:
        hits = rule.search(text)
        if hits:
            out.append((rule, hits[0]))
    return out
