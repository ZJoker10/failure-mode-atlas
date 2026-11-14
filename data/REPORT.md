# Failure-Mode Atlas — Robotics 1 (Sapienza, Prof. A. De Luca)

A reverse-engineered map of what this course's written exams are *designed to catch*, built only from the course's own exam papers and lecture slides.

Every claim below carries a document, a page (or exercise) and a verbatim quote. The build refuses to emit an entry whose quote cannot be found on the page it cites.

## 1. Corpus

| | Documents | Pages | Readable pages | Unreadable (no text layer) |
|---|---|---|---|---|
| Past exams | 160 | 884 | 879 | 5 |
| Lecture decks | 20 | 771 | 766 | 5 |

Readable: **99.4%** of exam pages, **99.4%** of slide pages. OCR pages: 0 — nothing was OCR'd, so no text is claimed from an unreadable page.

### What was analysed, and what was not

| Outcome | Exams | Why |
|---|---|---|
| Analysed | 97 | Segment into ≥2 exercises, so marks can be spread |
| Excluded: single-block era | 27 | Pre-2013 papers have no per-exercise headings; one undivided block has no per-question marks to rank by |
| Excluded: partial sheet | 34 | Extra sheets, data sheets and answer keys are fragments of a paper |
| Excluded: unreadable | 2 | No text layer at all |

Questions parsed: **351** (85.2% of the estimated total).

## 2. Method

1. **Ingest** — `pdftotext -layout`, page by page. A page with fewer than 80 extracted characters is marked unreadable rather than guessed at.
2. **Segment** — exams into exercises (`Exercise N`, `Question #N`, or the older unnumbered layout), exercises into task clauses (lettered parts, roman numerals, bullets, or task-verb sentences).
3. **Fire rules** — 17 *design tells*. A design tell is an instruction that only makes sense if a specific error is anticipated: *"so that all constant DH parameters are nonnegative"* exists because students pick sign conventions that make them negative. The rule book is in `atlas/rules.py` and is the entire interpretive content of the product.
4. **Cross-reference** — each concept is routed to the lecture deck that owns it (`PREFERRED_DECK`), then the earliest page inside 10% of peak keyword density, so the citation points at where the topic is taught rather than at an appendix.
5. **Rank** — marks at risk × questions affected, then aggregate into 27 entries.

6. **Validate, then write** — see §4.

## 3. The atlas

