"""Build: corpus -> atlas.json + coverage.json, with the guardrail as a gate.

Flow
----
    load corpus  ->  segment exams  ->  index slides
        ->  for each task clause: fire rules + detect concepts
        ->  aggregate (rule x concept) into one failure mode
        ->  pick an exemplar quote that survives the grounding check
        ->  attach the matching lecture page, or record that none exists
        ->  rank by marks exposed per exam
        ->  validate. if ANY problem, do not write atlas.json.

The last step is the whole point. A build that fails validation produces a
report of why, not a product with a caveat in the README.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from . import evidence as ev
from .ingest import Document, coverage as ingest_coverage, load_corpus
from .rules import CONCEPTS, PREFERRED_DECK, RULES, RULES_BY_ID, Rule, concepts_in, rules_in
from .segment import Clause, Exercise, segment_exam

# Sapienza marks exams out of 30. Seven midterms in the corpus state per-exercise
# points explicitly and all of them sum to 30, which corroborates the total. None
# of the ordinary written exams state a split, so the split below is modelled and
# labelled `reconstructed` everywhere it is shown.
EXAM_TOTAL_MARKS = 30.0

# A usable evidence quote is prose a human can read off the page. PDF extraction
# of matrices and vector diagrams produces spans like "T – Find, if possible,
# a non-zero generalized Cartesian force F c = f T mT ∈ R6", which verify as
# substrings but prove nothing. These thresholds are the filter that keeps such
# fragments out of the atlas.
def looks_like_prose(s: str) -> bool:
    words = s.split()
    if len(words) < 6:
        return False
    letters = sum(c.isalpha() or c in " .,;:'’" for c in s)
    if letters / max(len(s), 1) < 0.80:
        return False
    if "…" in s or "\\" in s:
        return False
    # long runs of single-character "words" are column artefacts
    short = sum(1 for w in words if len(w) <= 1)
    if short / len(words) > 0.28:
        return False
    return True



# ------------------------------------------------------------------ anchoring

def reanchor(doc: Document, clause: Clause) -> int:
    """Find the page a clause actually starts on.

    Segmenting joins wrapped lines, which shifts offsets, so the page recorded
    during segmentation is a guess. Evidence is only as good as this anchor, so
    it is re-derived by matching the clause head against each page.
    """
    key = ev.normalise(clause.text)[:90]
    if not key:
        return clause.page
    for p in doc.pages:
        if p.scanned:
            continue
        if key in ev.normalise(p.text):
            return p.index
    return clause.page


def sentence_around(text: str, span: str) -> str:
    """Quote the trigger in context, verbatim.

    The quote is centred on the span that fired the rule rather than on the
    sentence, because extraction frequently loses the punctuation that separates
    a task clause from a spec table, and a sentence-wide grab then quotes "Max
    payload 1 kg ..." as if it were part of the instruction. A tight window around
    the trigger is what an examiner actually wants to read.
    """
    i = text.find(span)
    if i < 0:
        return span
    before = text[:i].split()
    after = text[i:].split()
    window = " ".join(before[-10:] + after[:26])
    if len(window) >= 70 and ev.normalise(span) in ev.normalise(window):
        quote = window
    else:
        starts = [0] + [m.end() for m in re.finditer(r"[.;:]\s+", text[:i])]
        sent_start = starts[-1] if starts else 0
        m = re.search(r"[.;:]\s", text[i + len(span):])
        sent_end = i + len(span) + (m.start() + 1 if m else len(text) - i - len(span))
        quote = text[sent_start:sent_end].strip()

    quote = trim_leading_noise(quote, span)
    return quote if len(quote) >= ev.MIN_QUOTE_CHARS else span


def trim_leading_noise(quote: str, span: str) -> str:
    """Drop a leading run of equation debris from a quote, keeping the span.

    A sentence boundary inside an extracted matrix often lands mid-formula, so a
    quote can begin "0 l2 c2 l3 c3 Find all (singular) configurations ...". The
    slice below starts at the first token that looks like a word and still
    contains the trigger, so it stays a verbatim substring of the page.
    """
    if ev.normalise(span) not in ev.normalise(quote):
        return quote
    words = quote.split()
    cut = 0
    for n, w in enumerate(words):
        core = w.strip("()[],.;:")
        if len(core) >= 3 and sum(c.isalpha() for c in core) >= 3:
            cut = n
            break
    if cut == 0:
        return quote
    candidate = " ".join(words[cut:])
    return candidate if ev.normalise(span) in ev.normalise(candidate) else quote


# --------------------------------------------------------------- slide index

def kw_hits(text: str, kws: tuple[str, ...]) -> list[str]:
    """Concept keywords present as whole words.

    Substring matching is too loose for short terms: "DH" occurs inside
    "09_Exercise_DH_KukaLWR4.pdf" and inside ordinary words, which is how a
    lecture cross-reference once landed on a lab-exercise filename.
    """
    return [
        k for k in kws
        if re.search(rf"(?<!\w){re.escape(k)}(?!\w)", text, re.I)
    ]


def strip_slide_footer(s: str) -> str:
    """Remove the running footer that extraction appends to slide bodies.

    Only a suffix is removed, so what remains is still a verbatim prefix of the
    page text and continues to ground.
    """
    return re.sub(r"\s+(?:Robotics\s*1|Robotics\s*I)\s+\d{1,3}\s*$", "", s).strip()


class SlideIndex:
    """Concept -> best (doc, page, quote) in the lecture decks.

    Two rules keep this honest:

    * the search is narrowed to the deck that *owns* the concept
      (`PREFERRED_DECK`), so a trajectory claim cannot land on the course
      overview slide just because that slide repeats the word "trajectory";
    * a page qualifies only if it hits at least two distinct concept keywords,
      which rules out pages that merely mention the topic in passing.
    """

    def __init__(self, slides: list[Document]):
        self.slides = slides
        self._best: dict[str, tuple[int, Document, int, str]] = {}
        by_id = {d.doc_id: d for d in slides}

        for cid, spec in CONCEPTS.items():
            kws = spec["slide_kw"]
            preferred = PREFERRED_DECK.get(cid)
            # Preferred deck first; if it yields nothing, widen rather than report
            # a concept as unmapped when the material exists elsewhere.
            pools = []
            if preferred in by_id:
                pools.append([by_id[preferred]])
            pools.append(slides)

            for pool in pools:
                hit = self._search(pool, kws, preferred, cid)
                if hit:
                    self._best[cid] = hit
                    break

    @staticmethod
    def _search(pool: list[Document], kws: tuple[str, ...], preferred: str | None,
                concept_id: str):
        hits: list[tuple[int, Document, int, str]] = []
        for doc in pool:
            for page in doc.pages:
                if page.scanned:
                    continue
                # Flatten first: slides wrap lines mid-phrase, so "inverse
                # kinematics" only exists after whitespace collapse.
                flat = ev.flatten(page.text)
                low = flat.lower()
                if len(flat) < 200:
                    continue
                # Agenda slides list every topic, so they match every concept.
                # They are navigational, not explanatory.
                labels = ("direct kinematics", "inverse kinematics", "differential "
                          "kinematics", "statics", "trajectory planning",
                          "kinematic control", "actuators")
                if sum(1 for lab in labels if lab in low) >= 4:
                    continue
                matched = kw_hits(flat, kws)
                # Inside the deck that owns the concept, one hit is enough: the
                # deck choice already provides the specificity. The two-hit rule
                # is only needed when falling back to the whole slide set.
                need = 1 if preferred == doc.doc_id else 2
                if len(matched) < need:
                    continue
                score = sum(low.count(k.lower()) for k in matched)
                # A page whose opening line names the concept is the page *about*
                # it, not a page that mentions it in passing.
                if kw_hits(flat[:140], kws):
                    score += 5
                avoid = CONCEPTS[concept_id].get("avoid", ())
                if any(a in low for a in avoid):
                    continue
                quote = SlideIndex._quote_for(flat, kws)
                if not quote:
                    continue
                hits.append((score, doc, page.index, quote))

        if not hits:
            return None
        # Prefer where the topic is first taught: among pages within 10% of the
        # best keyword density, take the earliest. That is what keeps a
        # cross-reference out of "Appendix: Modified DH convention".
        top = max(h[0] for h in hits)
        band = [h for h in hits if h[0] >= 0.9 * top]
        return min(band, key=lambda h: (h[2], -h[0]))

    @staticmethod
    def _quote_for(flat: str, kws: tuple[str, ...]) -> str:
        """A verbatim passage of the slide that names the concept.

        Slides are bullet lists with almost no terminal punctuation, and the
        bullet glyph differs per deck (it extracts as "n", "§", "•", or nothing),
        so the candidate set is built two ways: split on the usual glyphs, then
        take a word window around each keyword hit inside each segment. Both are
        exact substrings of the flattened page, so both ground.

        If no passage survives, the slide title is used: for a cross-reference
        ("where is this taught?") a heading that names the topic is the honest
        answer and is trivially checkable. Extraction garbage -- unicode math
        italics (𝑅𝐹, 𝑞, 𝑘), equation rows, interleaved columns -- is rejected in
        both paths, because a quote a judge cannot read is not evidence.
        """

        def acceptable(s: str, min_words: int) -> bool:
            words = s.split()
            if len(words) < min_words:
                return False
            letters = sum(c.isalpha() or c in " .,;:'’-()" for c in s)
            if letters / len(s) < 0.82:
                return False
            if sum(1 for c in s if ord(c) > 0x2000) / len(s) > 0.01:
                return False
            if "!!!" in s or "…" in s or "&&" in s:
                return False
            # Resource/reference slides ("... a popular 3-minute illustration ...
            # https://www.youtube.com/...") are pointers, not teaching pages.
            if "..." in s or "http" in s.lower() or "www." in s.lower():
                return False
            if sum(1 for w in words if len(w.strip(".,;:()[]")) <= 2) / len(words) > 0.30:
                return False
            if s.count("=") >= 2:
                return False
            return True

        segs = [p.strip() for p in re.split(r"\s+n\s+|[•▪◦§→]", flat) if p.strip()]
        cands: list[str] = []
        for seg in segs:
            cands.append(seg)
            words = seg.split()
            low = seg.lower()
            for kw in kw_hits(seg, kws):
                i = low.find(kw.lower())
                if i < 0:
                    continue
                # word index of the hit, then a readable window around it
                wi = len(seg[:i].split())
                # two widths: a full passage, and a tight window for pages whose
                # bullets extract as nothing and leave one giant run of text
                for a, b in ((wi - 6, wi + 34), (wi - 3, wi + 8)):
                    w = words[max(0, a): b]
                    if w:
                        cands.append(" ".join(w))

        best, best_score = "", -1
        for s in cands:
            if not (30 <= len(s) <= 250):
                continue
            if not kw_hits(s, kws):
                continue
            # Five words is enough for a slide heading ("Trajectory planning in
            # joint space"), which is often the best cross-reference on the page.
            if not acceptable(s, 5):
                continue
            # Prefer more distinct concept keywords, then the fuller passage.
            # Prefer passages that open a sentence, then keyword richness, then
            # length: a quote starting mid-clause reads like a fragment.
            opener = 200 if s[:1].isupper() else 0
            score = (
                len(kw_hits(s, kws)) * 1000
                + opener
                + min(len(s), 150)
            )
            if score > best_score:
                best, best_score = s, score
        if best:
            return strip_slide_footer(best)

        for s in segs:
            if 12 <= len(s) <= 120 and kw_hits(s, kws):
                if acceptable(s, 3):
                    return s
        return ""

    def evidence_for(self, concept: str) -> dict | None:
        hit = self._best.get(concept)
        if not hit:
            return None
        _, doc, page, quote = hit
        return {"doc": doc.doc_id, "ref": f"p. {page}", "quote": quote}

    def mapped(self) -> list[str]:
        return sorted(self._best)

    def unmapped(self) -> list[str]:
        return sorted(set(CONCEPTS) - set(self._best))


# ------------------------------------------------------------------- builder

def _slug(rule_id: str, concept: str) -> str:
    return f"FM-{rule_id}-{concept}"


def _ref_label(clause_ref: str, page: int) -> str:
    """'Robotics1_26.07.13 / Exercise 1 / a' -> 'Exercise 1a, p. 2'.

    The page is part of the reference because the grounding check verifies the
    quote against exactly that page, and a reader needs to be able to land on it.
    """
    parts = [p.strip() for p in clause_ref.split(" / ")]
    ex = next((p for p in parts if p.lower().startswith(("exercise", "question"))), "")
    label = parts[-1] if len(parts) >= 3 else ""
    # Only a lettered/roman sub-part is glued on; numeric labels are clause
    # ordinals produced by the fallback splitter, not something on the page.
    if label and len(label) <= 4 and label.isalpha():
        ex = f"{ex}{label}" if ex else label
    return f"{ex or 'exam'}, p. {page}"


def _confidence(strength: str, exams_hit: int, has_lecture: bool) -> float:
    base = 0.62 if strength == "documented" else 0.40
    reach = 0.28 * min(1.0, exams_hit / 8.0)
    lec = 0.08 if has_lecture else 0.0
    return round(min(0.95, base + reach + lec), 2)


def build(corpus_root: Path, out_dir: Path, cache_dir: Path | None = None) -> tuple[list[dict], dict]:
    docs = load_corpus(corpus_root, cache_dir)
    by_id = {d.doc_id: d for d in docs}

    exam_docs = [d for d in docs if d.kind == "exams"]
    slide_docs = [d for d in docs if d.kind == "slides"]
    slide_index = SlideIndex(slide_docs)

    # ---- segment, keeping only exams that actually decompose into questions
    parsed: list[tuple[Document, list[Exercise]]] = []
    excluded_scanned = 0
    excluded_format = 0
    excluded_partial = 0
    for doc in exam_docs:
        readable = doc.n_pages - doc.n_scanned
        if readable == 0:
            excluded_scanned += 1
            continue
        exs = segment_exam(doc)
        if len(exs) < 2:
            # Some files are deliberately partial: an extra sheet, a data sheet,
            # an answer key. They cannot carry per-question marks and are counted
            # apart from papers the segmenter could not read.
            if re.search(r"extra_?sheet|data_?sheet|reply_?sheet|_ws\b|_sheet", doc.doc_id, re.I):
                excluded_partial += 1
            else:
                excluded_format += 1
            continue
        for ex in exs:
            for cl in ex.clauses:
                cl.page = reanchor(doc, cl)
        parsed.append((doc, exs))

    n_exams = len(parsed)
    n_questions = sum(len(exs) for _, exs in parsed)

    # ---- collect hits, keyed by (rule, concept)
    Acc = dict
    buckets: dict[tuple[str, str], Acc] = defaultdict(
        lambda: {"occ": [], "exams": set(), "clauses": 0}
    )
    vetoed_clauses = 0

    for doc, exs in parsed:
        per_exercise_marks = EXAM_TOTAL_MARKS / max(len(exs), 1)
        for ex in exs:
            per_clause_marks = per_exercise_marks / max(len(ex.clauses), 1)
            for cl in ex.clauses:
                fired = rules_in(cl.text)
                if not fired:
                    # Precision accounting: clauses a rule pattern matched but
                    # the rule's veto rejected. Reported, not silently dropped.
                    if any(r.veto and any(v.lower() in cl.text.lower() for v in r.veto)
                           and any(re.search(p, cl.text, re.I) for p in r.patterns)
                           for r in RULES):
                        vetoed_clauses += 1
                    continue
                concepts = concepts_in(cl.text)
                for rule, span in fired:
                    # Attach to the rule's own concept first. Falling back to
                    # whatever concept the clause happens to mention would file a
                    # workspace question under "statics" just because the word
                    # appeared, so the fallback is the rule's primary concept.
                    targets = [c for c in rule.concepts if c in concepts] or [rule.concepts[0]]
                    for cid in targets:
                        b = buckets[(rule.id, cid)]
                        b["exams"].add(doc.doc_id)
                        b["clauses"] += 1
                        b["occ"].append(
                            {
                                "exam": doc.doc_id,
                                "page": cl.page,
                                "ref": cl.ref,
                                "span": span,
                                "quote": sentence_around(cl.text, span),
                                "marks": per_clause_marks,
                            }
                        )

    # ---- assemble entries
    entries: list[dict] = []
    rejected_grounding = 0
    rejected_short = 0
    rejected_no_span = 0

    for (rule_id, cid), b in buckets.items():
        rule = RULES_BY_ID[rule_id]

        # The exemplar is not the longest quote, it is the longest quote that
        # CONTAINS the span which fired the rule. Evidence for "minimum time is
        # demanded" has to show the words "minimum time", or it is not evidence.
        def shows_trigger(o: dict) -> bool:
            q = ev.normalise(o["quote"])
            return bool(o.get("span")) and ev.normalise(o["span"]) in q

        # Two passes: prefer a quote a human can read, then relax to any verbatim
        # span that contains the trigger. Both paths are grounding-checked.
        ranked = sorted(
            b["occ"],
            key=lambda o: (looks_like_prose(o["quote"]), len(o["quote"])),
            reverse=True,
        )
        chosen = None
        for o in ranked:
            if not shows_trigger(o):
                rejected_no_span += 1
                continue
            quote = o["quote"]
            if len(quote) < ev.MIN_QUOTE_CHARS or len(quote.split()) < ev.MIN_QUOTE_WORDS:
                rejected_short += 1
                continue
            doc = by_id[o["exam"]]
            page = doc.pages[o["page"] - 1] if 1 <= o["page"] <= doc.n_pages else None
            if page is None or page.scanned:
                rejected_grounding += 1
                continue
            if ev.normalise(quote) in ev.normalise(page.text):
                chosen = o
                break
            rejected_grounding += 1

        if chosen is None:
            continue  # cannot cite it -> does not ship

        lecture = slide_index.evidence_for(cid)
        # Marks model: mean marks exposed per exam IN WHICH THE MODE APPEARS.
        # This answers "how much of a paper is at stake when this shows up",
        # which is the actionable number for a professor, and it does not
        # dilute a frequent mode across exams that never test it.
        marks_here = sum(o["marks"] for o in b["occ"])
        marks_at_risk = round(marks_here / max(len(b["exams"]), 1), 2)
        marks_per_exam_all = round(marks_here / max(n_exams, 1), 2)

        entries.append(
            {
                "id": _slug(rule_id, cid),
                "title": f"{rule.name} — {CONCEPTS[cid]['label']}",
                "rule_id": rule_id,
                "trigger": rule.trigger,
                "wrong_turn": rule.wrong_turn,
                "root_misconception": rule.misconception,
                "concepts": [cid],
                "evidence": {
                    "exam": {
                        "doc": chosen["exam"],
                        "ref": _ref_label(chosen["ref"], chosen["page"]),
                        "quote": chosen["quote"],
                    },
                    "lecture": lecture,
                },
                "probe": rule.probe,
                "correction": rule.correction,
                "marks_at_risk": marks_at_risk,
                "strength": rule.strength,
                "confidence": _confidence(rule.strength, len(b["exams"]), lecture is not None),
                # --- extras, beyond the required contract
                "questions_affected": len(b["occ"]),
                "exams_affected": len(b["exams"]),
                "marks_per_exam_all": marks_per_exam_all,
                "occurrences": [
                    {"doc": o["exam"], "ref": o["ref"], "page": o["page"], "quote": o["quote"]}
                    for o in sorted(b["occ"], key=lambda o: len(o["quote"]), reverse=True)[:4]
                ],
            }
        )

    # Rank by marks at risk, then by how many questions carry the mode. A mode
    # seen in one exam only is still listed, but flagged, because one sighting
    # cannot distinguish a design tell from a coincidence.
    for e in entries:
        e["thin_evidence"] = e["exams_affected"] < 3
    entries.sort(
        key=lambda e: (e["marks_at_risk"] * e["questions_affected"], e["marks_at_risk"]),
        reverse=True,
    )

    # ---- coverage, including the analysis's own resolution
    cov = ingest_coverage(docs)
    uncovered_pages = sum(1 for d in parsed for p in d[0].pages if p.scanned)
    cov["analysis"] = {
        "exams_total": len(exam_docs),
        "exams_analysed": n_exams,
        "exams_excluded_scanned": excluded_scanned,
        "exams_excluded_single_block_era": excluded_format,
        "exams_excluded_partial_sheet": excluded_partial,
        "questions_parsed": n_questions,
        "questions_total_estimate": n_questions + excluded_format + excluded_partial,
        "pct_questions_parsed": round(
            100 * n_questions / max(n_questions + excluded_format + excluded_partial, 1), 1
        ),
        "scanned_pages_inside_analysed_exams": uncovered_pages,
        "failure_modes_emitted": len(entries),
        "rejected_by_grounding": rejected_grounding,
        "rejected_quote_too_short": rejected_short,
        "rejected_quote_missing_trigger_span": rejected_no_span,
        "clauses_vetoed_by_rule_precision": vetoed_clauses,
        "concepts_mapped": slide_index.mapped(),
        "concepts_unmapped": slide_index.unmapped(),
        "marks_model": {
            "exam_total": EXAM_TOTAL_MARKS,
            "basis": "reconstructed",
            "defines": {
                "marks_at_risk": (
                    "Mean marks exposed per exam in which this mode appears "
                    "(equal split across exercises, then across task clauses)."
                ),
                "marks_per_exam_all": (
                    "Mean marks exposed per analysed exam, including exams that do not "
                    "test this mode. Always smaller; shown for context only."
                ),
            },
            "note": (
                "No document in this corpus states per-exercise points. The split is an "
                "assumption, so marks_at_risk is 'marks exposed under an equal split', "
                "not a measured quantity."
            ),
        },
    }
    return entries, cov


def export_pages(entries: list[dict], docs: list[Document],
                 corpus_root: Path, dest: Path) -> int:
    """Copy each cited page out of its source PDF as a one-page file.

    The corpus is third-party course material and is not redistributed with the
    project. A judge should still be able to open the page a quote comes from,
    so the cited pages -- and only those -- are exported: same file, same page
    number, nothing else. The rendered page is the strongest possible check on a
    quote, because it does not depend on the text layer at all.
    """
    dest.mkdir(parents=True, exist_ok=True)
    by_id = {d.doc_id: d for d in docs}
    wanted: set[tuple[str, int]] = set()
    for e in entries:
        for slot in ("exam", "lecture"):
            blk = e["evidence"].get(slot)
            if not blk:
                continue
            m = re.search(r"(\d+)\s*$", blk["ref"])
            if m:
                wanted.add((blk["doc"], int(m.group(1))))

    made = 0
    for doc_id, page in sorted(wanted):
        d = by_id.get(doc_id)
        if d is None or not (1 <= page <= d.n_pages):
            continue
        out = dest / f"{doc_id}_p{page}.pdf"
        if out.exists() and out.stat().st_size > 0:
            made += 1
            continue
        r = subprocess.run(
            ["pdfseparate", "-f", str(page), "-l", str(page),
             str(corpus_root / d.path), str(out)],
            capture_output=True,
        )
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            made += 1
    return made


def write(entries: list[dict], cov: dict, out_dir: Path, docs: list[Document]) -> int:
    """Validate, then write. Returns the process exit code."""
    problems = ev.validate(entries, docs)
    out_dir.mkdir(parents=True, exist_ok=True)

    if problems:
        (out_dir / "REJECTED.txt").write_text(
            "Build refused. These claims could not be supported:\n\n"
            + "\n".join(str(p) for p in problems[:200])
            + f"\n\n{len(problems)} problem(s). atlas.json was NOT written.\n"
        )
        print(f"BUILD REFUSED — {len(problems)} problem(s). See data/REJECTED.txt")
        return 1

    (out_dir / "atlas.json").write_text(json.dumps(entries, indent=1, ensure_ascii=False))
    (out_dir / "coverage.json").write_text(json.dumps(cov, indent=1, ensure_ascii=False))

    # only the cited pages, for the evidence viewer
    pages: dict[str, dict[str, str]] = {}
    wanted = set()
    for e in entries:
        for slot in ("exam", "lecture"):
            blk = e["evidence"].get(slot)
            if blk:
                m = re.search(r"(\d+)\s*$", blk["ref"])
                if m:
                    wanted.add((blk["doc"], int(m.group(1))))
    by_id = {d.doc_id: d for d in docs}
    for doc_id, page_no in wanted:
        d = by_id.get(doc_id)
        if d and 1 <= page_no <= d.n_pages:
            pages.setdefault(doc_id, {})[str(page_no)] = d.pages[page_no - 1].text
    (out_dir / "evidence_pages.json").write_text(json.dumps(pages, ensure_ascii=False))
    return 0
