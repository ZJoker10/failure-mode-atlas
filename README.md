# Failure-Mode Atlas

[![CI](https://github.com/ZJoker10/failure-mode-atlas/actions/workflows/ci.yml/badge.svg)](https://github.com/ZJoker10/failure-mode-atlas/actions/workflows/ci.yml)

**A ranked, evidence-linked map of what a university robotics course's exams are built to catch — and a pipeline that refuses to say anything the documents don't support.**

Draft entry for **BESTech Student Tech Clash 2026**, case study *AI on Campus* (Direction 1: Teaching).

**Team:** Zeyad Kandil · Maxime Kerger · Berk Ateşlap · Angelica Corbalán

The corpus is the publicly published lecture and exam material of **Robotics 1**, Sapienza University of Rome. **None of that material is redistributed in this repository** — see [Provenance](#provenance-and-what-this-repo-does-not-contain). What is here is the pipeline, the rule book, the validated atlas and the tests.

---

## The claim

A professor's exam encodes an implicit theory of student error. Some of that theory leaks into the wording: an instruction that only makes sense if a specific mistake is expected is *documented* evidence that the mistake is expected.

> "…assign the Denavit-Hartenberg (D-H) convention, **so that all constant D-H parameters are non-negative**."

That clause is not neutral. It exists because students choose frame conventions that make parameters negative. The clause is quotable; the inference from clause to student behaviour is named, numbered and auditable — it is rule `DT-01` in [`atlas/rules.py`](atlas/rules.py), not a hidden leap inside a model.

So the product is narrow on purpose:

* **Find** the failure modes the exams pre-empt.
* **Rank** them by marks exposed × questions affected.
* **Prove** each one with a verbatim quote from a page anyone can open.

It does **not** predict what students did. There is no cohort data in this corpus, and the system says so — in code, twice, before retrieval runs.

---

## Quick start

Requires Python 3.11+ and [poppler](https://poppler.freedesktop.org/) (`pdftotext`, `pdfinfo`). No Python packages are needed.

```bash
cd failure-mode-atlas

# 1. corpus -> validated atlas (writes data/*.json, refuses on any ungrounded claim)
python -m atlas.cli build

# 2. ask it something
python -m atlas.cli ask "Why do students get DH frame signs wrong?"

# 2b. the quiz, without a browser (same scorer as the page)
python -m atlas.cli quiz --answers 0120120120

# 2c. or the Studio, to run the same pipeline on your own files
./studio.sh

# 3. human report + viewer
python -m atlas.report          # -> data/REPORT.md
python -m atlas.view            # -> web/index.html

# 4. reproduce the self-validation draw
python -m atlas.cli spotcheck --sample 8 --seed 11

# 5. tests
python -m unittest discover -s tests -v
```

### Opening the viewer

Three ways, in order of convenience:

```bash
./demo.sh                       # http://localhost:8787/  (serves the repo, opens a browser)
```

```bash
xdg-open web/index.html         # or: open web/index.html   (macOS)
```

or just **double-click `web/index.html`** in a file manager. The file is self-contained — data inlined, no fetch, no build step, works from `file://`. A copy of that one file is enough to show on another machine.

**If it does not open, it is almost always one of these:**

| Symptom | Cause | Fix |
|---|---|---|
| You see HTML source text | You clicked `web/index.html` **on github.com**. GitHub serves repository files as text and never renders HTML. | Clone the repo and open the file locally, or run `./demo.sh` |
| Nothing happens on double-click | No default application for `.html` | `xdg-open web/index.html`, or `./demo.sh` |
| Blank page or unstyled text | The file was truncated while copying | Re-copy the whole 190 KB file, or `python -m atlas.view` to regenerate |
| Page loads but links do nothing | You are looking at an old build | `python -m atlas.view` rewrites it |
| Works locally, not over SSH | `file://` paths and `localhost` refer to the remote machine | Copy `web/index.html` to your machine and open that single file |

The viewer is verified interactively, not just visually: in headless Chromium a scripted click on row 1 routes to `#/mode/…` and renders the detail screen, and the evidence link opens `#/evidence/…` with the citation and the quoted span.

The corpus itself is **not** committed (210 MB of third-party PDFs), and neither are copies of its pages. `data/atlas.json` carries the citation and the quoted span for every claim; `corpus/_fetch_log.json` records where each source document came from. See [`corpus/README.md`](corpus/README.md) to rebuild the corpus and re-run the grounding check.

### The screens

| Screen | Route | What it answers |
|---|---|---|
| Study-profile quiz | `#/` (landing) or `#/quiz` | What kind of studier are you, and where should you start? |
| Quiz result | `#/quiz/<10 digits>` | A shareable profile, three entries to read first, and the caveat. |
| Atlas index | `#/atlas` | What are the modes, and in what order? |
| Failure-mode detail | `#/mode/<id>` | What exactly goes wrong, and where is it proven? |
| Evidence viewer | `#/evidence/<id>/exam` | Show me the quote on the page it claims to come from. |
| **Ask** | `#/ask` | Ask a question and get the matching entries back — or a refusal. |
| Coverage | `#/coverage` | What was read, what was refused, what is modelled? |

The **Ask** screen is retrieval over the 27 validated entries, not generation. It is also where both refusals are visible without a terminal:

- *"What will students score on question 3?"* → `NO_COHORT_DATA` card. The guard runs before retrieval, so the question never reaches the atlas.
- *"What is the capital of Peru?"* → *"No match in the atlas"* rather than the nearest entry dressed up as an answer.

The guard is not re-implemented in JavaScript. `atlas/answer.py` owns `COHORT_PATTERNS`, `NO_COHORT_REASON`, `STOP` and `ranked_matches`; the viewer inlines that data at build time and `tests/test_atlas.py::TestAnswerParity` asserts that the parsed JSON block in `web/index.html` equals the Python source. The CLI and the browser cannot drift apart without a test failing.

The coverage screen reports the grounding outcome rather than offering a live checker: the test runs at build time, against the page text, and a failure writes `REJECTED.txt` instead of an entry. Because the source pages are not redistributed here, re-running it needs the corpus — `python -m atlas.cli build`, or `tests/test_atlas.py`, which feeds the writer a fabricated quote and asserts that nothing is published.

All four screens the brief asks for are present. Two more sit around them: **Quiz**, which is the
landing page because it is the cheapest way in, and **Ask**, which makes the refusal behaviour
visible in five seconds. Both are additive — `#/atlas` goes straight to the ranked index.

---

## The quiz — and why it is not a learning-styles test

The viewer opens on a ten-question study-profile quiz. It takes under a minute, works with the
number keys, and exists for one reason: a visitor who does not know the course needs somewhere to
start that is not "read 27 entries".

**What it measures.** Three axes, each a weighted sum over the answers:

| Axis | Positive end | Negative end |
|---|---|---|
| Representation | figure-first | symbol-first |
| Approach | method-first | derivation-first |
| Warm-up | example-first | attempt-first |

The profile is the nearest of four quadrants — *Sketch first, then the recipe*; *Picture first, then
rebuild it*; *Symbols first, then the method*; *Definitions first, then derive* — plus a separate
warm-up note. Each profile opens three entries, chosen because that habit meets an explicit warning
in the exam wording:

| Profile | Opens |
|---|---|
| Sketch first, then the recipe | DH frames · singular configurations · trajectory planning |
| Picture first, then rebuild it | singular configurations · statics · orientation |
| Symbols first, then the method | inverse kinematics · trajectory planning · DH frames |
| Definitions first, then derive | Jacobian · orientation · inverse kinematics |

**What it does not measure.** How you learn, what you will score, or which teaching would suit you.
"Visual / auditory / kinaesthetic" has little support as a way to improve outcomes, and this corpus
holds no student responses at all. So the quiz records only what you say you do, and the
profile-to-entry mapping is an editorial choice labelled `reconstructed` — the same label the atlas
puts on every other inference. The result screen says all of this in plain words, above the fold
for the disclaimer and not buried in a footnote.

**One scorer, two surfaces.** The questions, weights, profile copy and disclaimer live in
[`atlas/quiz.py`](atlas/quiz.py). The viewer inlines that content as data and runs a five-line
weighted sum; `python -m atlas.cli quiz` runs the Python one. Three tests keep them honest: the
inlined payload must equal `quiz.payload()`, every one of the 3¹⁰ answer sets must land in a known
profile with all axes inside [-1, 1], and the shipped JavaScript scorer is executed **under node**
and compared to Python for a set of answer vectors. Answers are never sent anywhere; a finished quiz
is encoded in the URL (`#/quiz/0120120120`) so a result can be linked.

---

## Studio — the same discipline, applied to your own material

The atlas is one worked example on one course. **Studio** is the second mode: upload your own
course material, and get it back in the shape you say you study in.

```bash
./studio.sh                     # http://localhost:8788/  (Ctrl-C to stop)
```

No account, no sign-in, no network call. The page is served from `127.0.0.1`, the parsing happens
in that Python process, and the uploads live in `data/uploads/<session>/` on this machine until you
delete them. `./studio.sh 9000` picks another port; `fuser -k 8788/tcp` frees a stale one.

**The flow.** A twelve-question preference quiz (Visual / Aural / Read-write / Kinesthetic) →
the result is saved in `localStorage` under `fma.vark.v1`, so a second visit skips the quiz →
upload PDF, PPTX or DOCX → a report → download it as Markdown or PDF.

**What tailoring actually changes.** Order and emphasis, never facts. Every edition prints the
same extracted sentences with the same page or slide references; the preference decides what
comes first:

| Edition | Shape |
|---|---|
| Visual | figures first — page renders or images lifted from your own file, nothing redrawn |
| Aural | the same sentences as a script, with the browser's own speech synthesiser |
| Read/write | headings, dense paragraphs, definitions in reading order |
| Kinesthetic | numbered checks over the extracted steps, with a finish tick |

Each sentence appears exactly once per report: definition sentences are excluded from the key
points and live only in the glossary block, and the Aural edition has no separate transcript
panel duplicating its own script. The concept map is generated from term co-occurrence and is
labelled as such — it is a reading aid, not a diagram the material contains.

**What it does not do.** No model is called, so nothing is paraphrased, summarised or invented —
every sentence in the report is a substring of your upload. It does not understand the material,
measure difficulty, predict a mark, or claim that matching a modality raises one. A scanned PDF
with no text layer is *flagged* rather than quietly summarised, and figures are capped rather than
stretched.

### Why VARK, and why it is still not a learning-styles claim

The quiz is a preference questionnaire with an explicit caveat on the result screen: it says how
you like material presented, not how you learn, and matching a modality is not shown to improve
outcomes. This is the same position as the study-profile quiz above, applied to a coarser
four-letter vocabulary that the audience already recognises. The letters never filter anything — a
Visual report still contains every sentence the Read/write one does.

One scorer, again: the questions and the caveat live in [`atlas/vark.py`](atlas/vark.py), the page
inlines them as data, and the JavaScript tally is compared against the Python `score()` in the
test suite. Four counters cannot drift far, but they are checked.

### How the exports work

Markdown and JSON are generated server-side from the same report model the page renders, so a
download cannot disagree with the screen. PDF is the print page rendered by headless Chrome. That
last step is the only one with an external dependency, so it tries `chromium`, `google-chrome`,
then the Playwright headless shell, and stages the HTML **inside the session directory** — a snap
Chromium is confined and cannot read `/tmp`, which is exactly how this failed the first time. If no
Chrome is present the button reports it and the Markdown download still works.

### Formats and their limits

| Format | Read with | What survives |
|---|---|---|
| PDF | `pdftotext -layout`, `pdfimages`, `pdftoppm` | prose lines, embedded images; inline maths is mangled, so runs of symbols are dropped rather than shown as broken quotes |
| PPTX | stdlib `zipfile` + `ElementTree` | slide text and pictures, one section per slide that has prose |
| DOCX | stdlib `zipfile` + `ElementTree` | headings become numbered sections, body paragraphs, embedded images |

A page or slide with no prose is not counted as a section. The counts on the page (pages, sections,
definitions, figures) are the counts the report is built from, not an estimate.

---

## Architecture

```mermaid
graph TD
    subgraph INPUT["Input — corpus"]
        EX["Exam papers<br/>160 PDFs, 884 pages"]
        SL["Lecture decks<br/>20 PDFs, 771 pages"]
        SY["Syllabus<br/>exam index + programme"]
    end

    subgraph GATE0["Refusal gate — before any retrieval"]
        Q0{"Cohort question<br/>or empty corpus?"}
        R0["Refuse<br/>NO_COHORT_DATA / NO_CORPUS<br/>nothing is generated"]
    end

    subgraph KNOWLEDGE["Knowledge — what the documents say"]
        ING["Ingest<br/>pdftotext → pages"]
        SEG["Segment<br/>exams → exercises → clauses<br/>each clause keeps a page anchor"]
        TAX["Concept taxonomy<br/>11 concepts + preferred deck"]
        RUL["Design-tell rules<br/>17 rules, each a named inference<br/>with patterns, probe, correction, veto"]
    end

    subgraph TOOLS["Tools — deterministic code, no LLM"]
        XRF["Cross-reference<br/>clause → lecture page"]
        MRK["Marks model<br/>equal split, 30-point scale"]
        RANK["Rank<br/>marks at risk × questions affected"]
        STR["Structural check<br/>required fields, types, ranges"]
        GND["Grounding check<br/>quote must occur verbatim<br/>on the cited page"]
    end

    subgraph DECISIONS["Decisions — gates"]
        G1{"Structural<br/>problem?"}
        G2{"Ungrounded<br/>quote?"}
        D2["REJECTED.txt<br/>exit 1, no atlas"]
        D1["Publish entry"]
    end

    subgraph OUTPUT["Output"]
        AJ["atlas.json<br/>27 validated entries"]
        CV["coverage.json<br/>what was read and excluded"]
        PROV["corpus/_fetch_log.json<br/>source manifest, no PDFs"]
        RP["REPORT.md"]
        WV["web/index.html<br/>4 screens"]
    end

    EX --> Q0
    SL --> Q0
    SY --> Q0
    Q0 -- yes --> R0
    Q0 -- no --> ING
    ING --> SEG --> RUL
    SL --> TAX --> XRF
    RUL --> XRF
    XRF --> MRK --> RANK
    RANK --> STR --> G1
    G1 -- yes --> D2
    G1 -- no --> GND --> G2
    G2 -- yes --> D2
    G2 -- no --> D1 --> AJ
    AJ --> RP
    AJ --> WV
    PROV --> AJ
    CV --> WV

    subgraph STUDIO["Studio — the same discipline, your own material"]
        UP["Upload<br/>PDF · PPTX · DOCX"]
        PRS["Parse<br/>pdftotext / OOXML<br/>figures extracted, not redrawn"]
        AN["Analyse<br/>one report model<br/>sentences + references + glossary"]
        ED["Four editions<br/>V · A · R · K<br/>same sentences, order changes"]
        EX2["Exports<br/>page · Markdown · PDF"]
    end

    UP --> PRS --> AN --> ED --> EX2
    EX2 -. "no model called;<br/>every line is a substring<br/>of the upload" .- GND

    classDef primary fill:#00ffff,color:#000,stroke:#080d1a
    classDef gateway fill:#ee82ff,color:#fff,stroke:#080d1a
    classDef data fill:#ff1493,color:#fff,stroke:#080d1a
    classDef external fill:#444,color:#ccc,stroke:#666

    class ING,SEG,TAX,RUL,PRS,AN,ED primary
    class Q0,G1,G2,GND,STR,MRK,XRF,RANK,D1,D2,R0 gateway
    class AJ,CV,PROV,RP,WV,EX2 data
    class EX,SL,SY,UP external

    style INPUT fill:#080d1a,color:#00ffff,stroke:#00ffff
    style GATE0 fill:#080d1a,color:#00ffff,stroke:#00ffff
    style KNOWLEDGE fill:#080d1a,color:#00ffff,stroke:#00ffff
    style TOOLS fill:#080d1a,color:#00ffff,stroke:#00ffff
    style DECISIONS fill:#080d1a,color:#00ffff,stroke:#00ffff
    style OUTPUT fill:#080d1a,color:#00ffff,stroke:#00ffff
    style STUDIO fill:#080d1a,color:#00ffff,stroke:#00ffff
```

**Legend.** Cyan = knowledge and transformation modules. Magenta = tools and gates that decide. Pink = stored artefacts. Grey = external input. Dark subgraph headers = pipeline stages. Studio is a second entry point
into the same idea: parse the file, build one report model, present it four ways, generate nothing.

### Input → knowledge → tools → decisions → output, in words

* **Input** is one course only: exam papers, the decks they cross-reference, and the syllabus. No multi-course support, by design.
* **Knowledge** is built in three steps. Ingest turns PDFs into page text. Segment turns an exam into exercises and each exercise into task clauses, keeping the page each clause starts on. Rules name the inferences. Everything after this step is counting and citing.
* **Tools** do not generate language. `evidence.py` verifies, `build.py` measures and ranks, and neither calls a model.
* **Decisions** are gates with no human in the loop. A claim either grounds or the build refuses wholesale. A question either has cohort data behind it or it is refused before retrieval.
* **Output** is JSON, Markdown and one self-contained HTML file, all derived from the same validated list.

### Pipeline detail

| Stage | File | What it decides |
|---|---|---|
| Ingest | `atlas/ingest.py` | A page with <80 chars is *scanned*; no claim is ever made from it. |
| Segment | `atlas/segment.py` | `Exercise N` / `Question #N` headings; solutions cut off at `Solution of Midterm Test`, `Soluzioni`, `Svolgimento`; clauses split on lettered/roman/bullet markers, else on task-verb sentences. |
| Rules | `atlas/rules.py` | 17 design tells. Each has a regex, the trigger, the wrong turn, the misconception, a probe, a correction, and optionally a `veto`. |
| Evidence | `atlas/evidence.py` | Structural + grounding validators, plus first-class `Refusal` objects. |
| Build | `atlas/build.py` | Fires rules over clauses, picks the tightest quote, cross-references the lecture page, models marks, ranks, and gates the write. |
| Report | `atlas/report.py` | Markdown, including the self-validation table. |
| View | `atlas/view.py` | Four hash-routed screens, data inlined. |

---

## How one failure mode is made

1. **A rule fires.** `DT-11` matches *"in minimum time"* under velocity/acceleration bounds.
2. **A quote is cut.** The sentence window is tightened around the trigger, then trimmed of leading noise. The quote must contain the firing span, be ≥2 words and ≥12 characters, and look like prose (no equations, URLs, or bullet debris).
3. **The exam is counted.** One occurrence per clause, deduplicated per exam.
4. **The lecture page is found.** The concept's preferred deck is searched; the earliest page within 10% of peak keyword density wins ("where it is first taught").
5. **Marks are modelled.** 30 marks split equally across exercises, then across clauses. `marks_at_risk` is the mean exposure *per exam in which the mode appears*.
6. **Ranking.** `score = marks_at_risk × questions_affected`. The report shows the product, so the ordering is legible rather than asserted.
7. **The gate.** Structural pass, then grounding pass. Both, or nothing.

---

## The guardrail is code, not prompt

```
$ python -m atlas.cli build
wrote data/atlas.json: 27 failure modes, 97/160 exams analysed, 351 questions parsed,
0 quote(s) rejected by grounding.
```

There are two validators because there are two distinct ways to be wrong:

| Validator | Question it asks | Why schema alone is not enough |
|---|---|---|
| **Structural** | Are all required fields present, typed, and in range? | A schema validator happily passes a beautifully formatted, entirely invented quote. |
| **Grounding** | Does the quote occur verbatim on the cited page, after whitespace normalisation? | This is the check that makes the atlas inspectable. |

`build.write()` runs both. Any problem and it writes `REJECTED.txt` with the offending claims and exits `1` — **it does not write a shorter atlas**. A missing entry is a gap; a made-up entry is a lie, and the two must not look the same.

Matching is done on a whitespace-flattened, case-folded form of both quote and page, because PDF extraction inserts line breaks and soft hyphens a human reader never sees.

### Verify a claim in thirty seconds

1. The entry names the document and the page — `13_TrajectoryPlanning`, `p. 29` — and the exact string it quotes.
2. `corpus/_fetch_log.json` records where that document came from, its HTTP status and its byte size.
3. Fetch the document from the course page and search that page for the string. It is there verbatim, or the entry would not exist.

That check needs the corpus, which this repository does not ship. [`corpus/README.md`](corpus/README.md) records how it is rebuilt. Removing the redistributed pages was deliberate: the source documents belong to the course, and the point of a citation is that it is checkable at the source rather than at a copy someone re-uploaded.

---

## Example interactions

### 1. A normal question — retrieval, not generation

```
$ python -m atlas.cli ask "Why do students get DH frame signs wrong?"

3 match(es) in the atlas, ranked by marks at risk:

## Sign gauge pre-empted — DH frame assignment  [FM-DT-01-dh_frames]
   marks at risk 2.9/30 per affected exam · 16 questions · 15 exams · documented · confidence 0.95
   trigger : The task constrains the sign of the DH parameters before the student starts.
   what goes wrong: Assigns z-axes in the opposite direction, so d or a come out negative,
                    then flips a sign somewhere downstream to compensate.
   why: DH parameters are whatever the diagram shows; the convention is decoration rather
        than a gauge choice you must declare.
   exam evidence: Robotics1_24.02.16 (Exercise 2a, p. 2)
     "Denavit-Hartenberg (D-H) convention, so that all constant D-H parameters are non-negative. …"
   taught in: 09_DirectKinematics (p. 12)
   probe: For this arm, which DH entries can be made nonnegative, and which axis direction
          did you have to reverse to do it?
   correction: Fix the z-axis direction rule first, then read the table off. …
```

`ask` ranks by keyword overlap over the validated entries. It never writes new prose — every line above is a field copied out of `atlas.json`.

### 2. Refusal — no cohort data (exit 0)

```
$ python -m atlas.cli ask "What will students score on question 3?"

REFUSED (NO_COHORT_DATA)

What will students score on question 3?

No cohort data is present in this corpus. The exams contain questions and solutions;
they contain no student responses, no marks distribution and no statistics.
Any predicted score would be invented, so none is given.
```

The pattern is matched *before* retrieval, so a persuasive question cannot argue its way past it. Exit code `0`: refusing is a successful answer, not an error.

### 3. Refusal — no corpus (exit 2)

```
$ python -m atlas.cli ask "Give me the failure modes for this course" --corpus /tmp/empty_course

REFUSED (NO_CORPUS)

No readable course material was found at '/tmp/empty_course'. The atlas is built only
from documents it can cite, so with an empty corpus there is nothing to report.
```

An atlas of guesses is exactly what this project exists to avoid.

### 4. The guardrail, attacked by hand

The viewer's coverage screen has a live grounding panel. Select any entry, delete three words from the quote, press *Check against the page*:

```
NOT FOUND. The build would refuse this quote — it writes REJECTED.txt and no atlas entry.
```

Restore the text and it reports `FOUND on <doc>, <ref>`. This is the same `normalise()` containment test used at build time, running on text the visitor controls.

### 5. Regression that mattered

An early cohort guard included a bare `get` pattern, so the question *"Why do students **get** DH frame signs wrong?"* was refused as a score prediction. The guard now requires an actual score/outcome object. The case is pinned in the test suite:

```python
def test_regression_bare_get_is_not_a_score_request(self):
    self.assertFalse(self.wants("Why do students get DH frame signs wrong?"))
```

---

## Demo script (5 minutes)

| Time | Do | Say |
|---|---|---|
| 0:00 | `./demo.sh` → the quiz opens | "Thirty seconds: three axes, four profiles, no claim about how anyone learns. It is a way in, not a diagnosis." |
| 0:35 | Answer with keys 1–3, then click a card | "The profile opens three entries. This one is DH frames, 3.16 of 30 marks per affected exam — and here is the sentence it rests on." |
| 0:55 | *Open the atlas →* | "27 failure modes. Most are an instruction in a past paper that only makes sense if a specific error is anticipated; two are labelled reconstructed because the link is our inference, not the wording." |
| 1:15 | Click row 1 | "Score 232: 7.74 marks per affected exam, across 30 questions in 18 exams." |
| 1:40 | Open an evidence panel | "Document, page and the exact span. The source PDF is not shipped — the citation is, and `_fetch_log.json` records where to get it." |
| 2:00 | Coverage → the rejection count | "Zero quotes rejected: the build refuses any claim it cannot ground, and `tests/test_atlas.py` proves it by feeding the writer a fabricated quote." |
| 2:30 | Ask → *"What will students score on question 3?"* | "Refused, in the browser, before retrieval. There is no cohort data, and the code knows that before it looks at a single entry." |
| 3:00 | Terminal: `ask … --corpus /tmp/empty_course` | "Refused again — no citable document, no atlas. The empty-corpus path is a build-time one, so it stays in the terminal." |
| 3:30 | Open `atlas/rules.py` | "Two entries are `reconstructed`, not `documented`. Here is the rule that made the inference. Attack the rule, not a hidden leap." |
| 4:20 | `data/REPORT.md` §9 | "Eight random entries re-read by hand. Eight confirmed. One real defect was found and fixed before this draw — and the pre-fix number is still in the report." |

---

## Self-validation

**Sample size: 8 failure modes**, drawn with `spotcheck --sample 8 --seed 11` (reproducible), each checked by opening the cited PDF page and reading the surrounding exercise — not by re-running the substring test.

* **8/8 supported** · error rate **0.0%**
* **6/8 distinct quoted instruments.** Two entries read the same sentence for different tells, so the independent sample is smaller than the mode count. Disclosed in the report rather than hidden.

**A real defect was found and fixed before the published draw.** The first pass (seed 7) sampled an entry citing *"count the motor revolutions needed to cover the entire joint range"* as evidence of joint-limit/workspace error. That is an encoder-sizing question. Rule `DT-13`'s pattern (`joint range`) was too broad, so it gained an explicit veto for encoder/resolution/gear-ratio contexts. That veto rejects 1 clause in the corpus, and the count is published as `clauses_vetoed_by_rule_precision` in `coverage.json`. The pre-fix draw was 7/8.

Verdicts and notes live in [`data/spotcheck_verdicts.json`](data/spotcheck_verdicts.json) and `data/REPORT.md` §9.

---

## Documented vs reconstructed

| Strength | Meaning | Entries |
|---|---|---|
| `documented` | The exam wording itself pre-empts the error. The quote is the evidence. | 25 |
| `reconstructed` | The exam states the task; the link from task to student behaviour is the rule's inference, and is named as such. | 2 |

The atlas never presents the second as the first. Student behaviour is always inference — this corpus contains no student work. What is *documented* is the professor's anticipation of it, and that is what the quotes show.

---

## Coverage — the edges, counted

| | Count |
|---|---|
| Exam papers on disk | 160 (884 pages, 99.4% readable) |
| Lecture decks | 20 (771 pages, 99.4% readable) |
| Exams analysed | 97 |
| Excluded — single-block era (pre-2013, no per-question units) | 27 |
| Excluded — partial sheet / answer key | 34 |
| Excluded — no text layer | 2 |
| Task clauses parsed | 351 (85.2% of estimated total) |
| Concepts mapped to a lecture page | 11/11 |
| Quotes rejected by grounding | 0 |
| Clauses dropped by rule precision | 1 |
| OCR run | none — nothing is claimed from image-only pages |

Only exams that segment into ≥2 exercises are analysable; a single undivided block has no per-question units to rank. Exclusions are categorised and reported rather than silently dropped.

### The marks model

30 marks per exam, split equally across exercises, then across task clauses. `marks_at_risk` is the mean exposure **per exam in which the mode appears**; `marks_per_exam_all` (always smaller) is also published for context.

This split is an **assumption**. Its one documented anchor: 7 midterms state per-exercise points, and they all sum to 30. The split stays modelled and is labelled `basis: "reconstructed"` everywhere it appears.

---

## Models, libraries, custom logic

**Models: none.** There is no LLM call anywhere in the pipeline. Three reasons, all deliberate:

1. **Reproducibility** — the same corpus yields byte-identical output.
2. **No hallucinated quotes** — an LLM asked to cite a page will sometimes cite a page that does not say that.
3. **Auditability** — the intellectual content is 17 readable rules and a counting loop, not a prompt.

**Libraries:** Python standard library only (`re`, `json`, `dataclasses`, `argparse`, `subprocess`, `unittest`). External binaries: `pdftotext` and `pdfinfo` from poppler.

**Custom logic that carries the product:**

* `normalise()` / `flatten()` — whitespace-collapsed, case-folded matching so a quote spanning a PDF line break still verifies.
* Tightest-quote search — a quote must contain the span that made the rule fire, so evidence cannot drift away from the claim.
* `Rule.veto` — precision knob; vetoed clauses are counted, not hidden.
* Preferred-deck routing with per-concept `avoid` terms, and "first taught" page selection.
* Equal-split marks model with explicit `basis`.
* First-class `Refusal` objects returned from code paths that run before retrieval.

**Not used:** `pdfplumber`, `pypdf`, `pymupdf`, any embedding store, any vector database, any hosted model.

---

## Limitations

* **No cohort data.** Nothing here says what students did. It says what the papers are built to catch.
* **Marks are modelled, not measured.** Ranking is exposure under an equal split.
* **Rules are a reading.** 17 tells, each quotable, but another examiner could read the same clause differently. That is why rules are named and separable.
* **Entries are not independent.** One sentence can pre-empt several errors; the evidence screen names the other entries sharing a page.
* **Extraction artefacts.** Inline maths is mangled by PDF extraction (`ℱ`, `𝑅𝐹`, `kq̇k`), so quotes are prose spans and equations are never used as evidence.
* **One course, by design.** No cross-course comparison and no platform.
* **No OCR.** 5 image-only pages per corpus are excluded and counted; nothing is claimed from them.
* **No claim of learning impact.** This is a structural finding with counts, not evidence that using it improves a mark.

---

## Provenance and what this repo does not contain

The atlas is built from the **Robotics 1** lecture decks and past exam papers at Sapienza
University of Rome. Those documents are published by the course for its own students. They are
**third-party material and are not included here**, in any form:

| Not in this repo | Why |
|---|---|
| The 190-PDF corpus (210 MB) | Third-party course material; `corpus/README.md` and `_fetch_log.json` record what it is and where it comes from |
| One-page PDFs of the cited pages | Removed deliberately — re-uploading the source pages is redistribution, not citation |
| Extracted page text | `data/evidence_pages.json` ships empty; the viewer falls back to document + page |
| The trained models or weights | None were used; every inference is a named rule in `atlas/rules.py` |

What remains is the part the team wrote: the pipeline, the 17-rule book, the 27 validated entries,
the quiz and Studio, and 82 tests. Quotes are short spans (a clause or a sentence), attributed to a
document and a page, and used to analyse how the papers are written.

The code is the team's joint work. It carries **no open-source licence**: copyright is held by the
four authors listed above, and a licence is theirs to grant, not mine to add. If you want to reuse
it, ask them.

---

## Repository layout

```
atlas/
  ingest.py     PDF -> pages, with scanned-page detection
  segment.py    pages -> exercises -> clauses, each with a page anchor
  rules.py      17 design-tell rules + 11-concept taxonomy  (the intellectual content)
  evidence.py   structural + grounding validators, Refusal
  build.py      orchestration, marks model, ranking, the write gate
  answer.py     the refusal guard + retrieval, shared by CLI and browser
  quiz.py       study-profile quiz: questions, weights, profiles, caveat
  vark.py       Studio preference quiz: 12 questions, four letters, caveat
  studio.py     PDF/PPTX/DOCX -> one report model -> four presentations
  studio_view.py  the Studio page (quiz inlined as data)
  studio_server.py  local server: upload, analyse, export
  theme.css     Studio design system, served at /theme.css
  report.py     Markdown report, incl. self-validation table
  view.py       self-contained viewer: quiz, atlas, ask, coverage
  cli.py        build / ask / quiz / studio / spotcheck
data/
  atlas.json            27 validated entries
  coverage.json         what was read, excluded, modelled
  evidence_pages.json   empty in this repo; the viewer falls back to document + page
  REPORT.md             human-readable report
  spotcheck_sample.json the reproducible draw
  spotcheck_verdicts.json  manual verdicts with notes
web/index.html          generated viewer (open from disk, or `./demo.sh`)
demo.sh                 serve the repo on localhost and open a browser
studio.sh               one command: the Studio on http://localhost:8788/
data/uploads/           Studio sessions (not committed); delete to clear
index.html              redirect to web/index.html (only needed when served)
tests/test_atlas.py     53 atlas tests, stdlib unittest
tests/test_studio.py    28 Studio tests, fixtures built in the test
corpus/                 not committed; see corpus/README.md
```

## Tests

```bash
python -m unittest discover -s tests -v     # 82 tests (2 skip without the corpus)
```

They cover the parts that must not silently break: normalisation and quote spanning, grounding rejection of a fabricated quote, the write gate producing `REJECTED.txt` and no `atlas.json`, structural validation, page-anchor labels, segmenter heading variants and solution headers, the `DT-13` veto, the cohort-refusal regression, viewer placeholder replacement and `</script>` escaping, parity between the CLI guard and the guard inlined in `web/index.html` (the JSON block is parsed, not grepped), the quiz (payload parity, every answer set scoring in range, all four profiles reachable, recommendations resolving to real entries, and the shipped JavaScript scorer run under node against the Python one), and a check that the published atlas is structurally valid and still in rank order.

`tests/test_studio.py` builds its own PPTX and DOCX fixtures from minimal OOXML zips, so it needs
neither the corpus nor Office. It covers the parsers (slide and heading sections, embedded images,
definition labels, article stripping), the four editions (each distinguishes itself by shape,
carries the same sentences, and prints none twice), determinism of the report model, Markdown and
print output, and the live handler on an ephemeral port: upload, analyse, export, a second file
joining a session, bad answers as 400, oversize uploads refused, unknown sessions as 404 and
`..` in a media path rejected.