| # | Failure mode | Concept | Marks at risk<br>(per affected exam) | Questions | Score<br>(marks × questions) | Exams | Evidence | Confidence |
|---|---|---|---|---|---|---|---|---|
| 1 | **Minimum time under bounds — Trajectory planning (joint space)**<br>`FM-DT-11-trajectory` | Trajectory planning (joint space) | 7.74 / 30 | 30 | 232.2 | 18 | documented | 0.95 |
| 2 | **Symbolic form demanded — Direct kinematics**<br>`FM-DT-04-direct_kinematics` | Direct kinematics | 3.67 / 30 | 47 | 172.5 | 38 | documented | 0.95 |
| 3 | **Rank and null space demanded — Singular configurations**<br>`FM-DT-10-singularity` | Singular configurations | 3.69 / 30 | 25 | 92.2 | 20 | documented | 0.95 |
| 4 | **Boundary conditions pinned — Trajectory planning (joint space)**<br>`FM-DT-09-trajectory` | Trajectory planning (joint space) | 4.99 / 30 | 17 | 84.8 | 16 | documented | 0.95 |
| 5 | **Justification demanded — Direct kinematics**<br>`FM-DT-08-direct_kinematics` | Direct kinematics | 4.54 / 30 | 15 | 68.1 | 12 | documented | 0.95 |
| 6 | **Rank and null space demanded — Differential kinematics / Jacobian**<br>`FM-DT-10-jacobian` | Differential kinematics / Jacobian | 3.39 / 30 | 18 | 61.0 | 17 | documented | 0.95 |
| 7 | **Closed form required — Inverse kinematics**<br>`FM-DT-06-inverse_kinematics` | Inverse kinematics | 2.81 / 30 | 21 | 59.0 | 19 | documented | 0.95 |
| 8 | **Coordination required — Trajectory planning (joint space)**<br>`FM-DT-12-trajectory` | Trajectory planning (joint space) | 4.98 / 30 | 10 | 49.8 | 10 | documented | 0.95 |
| 9 | **Frame placement pinned — DH frame assignment**<br>`FM-DT-14-dh_frames` | DH frame assignment | 3.16 / 30 | 15 | 47.4 | 14 | documented | 0.95 |
| 10 | **Sign gauge pre-empted — DH frame assignment**<br>`FM-DT-01-dh_frames` | DH frame assignment | 2.9 / 30 | 16 | 46.4 | 15 | documented | 0.95 |
| 11 | **Joint limits active — Inverse kinematics**<br>`FM-DT-13-inverse_kinematics` | Inverse kinematics | 3.13 / 30 | 13 | 40.7 | 12 | documented | 0.95 |
| 12 | **Justification demanded — Singular configurations**<br>`FM-DT-08-singularity` | Singular configurations | 4.04 / 30 | 10 | 40.4 | 10 | documented | 0.95 |
| 13 | **All branches requested — Inverse kinematics**<br>`FM-DT-07-inverse_kinematics` | Inverse kinematics | 4.04 / 30 | 9 | 36.4 | 9 | documented | 0.95 |
| 14 | **Static balance requested — Statics / force transformation**<br>`FM-DT-16-statics` | Statics / force transformation | 3.27 / 30 | 9 | 29.4 | 8 | documented | 0.95 |
| 15 | **Justification demanded — Differential kinematics / Jacobian**<br>`FM-DT-08-jacobian` | Differential kinematics / Jacobian | 4.62 / 30 | 6 | 27.7 | 6 | documented | 0.91 |
| 16 | **Symbolic form demanded — Differential kinematics / Jacobian**<br>`FM-DT-04-jacobian` | Differential kinematics / Jacobian | 3.39 / 30 | 6 | 20.3 | 6 | documented | 0.91 |
| 17 | **Minimum-norm solution specified — Differential kinematics / Jacobian**<br>`FM-DT-05-jacobian` | Differential kinematics / Jacobian | 5.0 / 30 | 3 | 15.0 | 3 | documented | 0.8 |
| 18 | **Orientation inverse singular — Singular configurations**<br>`FM-DT-17-singularity` | Singular configurations | 6.88 / 30 | 2 | 13.8 | 2 | documented | 0.77 |
| 19 | **Orientation inverse singular — Orientation / Euler angles**<br>`FM-DT-17-orientation` | Orientation / Euler angles | 10.0 / 30 | 1 | 10.0 | 1 | documented | 0.73 |
| 20 | **Joint limits active — DH frame assignment**<br>`FM-DT-13-dh_frames` | DH frame assignment | 2.31 / 30 | 4 | 9.2 | 4 | documented | 0.84 |
| 21 | **Zero configuration probe — Differential kinematics / Jacobian**<br>`FM-DT-15-jacobian` | Differential kinematics / Jacobian | 1.77 / 30 | 2 | 3.5 | 2 | reconstructed | 0.55 |
| 22 | **Singularity existence probed — Singular configurations**<br>`FM-DT-03-singularity` | Singular configurations | 3.0 / 30 | 1 | 3.0 | 1 | documented | 0.73 |
| 23 | **Singular cases flagged — Singular configurations**<br>`FM-DT-02-singularity` | Singular configurations | 3.0 / 30 | 1 | 3.0 | 1 | documented | 0.73 |
| 24 | **Singular cases flagged — Inverse kinematics**<br>`FM-DT-02-inverse_kinematics` | Inverse kinematics | 3.0 / 30 | 1 | 3.0 | 1 | documented | 0.73 |
| 25 | **Minimum-norm solution specified — Singular configurations**<br>`FM-DT-05-singularity` | Singular configurations | 3.0 / 30 | 1 | 3.0 | 1 | documented | 0.73 |
| 26 | **Zero configuration probe — Statics / force transformation**<br>`FM-DT-15-statics` | Statics / force transformation | 2.5 / 30 | 1 | 2.5 | 1 | reconstructed | 0.52 |
| 27 | **Static balance requested — Differential kinematics / Jacobian**<br>`FM-DT-16-jacobian` | Differential kinematics / Jacobian | 2.5 / 30 | 1 | 2.5 | 1 | documented | 0.73 |

