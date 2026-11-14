# AGENTS.md — failure-mode-atlas

One course, one claim: a professor's exams encode what he expects students to get wrong, and some of that leaks into the exam wording. Everything here serves finding those tells and proving them.

## Commands

```bash
python -m atlas.cli build                        # corpus -> data/*.json (gated)
python -m atlas.report                           # -> data/REPORT.md
python -m atlas.view                             # -> web/index.html
python -m atlas.cli ask "<question>"             # retrieval over validated entries
python -m atlas.cli quiz --answers 0120120120    # same scorer as the browser
python -m atlas.cli spotcheck --sample 8 --seed 11
python -m unittest discover -s tests -v          # 53 tests
```

`build` needs poppler (`pdftotext`, `pdfinfo`, `pdfseparate`) and a populated `corpus/` (not committed; see `corpus/README.md`).

## Architecture in one line

`ingest.py` (PDF → pages) → `segment.py` (pages → exercises → clauses, each with a page anchor) → `rules.py` (17 design tells) → `build.py` (aggregate, cross-reference to slides, model marks, rank) → `evidence.py` (validate) → `report.py` / `view.py`. The quiz is a separate side door: `quiz.py` holds its content, `view.py` inlines it, `cli.py` can print it.

## Invariants — do not weaken these

1. **No LLM calls, anywhere.** Analysis is deterministic and rule-based. If a change needs a model, the answer is no.
2. **Both validators or nothing.** `build.write()` refuses to write `atlas.json` if the structural *or* the grounding check reports a problem; it writes `REJECTED.txt` and exits 1. Never make the gate advisory, and never let a build write a shorter atlas instead of failing.
3. **Every entry needs `{doc, ref, quote}`, and the quote must occur verbatim on that page** after `normalise()`. Never add a hand-written entry to `data/atlas.json` — it will be overwritten and it bypasses the gate.
4. **`documented` vs `reconstructed` is load-bearing.** `documented` means the exam wording pre-empts the error. Student behaviour is always inference. If a sentence describes what students *do*, the entry is `reconstructed`.
5. **Marks are modelled.** `marks_at_risk` is an equal split under a 30-point total, labelled `basis: "reconstructed"`. Do not present it as measured, and do not compute descriptors like "average student".
6. **Refusals are code paths, not prompt text.** `NO_COHORT_DATA` and `NO_CORPUS` are checked before retrieval. Adding a pattern to `COHORT_PATTERNS` can false-positive on ordinary questions — the bare `get` case is a pinned regression test.
7. **The quiz is not a learning-style test.** It records self-reported study habits and the profile-to-entry mapping is labelled `reconstructed`. Never add a claim about how someone learns, never predict a mark, and keep the caveat on the result screen. Questions, weights and profiles live only in `quiz.py`; the viewer gets them as data at build time.
8. **Quotes are prose, never equations.** PDF extraction mangles inline maths (`ℱ`, `kq̇k`); a quote that verifies but cannot be read proves nothing.

## Editing rules

`rules.py` is the whole intellectual content. When adding a tell:

* write the `trigger` / `wrong_turn` / `misconception` / `probe` / `correction` as if a judge will attack the rule, because they can;
* prefer a `veto` over a cleverer regex when a pattern fires on the wrong context — and remember vetoed clauses are counted in `coverage.json` (`clauses_vetoed_by_rule_precision`);
* rerun `build` and check that the count of rejected quotes is still 0;
* if the change alters published entries, rerun `spotcheck` with the same seed and re-read the affected pages by hand. The published sample is `--sample 8 --seed 11`; do not change the seed to improve the number.

## Files that are generated

`data/atlas.json`, `data/coverage.json`, `data/evidence_pages.json`, `data/pages/`, `data/REPORT.md`, `web/index.html`, `data/spotcheck_sample.json`. Edit the generator, never the output. `data/spotcheck_verdicts.json` is the one hand-written artefact: it records manual verdicts and must cite the page it was checked against.

## Style

Standard library only. Type hints on public functions. Comments explain *why a choice was made*, not what the line does. British spelling in prose ("normalise", "artefact"). No em dashes in commit messages.
