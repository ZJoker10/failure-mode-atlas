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

    def test_published_entries_are_ranked_by_score(self):
        scores = [e["marks_at_risk"] * e["questions_affected"] for e in self.entries]
        self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    unittest.main()