`marks_at_risk` is the mean marks exposed **per exam in which the mode appears**, on Sapienza's 30-point scale, under an equal split across exercises and then across task clauses. Seven midterms in the corpus do state per-exercise points and all of them sum to 30, which corroborates the total; no ordinary written exam states a split, so the split is modelled and is labelled `reconstructed` wherever it appears.

## 4. The guardrail

Two independent validators run on every build:

| Validator | Question it asks | Catches |
|---|---|---|
| Structural | Are all required fields present, typed and in range? | Malformed entries |
| Grounding | Does the quote occur verbatim on the cited page, after whitespace normalisation? | Invented or misplaced evidence |

The build writes `data/atlas.json` **only if both pass**. This run:

- entries emitted: **27**
- quotes rejected because they did not ground: **0**
- quotes rejected because they did not contain the rule's trigger: **0**
- quotes rejected as too short to be evidence: **0**
- concepts with no lecture cross-reference: **0** (none)

## 5. Documented vs reconstructed

| Strength | Meaning | Entries |
|---|---|---|
| `documented` | The exam wording itself pre-empts the error. The quote is the evidence. | 25 |
| `reconstructed` | The exam states the task; the link from task to student behaviour is the rule's inference, and is named as such. | 2 |

The atlas never presents the second as the first. A judge who disagrees with a `reconstructed` entry can attack the named rule in `atlas/rules.py` instead of arguing with a hidden leap.

## 6. Detail — highest-ranked modes

### Minimum time under bounds — Trajectory planning (joint space)
`FM-DT-11-trajectory` · documented · confidence 0.95 · 7.74/30 marks at risk · 30 questions in 18 exams

**Trigger (in the paper).** Minimum-time motion subject to acceleration or velocity bounds.

**What goes wrong.** Times the motion by picking a comfortable duration, or uses a symmetric profile that satisfies the bound on one joint only.

**Root misconception.** A feasible trajectory is a minimal one if it looks tight.

**Exam evidence.** `Robotics1_26.07.13` — Exercise 2, p. 2

> polynomial joint trajectory q(t) that realizes a coordinated motion in minimum time T of two robot joints from q(0) = (0, −π/2) to q(T ) = (π/4, π/4) [rad], with boundary conditions q̇(0) = q̈(0)

**Taught in.** `13_TrajectoryPlanning` — p. 29

> Trajectory planning in joint space

**Probe.** Which joint saturates its bound first, and for how long?

**Correction.** Each joint has its own minimal time under its own bound. The coordinated time is the maximum, then the slower joint is scaled to fill it.

---

### Symbolic form demanded — Direct kinematics
`FM-DT-04-direct_kinematics` · documented · confidence 0.95 · 3.67/30 marks at risk · 47 questions in 38 exams

**Trigger (in the paper).** The task requires a symbolic expression, not a number.

**What goes wrong.** Substitutes the numeric link lengths at the first opportunity, then cannot simplify, factor or find the singular set later.

**Root misconception.** Numbers make it concrete, so numbering early is safer.

**Exam evidence.** `Robotics1_18.01.11` — Exercise 1, p. 1

> the Denavit-Hartenberg (DH) convention and complete the as- sociated symbolic table of parameters, specifying also the signs of the non-zero constant parameters. Draw the frames and fill in the table directly on the extra sheet

**Taught in.** `09_DirectKinematics` — p. 8

> Direct kinematics of 2R planar robot just using

**Probe.** Write k(q) with the link lengths still as symbols; where does l2 appear twice?

**Correction.** Carry symbols to the end. Numbers are a final check, never an intermediate step, because the structure is what is being marked.

---

### Rank and null space demanded — Singular configurations
`FM-DT-10-singularity` · documented · confidence 0.95 · 3.69/30 marks at risk · 25 questions in 20 exams

**Trigger (in the paper).** The task asks for rank and a null-space basis, not just 'J is singular'.

**What goes wrong.** Computes det(J) = 0, declares a singularity, and moves on without producing rank or any basis.

**Root misconception.** Singular means the determinant vanished; the structure of what collapsed is extra.

**Exam evidence.** `Robotics1_18.02.05` — Exercise 3, p. 1

> next a configuration q 0 where J L is full rank, and substitute all the available numerical data in this matrix. Sketch this configuration and compute then a non-zero joint velocity q̇ 0 ∈ R4 such

