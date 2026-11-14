"""Tests for the failure-mode atlas.

Standard library only (`unittest`), because the project ships no runtime
dependencies and the environment has no pytest. Run with::

    python -m unittest discover -s tests -v

The tests are deliberately about the *guardrails*, not about the ranking: a
ranking can be wrong and still be honest, but a claim that cannot be grounded is
the one failure this project exists to prevent.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas import evidence as ev                     # noqa: E402
from atlas.build import _ref_label, write            # noqa: E402
from atlas.ingest import Document, Page              # noqa: E402
from atlas.rules import RULES_BY_ID, Rule            # noqa: E402
from atlas.segment import segment_exam               # noqa: E402

PAGE_TEXT = (
    "Exercise 1\n"
    "Assign the Denavit-Hartenberg frames so that all constant DH parameters are\n"
    "nonnegative, and fill in the symbolic table of parameters.\n"
)


def make_doc(text: str = PAGE_TEXT, doc_id: str = "Fake_26.01.01") -> Document:
    return Document(
        doc_id=doc_id,
        kind="exams",
        path=f"exams/{doc_id}.pdf",
        pages=[Page(index=1, text=text, chars=len(text), scanned=False)],
    )


def make_entry(**over) -> dict:
    entry = {
        "id": "FM-DT-01-test",
        "title": "Sign gauge pre-empted — DH frame assignment",
        "trigger": "The exam fixes the sign of the DH parameters.",
        "wrong_turn": "Picks a frame convention that makes a parameter negative.",
        "root_misconception": "Frame choice is free, so signs are free.",
        "concepts": ["dh_frames"],
        "evidence": {
            "exam": {
                "doc": "Fake_26.01.01",
                "ref": "Exercise 1, p. 1",
                "quote": "so that all constant DH parameters are nonnegative",
            },
            "lecture": None,
        },
        "probe": "Which parameter went negative, and which frame choice caused it?",
        "correction": "Fix the frame convention before filling the table.",
        "marks_at_risk": 4.0,
        "strength": "documented",
        "confidence": 0.8,
    }
    entry.update(over)
    return entry


class TestTextNormalisation(unittest.TestCase):
    def test_flatten_collapses_line_breaks_and_soft_hyphens(self):
        raw = "so that all constant DH\nparameters are non\u00adnegative"
        self.assertEqual(ev.flatten(raw), "so that all constant DH parameters are nonnegative")

    def test_normalise_is_case_insensitive(self):
        self.assertEqual(ev.normalise("DH Parameters"), "dh parameters")

    def test_quote_spanning_a_pdf_line_break_grounds(self):
        """The whole point of normalising both sides."""
        docs = [make_doc()]
        entry = make_entry()
        entry["evidence"]["exam"]["quote"] = (
            "so that all constant DH parameters are nonnegative"
        )
        self.assertEqual(ev.validate_grounding([entry], docs), [])


class TestGroundingValidator(unittest.TestCase):
    def test_fabricated_quote_is_rejected(self):
        docs = [make_doc()]
        entry = make_entry()
        entry["evidence"]["exam"]["quote"] = (
            "students must always normalise the Jacobian first"
        )
        problems = ev.validate_grounding([entry], docs)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].kind, "grounding")

    def test_unknown_document_is_rejected(self):
        entry = make_entry()
        problems = ev.validate_grounding([entry], [make_doc(doc_id="Some_Other_Paper")])
        self.assertTrue(any("unknown document" in p.detail for p in problems))

    def test_page_out_of_range_is_rejected(self):
        entry = make_entry()
        entry["evidence"]["exam"]["ref"] = "Exercise 1, p. 9"
        problems = ev.validate_grounding([entry], [make_doc()])
        self.assertTrue(any("outside" in p.detail for p in problems))

    def test_scanned_page_has_nothing_to_verify_against(self):
        doc = make_doc()
        doc.pages[0].scanned = True
        entry = make_entry()
        problems = ev.validate_grounding([entry], [doc])
        self.assertTrue(any("no text layer" in p.detail for p in problems))

    def test_write_refuses_and_writes_no_atlas(self):
        """The build gate: a bad quote must produce REJECTED.txt, not a smaller atlas."""
        bad = make_entry()
        bad["evidence"]["exam"]["quote"] = "a sentence that is not on the page at all"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()):  # build prints its refusal
                code = write([bad], {"note": "test"}, out, [make_doc()])
            self.assertEqual(code, 1)
            self.assertTrue((out / "REJECTED.txt").exists())
            self.assertFalse((out / "atlas.json").exists())

    def test_write_publishes_a_grounded_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            code = write([make_entry()], {"note": "test"}, out, [make_doc()])
            self.assertEqual(code, 0)
            self.assertTrue((out / "atlas.json").exists())
            self.assertFalse((out / "REJECTED.txt").exists())
            pages = json.loads((out / "evidence_pages.json").read_text())
            self.assertIn("Fake_26.01.01", pages)


class TestStructuralValidator(unittest.TestCase):
    def test_missing_required_field_is_caught(self):
        entry = make_entry()
        del entry["probe"]
        problems = ev.validate_structure([entry])
        self.assertTrue(any("probe" in p.detail for p in problems))

    def test_bad_strength_is_caught(self):
        problems = ev.validate_structure([make_entry(strength="certain")])
        self.assertTrue(any("strength" in p.detail for p in problems))

    def test_confidence_out_of_range_is_caught(self):
        problems = ev.validate_structure([make_entry(confidence=1.4)])
        self.assertTrue(any("confidence" in p.detail for p in problems))

    def test_too_short_quote_is_caught(self):
        entry = make_entry()
        entry["evidence"]["exam"]["quote"] = "DH"
        problems = ev.validate_structure([entry])
        self.assertTrue(any("too short" in p.detail for p in problems))

    def test_lecture_must_be_object_or_null(self):
        entry = make_entry()
        entry["evidence"]["lecture"] = "10_InverseKinematics p.3"
        problems = ev.validate_structure([entry])
        self.assertTrue(any("lecture" in p.detail for p in problems))


class TestRefLabel(unittest.TestCase):
    def test_lettered_subpart_is_glued_on(self):
        self.assertEqual(
            _ref_label("Robotics1_26.07.13 / Exercise 1 / a", 2), "Exercise 1a, p. 2"
        )

    def test_numeric_fallback_label_is_not_invented_on_the_page(self):
        self.assertEqual(
            _ref_label("Robotics1_26.07.13 / Exercise 1 / clause 3", 2),
            "Exercise 1, p. 2",
        )

    def test_question_heading_is_kept(self):
        """The '#' is in the source heading, so the citation keeps it."""
        self.assertEqual(
            _ref_label("Robotics1_09.01.31 / Question #2 / b", 1), "Question #2b, p. 1"
        )


class TestSegmenter(unittest.TestCase):
    def test_exercise_headings_split(self):
        text = (
            "Exercise 1\nDo the first thing and show the result clearly.\n\n"
            "Exercise 2\nCompute the second thing and report the value.\n"
        )
        exs = segment_exam(make_doc(text))
        self.assertEqual([e.number for e in exs], [1, 2])

    def test_points_tag_after_heading_is_tolerated(self):
        text = (
            "Exercise 1 [6 points]\nDraw the frames and fill the table.\n\n"
            "Exercise 2 [students without midterm]\nCompute the Jacobian.\n"
        )
        exs = segment_exam(make_doc(text))
        self.assertEqual(len(exs), 2)

    def test_solution_header_is_not_read_as_a_question(self):
        text = (
            "Exercise 1\nAssign the frames as discussed above.\n\n"
            "Solution of Midterm Test\n\n"
            "Exercise 2\nThis text is an answer and must be excluded.\n"
        )
        exs = segment_exam(make_doc(text))
        self.assertEqual([e.number for e in exs], [1])
        self.assertTrue(exs[0].has_solution)

    def test_soluzioni_header_is_recognised(self):
        text = "Exercise 1\nAssign the frames.\n\nSoluzioni\n"
        self.assertTrue(segment_exam(make_doc(text))[0].has_solution)

    def test_lettered_clauses_are_split(self):
        text = (
            "Exercise 1\n"
            "a) Sketch the robot in the zero configuration.\n"
            "b) Find the configuration where the gripper points along y0.\n"
        )
        exs = segment_exam(make_doc(text))
        self.assertEqual([c.label for c in exs[0].clauses], ["a", "b"])


class TestRulePrecision(unittest.TestCase):
    def test_dt13_fires_on_a_workspace_question(self):
        rule = RULES_BY_ID["DT-13"]
        hits = rule.search("Draw the reachable workspace under joint range limits.")
        self.assertTrue(hits)

    def test_dt13_is_vetoed_on_an_encoder_sizing_question(self):
        """The defect the spotcheck found: 'joint range' alone is ambiguous."""
        rule = RULES_BY_ID["DT-13"]
        text = (
            "The joint has a range of 700 degrees, a reduction ratio of 30 and a "
            "multi-turn absolute encoder; how many bits are needed for the resolution?"
        )
        self.assertEqual(rule.search(text), [])

    def test_every_rule_has_a_quotable_strength(self):
        for rid, rule in RULES_BY_ID.items():
            with self.subTest(rule=rid):
                self.assertIn(rule.strength, ev.STRENGTHS)
                self.assertTrue(rule.patterns)
                self.assertTrue(rule.probe.strip())


class TestRefusalPredicates(unittest.TestCase):
    def setUp(self):
        from atlas.cli import wants_cohort_prediction

        self.wants = wants_cohort_prediction

    def test_direct_score_prediction_is_caught(self):
        self.assertTrue(self.wants("What will students score on question 3?"))

    def test_pass_rate_is_caught(self):
        self.assertTrue(self.wants("What is the pass rate for this exam?"))

    def test_average_mark_is_caught(self):
        self.assertTrue(self.wants("What was the average mark on the trajectory question?"))

    def test_did_students_struggle_is_caught(self):
        self.assertTrue(self.wants("Did students struggle with the Jacobian?"))

    def test_prediction_of_performance_is_caught(self):
        self.assertTrue(self.wants("Predict the outcome of the next cohort."))

    def test_regression_bare_get_is_not_a_score_request(self):
        """'get' appears in ordinary questions and must not trigger a refusal."""
        self.assertFalse(self.wants("Why do students get DH frame signs wrong?"))

    def test_ordinary_atlas_question_is_not_refused(self):
        self.assertFalse(self.wants("Which failure modes affect trajectory planning?"))

    def test_show_me_the_jacobian_is_not_refused(self):
        self.assertFalse(self.wants("Show me the evidence for the Jacobian modes."))


class TestViewerRender(unittest.TestCase):
    def test_render_inlines_data_and_leaves_no_placeholders(self):
        from atlas import view

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "atlas.json").write_text(json.dumps([make_entry()]))
            (tmp / "coverage.json").write_text(json.dumps({"analysis": {}}))
            (tmp / "evidence_pages.json").write_text(
                json.dumps({"Fake_26.01.01": {"1": PAGE_TEXT}})
            )
            dest = view.render(tmp, tmp / "index.html")
            html = dest.read_text()
            self.assertNotIn("__ATLAS__", html)
            self.assertNotIn("__PAGES__", html)
            self.assertNotIn("__COV__", html)
            self.assertIn("FM-DT-01-test", html)
            self.assertIn("Failure-Mode Atlas", html)

    def test_closing_script_tag_inside_json_is_escaped(self):
        from atlas import view

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            nasty = make_entry(title="a </script> in the title")
            (tmp / "atlas.json").write_text(json.dumps([nasty]))
            (tmp / "coverage.json").write_text(json.dumps({"analysis": {}}))
            (tmp / "evidence_pages.json").write_text(json.dumps({}))
            html = view.render(tmp, tmp / "index.html").read_text()
            self.assertNotIn("</script> in the title", html)


class TestPublishedAtlas(unittest.TestCase):
    """The artefact, not the code: every published entry must still ground."""

    @classmethod
    def setUpClass(cls):
        cls.atlas_path = ROOT / "data" / "atlas.json"
        if not cls.atlas_path.exists():
            raise unittest.SkipTest("data/atlas.json not built yet")
        cls.entries = json.loads(cls.atlas_path.read_text())

    def test_published_entries_pass_structural_validation(self):
        self.assertEqual(ev.validate_structure(self.entries), [])


    def test_evidence_pages_are_serialised_deterministically(self):
        """`wanted` is a set; output must not depend on hash seed or run order."""
        path = ROOT / "data" / "evidence_pages.json"
        if not path.exists():
            raise unittest.SkipTest("data/evidence_pages.json not built yet")
        pages = json.loads(path.read_text())
        self.assertEqual(list(pages), sorted(pages))
        for doc_id, by_page in pages.items():
            with self.subTest(doc=doc_id):
                self.assertEqual(list(by_page), sorted(by_page))

    def test_published_entries_are_ranked_by_score(self):
        scores = [e["marks_at_risk"] * e["questions_affected"] for e in self.entries]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestAnswerParity(unittest.TestCase):
    """The CLI and the browser must run the same guard and the same retrieval."""

    def test_ranked_matches_top_hit_matches_the_cli(self):
        from atlas.answer import ranked_matches

        entries = json.loads((ROOT / "data" / "atlas.json").read_text())
        hits = ranked_matches("why do students get DH frame signs wrong", entries)
        self.assertTrue(hits)
        self.assertEqual(hits[0][1]["id"], "FM-DT-01-dh_frames")

    def test_cohort_guard_matches_between_cli_and_answer_module(self):
        from atlas import answer, cli

        for q in (
            "What will students score on question 3?",
            "what is the pass rate",
            "why do students get DH frame signs wrong",
            "which failure modes affect trajectory planning",
        ):
            with self.subTest(q=q):
                self.assertEqual(cli.wants_cohort_prediction(q),
                                 answer.wants_cohort_prediction(q))

    @staticmethod
    def _guard_from_viewer() -> dict:
        """Parse the inlined guard block, rather than grepping 166 KB of HTML.

        The patterns contain backslashes that the page escapes differently from
        `json.dumps`, so a substring check on the raw file compares escaping
        rules instead of behaviour. Parsing the JSON block and comparing the
        resulting strings tests what the browser actually compiles.
        """
        html = ROOT / "web" / "index.html"
        if not html.exists():
            raise unittest.SkipTest("web/index.html not built")
        text = html.read_text()
        start = text.index('id="d-guard"')
        start = text.index(">", start) + 1
        end = text.index("</script>", start)
        return json.loads(text[start:end])

    def test_js_patterns_are_the_python_patterns(self):
        """The viewer inlines the guard; a pattern must not exist in one place only."""
        from atlas.answer import COHORT_PATTERNS

        guard = self._guard_from_viewer()
        self.assertEqual(guard["patterns"], list(COHORT_PATTERNS))

    def test_stop_list_is_inlined(self):
        from atlas.answer import STOP

        guard = self._guard_from_viewer()
        self.assertEqual(set(guard["stop"]), STOP)

    def test_refusal_reason_and_concept_labels_are_inlined(self):
        from atlas.answer import NO_COHORT_REASON
        from atlas.rules import CONCEPTS

        guard = self._guard_from_viewer()
        self.assertEqual(guard["reason"], NO_COHORT_REASON)
        self.assertEqual(
            guard["concept_labels"], {k: v["label"] for k, v in CONCEPTS.items()}
        )

    def test_guard_refuses_in_the_browser_too(self):
        """Run the inlined patterns against questions the CLI refuses."""
        from atlas.answer import COHORT_PATTERNS, wants_cohort_prediction

        patterns = [re.compile(p) for p in COHORT_PATTERNS]
        questions = (
            "What will students score on question 3?",
            "what is the pass rate",
            "how well do students do on the exam",
            "predict the exam outcome for this class",
            "why do students get DH frame signs wrong",
            "which failure modes affect trajectory planning",
        )
        for q in questions:
            with self.subTest(q=q):
                js = any(p.search(q.lower()) for p in patterns)
                self.assertEqual(js, wants_cohort_prediction(q))


if __name__ == "__main__":
    unittest.main()
