# Corpus

This directory is **not committed**. It holds 190 PDFs (210 MB) of third-party course material. What is committed instead:

* `data/atlas.json` — every claim, with `{doc, ref, quote}`.
* `data/evidence_pages.json` — the extracted text of each cited page.
* `data/pages/` — the **30 cited pages as one-page PDFs**, so every quote can be checked against the rendered page without this directory.

## What was mirrored

Course: **Robotics 1**, Sapienza University of Rome, Prof. Alessandro De Luca.
Course page recorded in the syllabus itself: `http://www.diag.uniroma1.it/deluca/rob1_en.php`.

| Folder | Files | What it is |
|---|---|---|
| `exams/` | 160 | Past written exams and midterms, 2003–2026, plus their solution sections |
| `slides/` | 20 | The lecture decks the exams are cross-referenced against |
| `syllabus/` | 4 | Programme, exam index (`Syllabus_WrittenExamsRob1.pdf`, 29 pages), reading list |
| `exercises/` | 1 | Problem set used in class |
| `exams_it/` | 1 | One Italian-language paper, kept for the format comparison |

Every filename is listed in [`_fetch_log.json`](_fetch_log.json) with its HTTP status and byte size, and [`_audit.json`](_audit.json) records page counts, per-page character density and whether each file segments into exercises. Those two files are the closest thing to a manifest that exists.

## Re-fetching

The public listing has moved since this mirror was taken: the live course page now points teaching material at Sapienza's Moodle (`https://elearning.uniroma1.it/course/index.php?categoryid=675`), which requires a university login. The material used here came from the course's public file listing in November 2026.

So rather than ship a script that would silently 404, this is what to do:

1. Open `http://www.diag.uniroma1.it/deluca/rob1_en.php` and follow the written-exams and lecture-slides links. If the layout has changed, the [Wayback Machine](https://web.archive.org/web/*/diag.uniroma1.it/deluca/rob1_en.php) snapshots are the fallback.
2. Name the downloads exactly as they appear in `_fetch_log.json` — the pipeline derives document ids from filenames, and every citation in `data/atlas.json` uses those ids.
3. Verify each file ends with `%%EOF`. A truncated PDF still opens and still yields a plausible page count, so this check is not optional: it was the single cause of bad page numbers during the first build.
4. Rebuild and confirm `0 quote(s) rejected by grounding`:

```bash
python -m atlas.cli build
```

If the corpus is a different vintage, the atlas will differ. That is expected and is why every number in the README is tied to this snapshot's `coverage.json`.

## Why it is not committed

* 210 MB of someone else's teaching material, most of it still in use.
* The repository is meant to be readable in a browser, not a mirror.
* Redistribution adds nothing to verifiability: the 30 pages that carry claims are in `data/pages/`, and those are the only pages the atlas ever quotes.

## What was deliberately not used

The workspace also contained machine-generated study material (`Exam_Prep_*.pdf`, `July_2026_Exam_Plan`, `ML_Study_Plan`). It was excluded: those decks were produced by the user's own scripts, and one of them contains a literal "Common Pitfalls" section. Using them would make the atlas a lookup table, and every "evidence" quote would be the corpus citing itself.