**Taught in.** `11_DifferentialKinematics` — p. 32

> finding and analyzing in advance the mobility of a robot helps in singularity avoidance during trajectory planning and motion control

**Probe.** If det(J) = 0, what is rank(J) here, and name one vector J sends to zero.

**Correction.** Compute rank explicitly and exhibit a null vector. The null space is the self-motion — that is the physically meaningful output.

---

### Boundary conditions pinned — Trajectory planning (joint space)
`FM-DT-09-trajectory` · documented · confidence 0.95 · 4.99/30 marks at risk · 17 questions in 16 exams

**Trigger (in the paper).** Velocity and acceleration are pinned at both ends.

**What goes wrong.** Fits position only and produces a trajectory with a velocity jump at the endpoints, or forgets that a cubic cannot zero acceleration too.

**Root misconception.** Boundary conditions on position are the ones that matter; velocity follows along.

**Exam evidence.** `Robotics1_15.02.06` — Exercise 2, p. 2

> with trapezoidal speed profile so as to obtain a rest-to-rest circular trajectory p(t) from A to B that performs the transfer in minimum time T under the maximum velocity and acceleration constraints kṗ(t)k ≤ Vmax

**Taught in.** `13_TrajectoryPlanning` — p. 29

> Trajectory planning in joint space

**Probe.** How many boundary conditions did you impose, and how many free coefficients does your polynomial have?

**Correction.** Count degrees of freedom against conditions before choosing the degree. Cubic zeroes velocity; quintic is needed to zero acceleration too.

---

### Justification demanded — Direct kinematics
`FM-DT-08-direct_kinematics` · documented · confidence 0.95 · 4.54/30 marks at risk · 15 questions in 12 exams

**Trigger (in the paper).** A 'show that' / 'justify' imperative whose conclusion is already given.

**What goes wrong.** Substitutes a number, sees it works, and writes 'verified'. Or restates the claim in different words.

**Root misconception.** Matching the stated answer is the same as establishing it.

**Exam evidence.** `Robotics1_25.06.11` — Exercise 2, p. 1

> joints!] Evaluate numerically the direct kinematics in this configuration and verify the correctness of the obtained end-effector position and orientation with respect to the base frame RF0 . Figure 1: The ABB CBR 15000 collaborative robot.

**Taught in.** `09_DirectKinematics` — p. 8

> Direct kinematics of 2R planar robot just using

**Probe.** Show me the step where the conclusion follows — what would break if the claim were false?

**Correction.** Prove the general case symbolically; use the numeric instance only as a check. 'Show that' is a proof obligation, not a spot-check.

---

### Rank and null space demanded — Differential kinematics / Jacobian
`FM-DT-10-jacobian` · documented · confidence 0.95 · 3.39/30 marks at risk · 18 questions in 17 exams

**Trigger (in the paper).** The task asks for rank and a null-space basis, not just 'J is singular'.

**What goes wrong.** Computes det(J) = 0, declares a singularity, and moves on without producing rank or any basis.

**Root misconception.** Singular means the determinant vanished; the structure of what collapsed is extra.

**Exam evidence.** `Robotics1_18.02.05` — Exercise 3, p. 1

> next a configuration q 0 where J L is full rank, and substitute all the available numerical data in this matrix. Sketch this configuration and compute then a non-zero joint velocity q̇ 0 ∈ R4 such

**Taught in.** `11_DifferentialKinematics` — p. 2

> instantaneous velocity mappings can be obtained through time differentiation of the direct kinematics or in a geometric way, directly at the differential level

**Probe.** If det(J) = 0, what is rank(J) here, and name one vector J sends to zero.

**Correction.** Compute rank explicitly and exhibit a null vector. The null space is the self-motion — that is the physically meaningful output.

---

### Closed form required — Inverse kinematics
`FM-DT-06-inverse_kinematics` · documented · confidence 0.95 · 2.81/30 marks at risk · 21 questions in 19 exams

**Trigger (in the paper).** The task asks for an analytic inverse, not an iterative one.

**What goes wrong.** Sets up Newton's iteration and stops when the residual is small, delivering a point rather than a solution set.

**Root misconception.** A sufficiently good numeric answer is the same object as the closed form.

