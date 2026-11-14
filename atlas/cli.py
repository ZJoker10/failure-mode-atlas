"""CLI: build, ask, quiz, spotcheck, report.

The two refusal demos live here as real code paths, not as prompt text:

    ask "What will students score on question 3?"   -> NO_COHORT_DATA
    ask "..." --corpus /tmp/empty                   -> NO_CORPUS

Both are checked before any retrieval happens, so the refusal cannot be talked
out of by a persuasive question.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

from . import build as builder
from . import evidence as ev
from .ingest import load_corpus
from .answer import (
    NO_COHORT_REASON,
    STOP,
    ranked_matches,
    score_entry,
    terms_of,
    wants_cohort_prediction,
)
from .rules import CONCEPTS, RULES_BY_ID, Rule

DATA = Path("data")

# --------------------------------------------------------------- refusals

def corpus_is_empty(path: Path) -> tuple[bool, str]:
    """True when there is nothing citable at `path`."""
    if not path.exists():
        return True, f"path does not exist: {path}"
    pdfs = sorted(path.rglob("*.pdf"))
    if not pdfs:
        return True, f"no PDF files anywhere under {path}"
    readable = 0
    for p in pdfs[:50]:
        doc = ev_read_head(p)
        if doc.strip():
            readable += 1
    if readable == 0:
        return True, f"{len(pdfs)} PDF(s) under {path} but none has a text layer"
    return False, ""


def ev_read_head(p: Path) -> str:
    import subprocess

    r = subprocess.run(
        ["pdftotext", "-l", "1", str(p), "-"], capture_output=True, text=True, errors="replace"
    )
    return r.stdout


# --------------------------------------------------------------- retrieval

def ask(question: str, entries: list[dict], k: int = 3) -> str:
    """Deterministic retrieval. No generation, so nothing can be invented."""
    hits = ranked_matches(question, entries, k)
    if not hits:
        return (
            "No failure mode in the atlas matches that question.\n"
            f"Concept coverage is: {', '.join(sorted(CONCEPTS))}.\n"
            "Rather than stretch an entry to fit, the atlas reports no match."
        )

    out = [f"{len(hits)} match(es) in the atlas, ranked by marks at risk:\n"]
    for s, e in hits:
        ex = e["evidence"]["exam"]
        lec = e["evidence"].get("lecture")
        out.append(f"## {e['title']}  [{e['id']}]")
        out.append(
            f"   marks at risk {e['marks_at_risk']}/30 per affected exam · "
            f"{e['questions_affected']} questions · {e['exams_affected']} exams · "
            f"{e['strength']} · confidence {e['confidence']}"
        )
        out.append(f"   trigger : {e['trigger']}")
        out.append(f"   what goes wrong: {e['wrong_turn']}")
        out.append(f"   why: {e['root_misconception']}")
        out.append(f"   exam evidence: {ex['doc']} ({ex['ref']})")
        out.append(f"     \"{ex['quote']}\"")
        if lec:
            out.append(f"   taught in: {lec['doc']} ({lec['ref']})")
            out.append(f"     \"{lec['quote']}\"")
        else:
            out.append("   taught in: no lecture page found for this concept inside the corpus")
        out.append(f"   probe: {e['probe']}")
        out.append(f"   correction: {e['correction']}")
        out.append("")
    out.append(
        "Every quote above is verified to occur verbatim on the cited page by the build's "
        "grounding check. Marks are an equal-split model, not a measured quantity."
    )
    return "\n".join(out)


# ----------------------------------------------------------------- commands

def cmd_build(args) -> int:
    corpus = Path(args.corpus)
    empty, why = corpus_is_empty(corpus)
    if empty:
        print(ev.refuse_no_corpus("build the atlas", str(corpus)).as_dict()["reason"])
        return 2

    docs = load_corpus(corpus, Path(args.cache))
    entries, cov = builder.build(corpus, Path(args.out), Path(args.cache))
    code = builder.write(entries, cov, Path(args.out), docs)
    if code == 0:
        n_pages = builder.export_pages(entries, docs, corpus, Path(args.out, "pages"))
        a = cov["analysis"]
        print(f"exported {n_pages} cited page(s) to {Path(args.out, 'pages')}")
        print(
            f"wrote {Path(args.out, 'atlas.json')}: {len(entries)} failure modes, "
            f"{a['exams_analysed']}/{a['exams_total']} exams analysed, "
            f"{a['questions_parsed']} questions parsed, "
            f"{a['rejected_by_grounding']} quote(s) rejected by grounding."
        )
    return code


def cmd_ask(args) -> int:
    corpus = Path(args.corpus)
    if corpus_is_empty(corpus)[0]:
        r = ev.refuse_no_corpus(args.question, str(corpus))
        print(json.dumps(r.as_dict(), indent=1) if args.json else
              f"REFUSED ({r.code})\n\n{r.question}\n\n{r.reason}")
        return 2

    if wants_cohort_prediction(args.question):
        r = ev.refuse_no_cohort(args.question)
        print(json.dumps(r.as_dict(), indent=1) if args.json else
              f"REFUSED ({r.code})\n\n{r.question}\n\n{r.reason}")
        return 0

    path = Path(args.out, "atlas.json")
    if not path.exists():
        print(f"No atlas at {path}. Run: python -m atlas.cli build")
        return 2
    entries = json.loads(path.read_text())
    text = ask(args.question, entries, args.k)
    print(json.dumps({"refused": False, "answer": text}, indent=1) if args.json else text)
    return 0


def cmd_quiz(args) -> int:
    """Print a study profile without a browser. Deterministic: same answers, same output."""
    from . import quiz

    atlas_path = Path(args.out) / "atlas.json"
    if not atlas_path.exists():
        print("data/atlas.json is missing. Run `python -m atlas.cli build` first.")
        return 2
    entries = json.loads(atlas_path.read_text())

    if args.answers:
        answers = quiz.decode(args.answers)
        if answers is None:
            print(f"--answers must be {len(quiz.QUESTIONS)} digits, each 0-2.")
            return 2
    else:
        picked = []
        for i, q in enumerate(quiz.QUESTIONS, 1):
            print(f"\n{i}. {q['stem']}")
            for j, o in enumerate(q["options"], 1):
                print(f"   {j}) {o['label']}")
            while True:
                raw = input("   > ").strip()
                if raw in ("1", "2", "3"):
                    picked.append(int(raw) - 1)
                    break
                print("   Type 1, 2 or 3.")
        answers = tuple(picked)

    r = quiz.result(answers, entries)
    if args.json:
        print(json.dumps(r, indent=1, ensure_ascii=False))
        return 0

    print(f"\n{r['name']}  [{r['profile']}]")
    print(f"{r['quadrant']}" + ("  (no strong preference on either axis)" if r["no_strong_preference"] else ""))
    print()
    for a in r["axes"]:
        if a["neutral"]:
            verdict = "no strong preference"
        else:
            side = a["positive"] if a["value"] >= 0 else a["negative"]
            verdict = ("strong " if abs(a["value"]) >= 0.5 else "lean ") + side
        print(f"  {a['label']:<32} {verdict}")
    print(f"\n{r['blurb']}")
    print(f"\nWatch: {r['watch']}")
    print(f"\nWarm-up: {r['warmup_note']}")
    print("\nStart here:")
    for rec in r["recommendations"]:
        print(f"  - {rec['title']}  [{rec['id']}]")
        print(f"    {rec['why']}")
    print(f"\nMapping strength: {r['mapping_strength']}. {quiz.DISCLAIMER}")
    print(f"\nShareable: #/quiz/{r['answers']}")
    return 0


def cmd_spotcheck(args) -> int:
    """Draw a random sample and print everything needed to check it by hand.

    The point is not the tool's confidence, it is that a human can open the cited
    PDF page and confirm or deny the claim in under a minute.
    """
    path = Path(args.out, "atlas.json")
    entries = json.loads(path.read_text())
    rng = random.Random(args.seed)
    sample = rng.sample(entries, min(args.sample, len(entries)))
    docs = {d.doc_id: d for d in load_corpus(Path(args.corpus), Path(args.cache))}

    rows = []
    for e in sample:
        for slot in ("exam", "lecture"):
            blk = e["evidence"].get(slot)
            if not blk:
                continue
            pg = int(re.search(r"(\d+)\s*$", blk["ref"]).group(1))
            page = docs[blk["doc"]].pages[pg - 1]
            verified = ev.normalise(blk["quote"]) in ev.normalise(page.text)
            rows.append(
                {
                    "id": e["id"],
                    "slot": slot,
                    "doc": blk["doc"],
                    "ref": blk["ref"],
                    "page": pg,
                    "quote": blk["quote"],
                    "substring_verified": verified,
                }
            )
            if args.verbose:
                print(f"\n=== {e['id']} [{slot}] {blk['doc']} p.{pg}")
                print("   quote:", blk["quote"])
                print("   page has it:", verified)

    out = Path(args.out, "spotcheck_sample.json")
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    ok = sum(1 for r in rows if r["substring_verified"])
    print(f"\nwrote {out} — {len(sample)} modes, {len(rows)} quotes, "
          f"{ok}/{len(rows)} verify as substrings of the cited page.")
    return 0 if ok == len(rows) else 1


def cmd_studio(args) -> int:
    """Serve the Studio page: upload material, get it back in your preference order."""
    from .studio_server import serve

    serve(args.host, args.port, open_browser=not args.no_open)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="atlas", description="Failure-Mode Atlas")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="corpus -> data/atlas.json")
    b.add_argument("--corpus", default="corpus")
    b.add_argument("--out", default="data")
    b.add_argument("--cache", default=".cache")
    b.set_defaults(func=cmd_build)

    a = sub.add_parser("ask", help="ask the atlas a question")
    a.add_argument("question")
    a.add_argument("--corpus", default="corpus")
    a.add_argument("--out", default="data")
    a.add_argument("--cache", default=".cache")
    a.add_argument("-k", type=int, default=3)
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_ask)

    q = sub.add_parser("quiz", help="study-profile quiz, without a browser")
    q.add_argument("--answers", default="", help="e.g. 0120120120 (one digit per question)")
    q.add_argument("--out", default="data")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_quiz)

    st = sub.add_parser("studio", help="local Studio page: upload material, get a report")
    st.add_argument("--host", default="127.0.0.1")
    st.add_argument("--port", type=int, default=8788)
    st.add_argument("--no-open", action="store_true", help="do not open a browser")
    st.set_defaults(func=cmd_studio)

    s = sub.add_parser("spotcheck", help="draw a random sample for manual verification")
    s.add_argument("--corpus", default="corpus")
    s.add_argument("--out", default="data")
    s.add_argument("--cache", default=".cache")
    s.add_argument("--sample", type=int, default=8)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(func=cmd_spotcheck)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