**Exam evidence.** `Robotics1_Midterm_2025-26_25.11.21` — Exercise 5b, p. 2

> For a desired r d , solve in closed form the inverse kinematics problem of this robot, assuming that joints have unlimited range. In doing so, identify the conditions for the existence and the

**Taught in.** `10_InverseKinematics` — p. 3

> Inverse kinematics problem

**Probe.** How many distinct q map to your p_d, and which equation did you use to separate them?

**Correction.** Isolate q1 from the position equation, then solve the remaining planar sub-problem. The count of branches is part of the answer.

---

### Coordination required — Trajectory planning (joint space)
`FM-DT-12-trajectory` · documented · confidence 0.95 · 4.98/30 marks at risk · 10 questions in 10 exams

**Trigger (in the paper).** Two joints or two robots must arrive together.

**What goes wrong.** Plans each joint independently to its own minimum time, so they finish at different instants and the path is not what was asked.

**Root misconception.** Synchronising is a detail of presentation; each axis is a separate problem.

**Exam evidence.** `Robotics1_21.10.19` — Exercise 2, p. 1

> using the associated symbolic DH parameters, determine a smooth and coordinated rest-to-rest joint trajectory that will move in T seconds the robot gripper from the initial position pi = (a1 + a3 , 0, 0) to

**Taught in.** `13_TrajectoryPlanning` — p. 29

> Trajectory planning in joint space

**Probe.** Joint 2 finishes after joint 1 — what is the end-effector doing in between?

**Correction.** Plan per joint, take the maximum duration, then time-scale every other joint to match. Coordination is a constraint, not a tidy-up.

---

### Frame placement pinned — DH frame assignment
`FM-DT-14-dh_frames` · documented · confidence 0.95 · 3.16/30 marks at risk · 15 questions in 14 exams

**Trigger (in the paper).** The task dictates where a frame origin must sit.

**What goes wrong.** Places the last frame at the flange instead of the specified point, then inherits an offset that contaminates every later answer.

**Root misconception.** Frame origins are arbitrary as long as the transform is right.

**Exam evidence.** `Robotics1_17.01.11` — Exercise 1, p. 1

> the link frames according to the Denavit-Hartenberg convention. Place the origin of the last frame coincident with point P . Make the free choices that are available so as to eliminate (i.e., “zeroing out”) as many

**Taught in.** `09_DirectKinematics` — p. 12

> Denavit-Hartenberg (DH) frames joint axis joint axis joint

**Probe.** Your origin sits at the flange — what is the constant offset to P, and which matrix absorbed it?

**Correction.** Place origins to the stated rule first; frame choice is a convention you must honour, and every downstream matrix depends on it.

---

### Sign gauge pre-empted — DH frame assignment
`FM-DT-01-dh_frames` · documented · confidence 0.95 · 2.9/30 marks at risk · 16 questions in 15 exams

**Trigger (in the paper).** The task constrains the sign of the DH parameters before the student starts.

**What goes wrong.** Assigns z-axes in the opposite direction, so d or a come out negative, then flips a sign somewhere downstream to compensate.

**Root misconception.** DH parameters are whatever the diagram shows; the convention is decoration rather than a gauge choice you must declare.

**Exam evidence.** `Robotics1_24.02.16` — Exercise 2a, p. 2

> Denavit-Hartenberg (D-H) convention, so that all constant D-H parameters are non-negative. Provide the table with the corresponding parameters. The first frame should be placed on the floor at the robot base and the origin of the

**Taught in.** `09_DirectKinematics` — p. 12

> Denavit-Hartenberg (DH) frames joint axis joint axis joint

**Probe.** For this arm, which DH entries can be made nonnegative, and which axis direction did you have to reverse to do it?

**Correction.** Fix the z-axis direction rule first, then read the table off. Verify the sign of every d and a against the drawn axis before writing k(q).

---

## 7. Two questions this atlas refuses

**"What will students score on question 3?"** — refused (`NO_COHORT_DATA`). The corpus contains questions and solutions. It contains no student responses, no marks, no distribution. A predicted score would be invented, so none is given.

**"Give me failure modes for a course with no material."** — refused (`NO_CORPUS`). With no citable documents there is nothing to report, and an atlas of guesses is exactly what this project exists to avoid.

## 8. Limitations

* **Marks are modelled, not measured.** No ordinary written exam states per-exercise points. Ranking is therefore *exposure under an equal split*, not observed loss.
* **No cohort data exists in the corpus.** Nothing here says what students actually did. It says what the papers are built to catch. That distinction is the whole honesty budget of the project.
* **Rules are the author's reading.** 17 rules, each named and quotable, but a different examiner could read the same instruction differently. `reconstructed` entries say so.
* **Extraction artefacts.** Inline mathematics is mangled by PDF extraction, so quotes are prose spans; equations are never quoted and never used as evidence.
* **Format-era gap.** 27 pre-2013 papers are excluded because they do not decompose into per-question units.
* **Single course, by design.** Textbooks arrive with different vocabularies; the corpus was chosen so comparisons are not attempted.

## 9. Self-validation sample

**Sample size 8 failure modes**, drawn at random (`python -m atlas.cli spotcheck --sample 8 --seed 11`, so the draw is reproducible). Each was checked by opening the cited PDF page and reading the surrounding exercise, not by re-running the substring test:

* confirmed: **8/8**
* error rate: **0.0%**
* distinct quoted instruments: 6/8 — two entries read the same sentence for different tells, so the independent sample is smaller than the mode count.

| Entry | Cited page | Verdict | Independent source | Note |
|---|---|---|---|---|
| `FM-DT-08-jacobian` | Robotics1_25.02.07_text p.1 | **hit** | yes | EXAM SAYS 'Verify that this is not a singular case by analyzing the Jacobian'. That is a justification demand, not a numeric check; the entry's wrong-turn (answering 'verified' without the analysis) is exactly what the clause pre-empts. |
| `FM-DT-17-singularity` | Robotics1_21.07.12 p.2 | **hit** | yes | EXAM SAYS 'check whether or not a representation singularity is encountered'. The demand to check for it documents that missing it is anticipated. The asin/atan2 mechanism in the entry is inference, and the entry is labelled by the exam demand. |
| `FM-DT-05-singularity` | Robotics1_26.07.13 p.1 | **hit** | yes | EXAM SAYS 'joint velocity with minimum norm that realizes v' at a singular q. Minimum-norm is stipulated verbatim, so the arbitrary-particular-solution error is pre-empted. |
| `FM-DT-16-jacobian` | Robotics1_23.02.13 p.2 | **hit** | yes | EXAM SAYS 'all non-zero end-effector wrenches w that are statically balanced by tau = 0'. This is a statics-through-J^T question; the entry's wrong-turn (balancing at the end-effector) is the error that makes tau=0 look impossible. |
| `FM-DT-02-inverse_kinematics` | Robotics1_26.07.13 p.1 | **hit** | no (shared quote) | EXAM SAYS 'determine all IK solutions in closed form, taking into account the singular cases'. The singular-cases clause is the tell. Same sentence also supports DT-06/DT-07. |
| `FM-DT-05-jacobian` | Robotics1_26.01.12 p.2 | **hit** | yes | EXAM SAYS 'there are infinite solutions and you choose the one with minimum norm'. Three explicit cases (unique / infinite / none) -- the entry's error is picking an arbitrary one. |
| `FM-DT-17-orientation` | Robotics1_21.07.12 p.2 | **hit** | no (shared quote) | Same sentence as FM-DT-17-singularity, read for the Euler-angle branch rather than for the Jacobian. Counted as a hit but NOT as an independent source. |
| `FM-DT-06-inverse_kinematics` | Robotics1_Midterm_2025-26_25.11.21 p.2 | **hit** | yes | EXAM SAYS 'solve in closed form the inverse kinematics problem'. Closed form is required verbatim, so a Newton iteration is not an acceptable answer. |

**One defect was found and fixed before this table was drawn.** A first pass (seed 7) sampled an entry whose quote — "count the motor revolutions needed to cover the entire joint range" — was an encoder-sizing question, not a question about workspace being cut by joint stops. The rule's pattern (`joint range`) was too broad, so `DT-13` gained an explicit veto for encoder/resolution/gear-ratio contexts. That veto now rejects 1 clause in the corpus, and the count is published in `coverage.json` as `clauses_vetoed_by_rule_precision`. The number above is the post-fix error rate; the pre-fix draw was 7/8.
