"""Studio: upload material, pick a preference, get the same facts in four shapes.

The pipeline is deliberately dumb, and that is the feature:

    PDF / PPTX / DOCX  ->  text + figures + page refs
                       ->  sections, key sentences, definitions, terms
                       ->  one report model
                       ->  four presentations (V, A, R, K)

No model runs here. Every sentence a report shows is copied from the upload,
and every claim about the material carries the page or slide it came from. What
changes between a visual and an aural report is *order and emphasis* — figures
first versus a spoken script first — never the facts.

Anything that cannot be extracted is reported as missing rather than filled in:
a scanned PDF is flagged, a slide deck with no images says so, and the concept
map is labelled as generated from term co-occurrence rather than as something
the material itself contains.
"""

from __future__ import annotations

import hashlib
import html
import re
import shutil
import subprocess
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from . import vark

WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'\-]{3,}")
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý(])")
DEF = re.compile(
    r"^(?P<term>[A-Z][A-Za-zÀ-ÿ\-]*(?:\s+[A-Za-zÀ-ÿ\-]+){0,3})\s+"
    r"(?:is|are|refers to|means|denotes)\s+(?P<body>.{15,})$"
)

# Slides and handouts often define by label rather than by sentence: "Jacobian:
# the matrix that maps joint rates to end-effector velocity". Kept separate so
# the prose rule above stays strict.
DEF_LABEL = re.compile(
    r"^(?P<term>[A-Z][A-Za-zÀ-ÿ\-]*(?:\s+[A-Za-zÀ-ÿ\-]+){0,2})\s*[:\u2014\u2013-]\s+"
    r"(?P<body>[A-Za-zÀ-ÿ].{18,})$"
)

STOP = set(
    """a an the and or but if then than that this these those there their they them it its is are was
    were be been being am do does did doing done have has had having to of in on at by for with from
    as into over under about between through during before after above below up down out off again
    further once here when where why how all any both each few more most other some such only own same
    so too very can will just should now not no nor you your yours we our ours he she his her hers
    which who whom whose what while because also may might must shall would could onto upon within
    without across per via etc using used use one two three four five six seven eight nine ten
    il lo la i gli le un uno una di da in con su per tra fra che chi cui non più come dove quando
    questo questa questi queste quello quella sono essere stato stata stati state del della dei delle
    al alla ai alle dal dalla nel nella sul sulla è e o ma se anche molto poco così quindi però""".split()
)


# --------------------------------------------------------------------- parse


def _run(cmd: list[str], timeout: int = 120) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout if r.returncode == 0 else ""


def clean(text: str) -> str:
    """Drop bullets, page numbers and mangled maths; keep prose."""
    s = (text or "").replace("\u00a0", " ").replace("\u00ad", "").strip()
    s = re.sub(r"\s+", " ", s)
    if len(s) < 3:
        return ""
    if not re.search(r"[A-Za-zÀ-ÿ]{2,}", s):
        return ""
    weird = sum(1 for ch in s if ord(ch) > 0x2000)
    if weird / len(s) > 0.15:
        return ""
    return s


def lines_of(raw: str) -> list[str]:
    out, seen = [], set()
    for line in raw.splitlines():
        c = clean(line)
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


# Glyphs a slide uses as separators, and the dots a running header leaves behind.
# A run of text containing them is a list of fragments, not a sentence.
DEBRIS = re.compile(r"[\u00a7\u2022\u25aa\u2023\u25e6]|\.{3,}")


def sentences(text: str) -> list[str]:
    """Sentence-like spans only.

    A slide page has no punctuation between its bullets, so joining the page
    turns the whole slide into one long "sentence" full of section glyphs. Those
    read as noise in a report, and the atlas rule applies here too: an extract
    that cannot be read proves nothing. So a candidate must look like prose,
    which for our purposes means at least one sentence-ending mark and none of
    the separators a slide uses.
    """
    out = []
    for part in SENT.split(text):
        s = part.strip()
        if not 30 <= len(s) <= 340:
            continue
        if len(WORD.findall(s)) < 5:
            continue
        if DEBRIS.search(s) or not re.search(r"[.!?]", s):
            continue
        # Symbols outnumbering words means the line came from an equation, not a
        # sentence. Printing it would put mangled maths in a study report, which
        # is the one thing the atlas bans outright.
        if sum(1 for c in s if c.isalpha()) / len(s) < 0.65:
            continue
        # "in time (< (6) = 4th order" survives the letter test but is still an
        # equation with words around it. A quarter of the tokens being symbol-only
        # is the line between "mentions a formula" and "is a formula".
        tokens = s.split()
        if sum(1 for t in tokens if not any(c.isalpha() for c in t)) / len(tokens) > 0.25:
            continue
        out.append(s)
    return out


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _render_pdf_page(path: Path, page: int, dest: Path) -> bool:
    _run(
        [
            "pdftoppm",
            "-f", str(page), "-l", str(page),
            "-r", "90", "-png", "-singlefile",
            str(path), str(dest.with_suffix("")),
        ],
        timeout=60,
    )
    return dest.exists()


RUNNING = re.compile(r"^(?:\.{2,}|page \d+|\W*$)", re.I)

# A slide footer ("Robotics 1 38") and a date line are decoration that happens to
# start with a capital. Neither is a section title.
HEADING_NOISE = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9 .&-]*)\s\d{1,3}$"   # course name + page number
    r"|^(?:January|February|March|April|May|June|July|August|September|October"
    r"|November|December)\s\d{1,2},\s\d{4}$"   # a date
)


def _heading(lines: list[str], fallback: str = "") -> str:
    """First line that could be a heading: short, capitalised, not a page artifact.

    A continued sentence ("rotation matrix by an angle ...") starts lowercase and
    makes a misleading title, so it is rejected and the caller's neutral label is
    used instead.
    """
    for line in lines:
        if RUNNING.match(line) or HEADING_NOISE.match(line):
            continue
        if len(line) > 90 or len(line.split()) < 2:
            continue
        if not line[:1].isupper():
            continue
        return line
    return fallback


def _pdf_pages(path: Path) -> tuple[list[tuple[int, str]], int, bool]:
    info = _run(["pdfinfo", str(path)])
    m = re.search(r"^Pages:\s+(\d+)", info, re.M)
    n_pages = int(m.group(1)) if m else 0
    text = _run(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"])
    pages = [(i + 1, p) for i, p in enumerate(text.split("\f")) if p.strip()]
    scanned = not pages
    return pages, n_pages, scanned


def _pdf_figures(path: Path, outdir: Path, pages: list[tuple[int, str]], limit: int) -> list[dict]:
    listing = _run(["pdfimages", "-list", str(path)])
    with_images = set()
    for line in listing.splitlines()[2:]:
        bits = line.split()
        if bits and bits[0].isdigit():
            with_images.add(int(bits[0]))

    sparse = [n for n, t in pages if len(t.strip()) < 420]
    order: list[int] = []
    for n in sorted(with_images) + sparse:
        if n not in order:
            order.append(n)

    figs = []
    for n in order[:limit]:
        dest = outdir / f"fig-{n:03d}.png"
        if _render_pdf_page(path, n, dest):
            figs.append(
                {"file": dest.name, "label": f"page {n}", "section": f"page {n}", "page": n}
            )
    return figs


def parse_pdf(path: Path, outdir: Path) -> dict:
    pages, n_pages, scanned = _pdf_pages(path)
    sections, all_text = [], []
    for number, raw in pages:
        ls = lines_of(raw)
        if not ls:
            continue
        body = " ".join(ls)
        all_text.append(body)
        found = sentences(body)
        if not found:
            continue
        title = _heading(ls, f"Page {number}")
        sections.append(
            {
                "title": title,
                "ref": f"page {number}",
                "sentences": found,
                "page": number,
            }
        )
    figures = _pdf_figures(path, outdir, pages, limit=8)
    return {
        "name": path.name,
        "kind": "pdf",
        "pages": n_pages,
        "scanned": scanned,
        "chars": sum(len(t) for t in all_text),
        "sections": sections,
        "figures": figures,
    }


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def parse_pptx(path: Path, outdir: Path) -> dict:
    sections, figures, chars = [], [], 0
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
        names.sort(key=lambda n: int(re.search(r"(\d+)", n).group(1)))
        for name in names:
            num = int(re.search(r"(\d+)", name).group(1))
            root = ET.fromstring(z.read(name))
            paras = []
            for p in root.iter(f"{A}p"):
                text = "".join(t.text or "" for t in p.iter(f"{A}t")).strip()
                c = clean(text)
                if c:
                    paras.append(c)
            if not paras:
                continue
            body = " ".join(paras[1:] or paras)
            found = sentences(body)
            if not found:
                continue
            title = _heading(paras, f"Slide {num}")
            chars += len(body)
            sections.append(
                {
                    "title": title,
                    "ref": f"slide {num}",
                    "sentences": found,
                    "page": num,
                }
            )
            rel_name = f"ppt/slides/_rels/slide{num}.xml.rels"
            if rel_name in z.namelist():
                rels = ET.fromstring(z.read(rel_name))
                for rel in rels:
                    target = rel.get("Target", "")
                    if "/media/" in target:
                        media = "ppt/" + target.split("ppt/")[-1].lstrip("/")
                        media = media.replace("ppt/../", "ppt/")
                        if media in z.namelist():
                            ext = Path(media).suffix.lower()
                            if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                                out = outdir / f"fig-s{num:03d}-{Path(media).name}"
                                out.write_bytes(z.read(media))
                                figures.append(
                                    {
                                        "file": out.name,
                                        "label": f"slide {num}",
                                        "section": title,
                                        "page": num,
                                    }
                                )
    seen, unique = set(), []
    for f in figures:
        if f["file"] not in seen:
            seen.add(f["file"])
            unique.append(f)
    for i, f in enumerate(unique[:10], 1):
        f["label"] = f"figure {i} · {f['label']}"
    return {
        "name": path.name,
        "kind": "pptx",
        "pages": len(sections),
        "scanned": False,
        "chars": chars,
        "sections": sections,
        "figures": unique[:10],
    }


def parse_docx(path: Path, outdir: Path) -> dict:
    sections, figures, chars = [], [], 0
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))

        def new_section(title: str) -> dict:
            n = len(sections) + 1
            return {"title": title or path.stem, "ref": f"section {n}", "page": n}

        current = new_section(path.stem)
        current["sentences"] = []
        for p in root.iter(f"{W}p"):
            style_el = p.find(f"{W}pPr/{W}pStyle")
            style = (style_el.get(f"{W}val") if style_el is not None else "") or ""
            text = clean("".join(t.text or "" for t in p.iter(f"{W}t")))
            if not text:
                continue
            is_heading = style.lower().startswith(("heading", "title"))
            if is_heading:
                if current["sentences"]:
                    sections.append(current)
                current = new_section(text)
                current["sentences"] = []
                continue
            current["sentences"].extend(sentences(text))
            chars += len(text)
        if current["sentences"]:
            sections.append(current)

        rels_name = "word/_rels/document.xml.rels"
        if rels_name in z.namelist():
            rels = ET.fromstring(z.read(rels_name))
            idx = 0
            for rel in rels:
                target = rel.get("Target", "")
                if "media/" in target:
                    media = "word/" + target.split("word/")[-1].lstrip("/")
                    media = media.replace("word/../", "word/")
                    if media in z.namelist():
                        ext = Path(media).suffix.lower()
                        if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                            idx += 1
                            out = outdir / f"fig-d{idx:03d}{ext}"
                            out.write_bytes(z.read(media))
                            figures.append(
                                {
                                    "file": out.name,
                                    "label": f"figure {idx}",
                                    "section": path.stem,
                                    "page": None,
                                }
                            )
    return {
        "name": path.name,
        "kind": "docx",
        "pages": len(sections),
        "scanned": False,
        "chars": chars,
        "sections": [s for s in sections if s["sentences"]],
        "figures": figures[:10],
    }


def parse(path: Path, outdir: Path) -> dict:
    suffix = path.suffix.lower()
    outdir.mkdir(parents=True, exist_ok=True)
    if suffix == ".pdf":
        doc = parse_pdf(path, outdir)
    elif suffix == ".pptx":
        doc = parse_pptx(path, outdir)
    elif suffix == ".docx":
        doc = parse_docx(path, outdir)
    else:
        raise ValueError(f"unsupported file type: {suffix or path.name}")
    doc["hash"] = _sha(path)
    doc["bytes"] = path.stat().st_size
    return doc


# ------------------------------------------------------------------ analyse


def _terms(texts: list[str], k: int = 14) -> list[list]:
    counts: Counter[str] = Counter()
    for t in texts:
        for w in WORD.findall(t.lower()):
            if len(w) < 5 or w in STOP:
                continue
            counts[w] += 1
    return [[w, n] for w, n in counts.most_common(k) if n >= 2]


def _definitions(sections: list[dict]) -> list[dict]:
    out, seen = [], set()
    for s in sections:
        for sent in s["sentences"]:
            m = DEF.match(sent)
            if not m:
                m = DEF_LABEL.match(sent)
                # a label definition still has to read as a clause, not a slide title
                if not m or len(m.group("body").split()) < 5:
                    continue
            term = re.sub(r"^(?:A|An|The)\s+", "", m.group("term").strip())
            key = term.lower()
            if key in seen or len(key) > 42:
                continue
            if len(m.group("body").split()) < 4:
                continue
            seen.add(key)
            out.append({"term": term, "text": sent, "ref": s["ref"]})
    return out[:24]


def _points(
    section: dict, tf: dict[str, int], k: int = 2, skip: set[str] | None = None
) -> list[str]:
    """The sentences that carry most of this document's own vocabulary.

    `skip` holds sentences already claimed by the definitions block, so a report
    shows any given sentence once rather than twice under two headings.
    """
    skip = skip or set()
    scored = []
    for i, s in enumerate(section["sentences"]):
        if s in skip:
            continue
        words = [w for w in WORD.findall(s.lower()) if w not in STOP]
        if not words:
            continue
        score = sum(tf.get(w, 0) for w in words) / (len(words) ** 0.5)
        scored.append((score, i, s))
    scored.sort(key=lambda t: (-t[0], t[1]))
    picked = sorted(scored[:k], key=lambda t: t[1])
    return [s for _, _, s in picked]


def _concept_map(terms: list[list], texts: list[str]) -> dict:
    names = [t for t, _ in terms[:9]]
    if len(names) < 3:
        return {"nodes": [], "edges": []}
    edges = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            weight = 0
            for t in texts:
                low = t.lower()
                if re.search(rf"\b{re.escape(a)}\b", low) and re.search(rf"\b{re.escape(b)}\b", low):
                    weight += 1
            if weight >= 2:
                edges.append([a, b, weight])
    edges.sort(key=lambda e: (-e[2], e[0], e[1]))
    return {"nodes": [list(n) for n in terms[:9]], "edges": edges[:12]}


def analyse(docs: list[dict], profile: dict) -> dict:
    """One report model for every preference. Presentation happens later."""
    out_docs = []
    all_text: list[str] = []
    for d in docs:
        texts = [s["title"] for s in d["sections"]] + [
            sent for s in d["sections"] for sent in s["sentences"]
        ]
        all_text.extend(texts)
        tf = {t: n for t, n in _terms(texts, k=40)}
        definitions = _definitions(d["sections"])
        claimed = {x["text"] for x in definitions}
        sections = []
        for s in d["sections"]:
            sections.append(
                {
                    "title": s["title"],
                    "ref": s["ref"],
                    "points": _points(s, tf, skip=claimed),
                    "sentences": s["sentences"][:8],
                    "figures": [
                        f
                        for f in d["figures"]
                        if f.get("page") is not None and f.get("page") == s.get("page")
                    ],
                }
            )
        out_docs.append(
            {
                "name": d["name"],
                "kind": d["kind"],
                "pages": d["pages"],
                "scanned": d.get("scanned", False),
                "sections": sections,
                "definitions": definitions,
                "terms": _terms(texts, k=12),
                "figures": d["figures"],
            }
        )

    terms = _terms(all_text, k=12)
    tf_all = {t: n for t, n in _terms(all_text, k=60)}
    flat = [s for d in out_docs for s in d["sections"]]
    used = {p for d in out_docs for s in d["sections"] for p in s["points"]}
    used |= {x["text"] for d in out_docs for x in d["definitions"]}
    overall = []
    for s in flat:
        overall.extend(_points(s, tf_all, k=3, skip=used))
    seen_overall = set()
    overall = [x for x in overall if not (x in seen_overall or seen_overall.add(x))]
    report = {
        "vark": profile,
        "docs": out_docs,
        "terms": terms,
        "concept_map": _concept_map(terms, all_text),
        "overall": overall[:6],
        "totals": {
            "files": len(out_docs),
            "pages": sum(d["pages"] for d in out_docs),
            "sections": len(flat),
            "definitions": sum(len(d["definitions"]) for d in out_docs),
            "figures": sum(len(d["figures"]) for d in out_docs),
        },
        "plan": _plan(out_docs),
    }
    return report


def _plan(docs: list[dict]) -> list[dict]:
    """Kinesthetic tasks derived from what the upload actually contains."""
    steps = []
    for d in docs:
        for definition in d["definitions"][:4]:
            steps.append(
                {
                    "do": f"Cover the sentence defining <b>{html.escape(definition['term'])}</b> "
                          f"and write the definition from memory.",
                    "check": f"{definition['ref']} · “{definition['text']}”",
                }
            )
        for fig in d["figures"][:3]:
            steps.append(
                {
                    "do": f"Redraw the figure from {html.escape(fig['label'])} without looking, "
                          f"then compare.",
                    "check": f"{d['name']} · {fig['label']}",
                }
            )
        for s in d["sections"][:6]:
            if s["points"]:
                steps.append(
                    {
                        "do": f"Close the notes and list the key points of "
                              f"“{html.escape(s['title'])}”.",
                        "check": f"{s['ref']} · {len(s['points'])} point(s) were extracted",
                    }
                )
    return steps[:12]


# ------------------------------------------------------------------- render


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def concept_svg(report: dict, size: int = 460) -> str:
    cm = report.get("concept_map") or {}
    nodes = cm.get("nodes") or []
    edges = cm.get("edges") or []
    if len(nodes) < 3:
        return ""
    import math

    cx = cy = size / 2
    r = size * 0.36
    pos = {}
    for i, (name, _count) in enumerate(nodes):
        ang = -math.pi / 2 + (2 * math.pi * i / len(nodes))
        pos[name] = (cx + r * math.cos(ang), cy + r * math.sin(ang))
    maxw = max((e[2] for e in edges), default=1)
    parts = [f'<svg viewBox="0 0 {size} {size}" class="cmap" role="img" '
             f'aria-label="Concept map generated from term co-occurrence">']
    for a, b, w in edges:
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        op = 0.18 + 0.42 * (w / maxw)
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="#2E6BFF" stroke-width="{1 + 2 * w / maxw:.1f}" opacity="{op:.2f}"/>'
        )
    for name, count in nodes:
        x, y = pos[name]
        rad = 7 + min(9, count)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad}" fill="#6209BA" opacity=".85"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y - rad - 6:.1f}" text-anchor="middle" '
            f'font-size="11.5" font-weight="700" fill="#0C2744">{esc(name)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _meta(report: dict) -> str:
    p = report["vark"]
    t = report["totals"]
    return (
        '<div class="meta">'
        f'<span class="tag doc">{esc(p["label"])}</span>'
        f'<span class="small">{t["files"]} file(s) · {t["pages"]} page/slide · '
        f'{t["sections"]} section(s) · {t["definitions"]} definition(s) · '
        f'{t["figures"]} figure(s)</span>'
        "</div>"
    )


def _figure_grid(figs: list[dict], limit: int = 8, media_base: str = "") -> str:
    if not figs:
        return ""
    return (
        '<div class="figgrid">'
        + "".join(
            f'<figure><img src="{esc(media_base + f["file"])}" alt="{esc(f["label"])}" '
            f'loading="lazy">'
            f'<figcaption>{esc(f["label"])}</figcaption></figure>'
            for f in figs[:limit]
        )
        + "</div>"
    )


def _doc_header(doc: dict) -> str:
    bits = [f'{doc["pages"]} page/slide', f'{len(doc["sections"])} section(s)']
    if doc["definitions"]:
        bits.append(f'{len(doc["definitions"])} definition(s)')
    if doc["figures"]:
        bits.append(f'{len(doc["figures"])} figure(s)')
    return (
        f'<div class="dochead"><h3>{esc(doc["name"])}</h3>'
        f'<span class="small">{esc(" · ".join(bits))}</span></div>'
    )


def _glossary(doc: dict, skip: set[str] | None = None) -> str:
    """Definitions not already shown as a key point; repeating them reads as padding."""
    skip = skip or set()
    shown = [d for d in doc["definitions"] if d["text"] not in skip]
    if not shown:
        return ""
    return (
        '<div class="gloss">'
        + "".join(
            f'<div class="gcard"><div class="eyebrow">{esc(d["ref"])}</div>'
            f'<b>{esc(d["term"])}</b><p>{esc(d["text"])}</p></div>'
            for d in shown
        )
        + "</div>"
    )


def render(report: dict, *, print_mode: bool = False, media_base: str = "") -> str:
    """The report body. Same facts in four orders; the preference picks the order.

    `media_base` is the URL prefix figures are served from; the on-page report
    passes `/media/<sid>/`, the print page passes a `file://` directory.
    """
    kind = report["vark"]["dominant"]
    t = report["totals"]
    # On the page the header bar already states the preference and the counts;
    # repeating them as the first line of the body read as a stutter.
    out = [_meta(report)] if print_mode else []

    if t["files"] == 0:
        return '<div class="panel"><p>Nothing was uploaded, so there is nothing to report.</p></div>'

    if kind == "V":
        out.append(
            '<div class="panel"><div class="eyebrow">Visual edition</div>'
            "<h2>The material as pictures</h2>"
            '<p class="small">Figures are page renders or images lifted from your own files — '
            "nothing is redrawn or invented. The map below is generated from term "
            "co-occurrence; it is a reading aid, not a diagram from the material.</p>"
            + "".join(
                f'<h3 class="soft">{esc(d["name"])}</h3>'
                + _figure_grid(d["figures"], media_base=media_base)
                for d in report["docs"]
            )
            + "</div>"
        )
        svg = concept_svg(report)
        if svg:
            out.append(
                '<div class="panel"><div class="eyebrow">Generated map</div>'
                "<h3>Terms that keep appearing together</h3>" + svg + "</div>"
            )
        for d in report["docs"]:
            body = []
            for s in d["sections"]:
                point = s["points"][0] if s["points"] else ""
                if not point:
                    continue
                body.append(
                    f'<div class="vrow"><span class="ref">{esc(s["ref"])}</span>'
                    f'<div><b>{esc(s["title"])}</b><p>{esc(point)}</p></div></div>'
                )
            if body:
                out.append(
                    '<div class="panel">'
                    + _doc_header(d)
                    + "".join(body)
                    + _glossary(d, {s["points"][0] for s in d["sections"] if s["points"]})
                    + "</div>"
                )

    elif kind == "A":
        script = []
        for d in report["docs"]:
            for s in d["sections"]:
                if not s["points"]:
                    continue
                say = f'{s["title"]}. ' + " ".join(s["points"])
                script.append(
                    f'<div class="say"><div class="eyebrow">{esc(s["ref"])}</div>'
                    f'<p data-say="{esc(say)}">{esc(say)}</p>'
                    + (
                        ""
                        if print_mode
                        else '<button class="btn ghost tiny" onclick="speak(this)">Listen</button>'
                    )
                    + "</div>"
                )
        out.append(
            '<div class="panel"><div class="eyebrow">Aural edition</div>'
            "<h2>A script you can listen to</h2>"
            '<p class="small">Each block is read from the upload, not paraphrased. '
            "The Listen button uses your browser's speech synthesiser; nothing is sent anywhere.</p>"
            + (
                ""
                if print_mode
                else '<p><button class="btn" onclick="speakAll()">Listen to everything</button></p>'
            )
            + "".join(script)
            + "</div>"
        )
        # No transcript panel: the script above already shows every sentence it
        # reads. Repeating it below read as padding and doubled the page count.
        for d in report["docs"]:
            if d["definitions"]:
                out.append(
                    '<div class="panel">' + _doc_header(d) + _glossary(d) + "</div>"
                )

    elif kind == "R":
        out.append(
            '<div class="panel"><div class="eyebrow">Read/write edition</div>'
            "<h2>Outline, with the definitions in place</h2>"
            '<p class="small">Dense on purpose: headings, the sentences that carry the most '
            "of the material's own terms, and every definition found in reading order.</p>"
            "</div>"
        )
        for d in report["docs"]:
            body, printed = [], set()
            for s in d["sections"]:
                if not s["points"]:
                    continue
                printed.update(s["points"])
                body.append(
                    f'<h4>{esc(s["title"])} <span class="ref">({esc(s["ref"])})</span></h4>'
                    + "".join(f"<p>{esc(p)}</p>" for p in s["points"])
                )
            out.append(
                '<div class="panel">' + _doc_header(d)
                + "".join(body)
                + (_glossary(d, printed) if d["definitions"] else "")
                + "</div>"
            )

    else:  # K
        steps = report.get("plan") or []
        out.append(
            '<div class="panel"><div class="eyebrow">Kinesthetic edition</div>'
            "<h2>Do this first</h2>"
            '<p class="small">Tasks are generated from what the upload contains: every definition '
            "and every figure produces one. Each carries the page or slide to check yourself "
            "against.</p>"
            + (
                '<ol class="steps">'
                + "".join(
                    f'<li><label><input type="checkbox"><span>{s["do"]}</span></label>'
                    f'<div class="check">Check: {s["check"]}</div></li>'
                    for s in steps
                )
                + "</ol>"
                if steps
                else "<p>No definitions or figures were found to build tasks from.</p>"
            )
            + "</div>"
        )
        out.append(
            '<div class="panel"><div class="eyebrow">Then read</div>'
            "<h2>The same points, in the order to attempt them</h2>"
            + "".join(
                _doc_header(d)
                + "".join(
                    f'<div class="vrow"><span class="ref">{esc(s["ref"])}</span>'
                    f'<div><b>{esc(s["title"])}</b>'
                    + "".join(f"<p>{esc(p)}</p>" for p in s["points"])
                    + "</div></div>"
                    for s in d["sections"] if s["points"]
                )
                for d in report["docs"]
            )
            + "</div>"
        )

    if report.get("overall"):
        out.append(
            '<div class="panel"><div class="eyebrow">Across the whole upload</div>'
            "<h3>Sentences that carry the most of its own vocabulary</h3>"
            + "".join(f"<p>{esc(s)}</p>" for s in report["overall"])
            + "</div>"
        )

    out.append(
        '<p class="small provenance">Every sentence above is copied verbatim from your upload; '
        "page and slide references are given so it can be checked. Nothing was paraphrased or "
        "generated by a model. The preference changes order and emphasis only.</p>"
    )
    return "".join(out)


def markdown(report: dict) -> str:
    p = report["vark"]
    t = report["totals"]
    lines = [
        f'# Study report — {p["label"]}',
        "",
        f'{t["files"]} file(s) · {t["pages"]} page/slide · {t["sections"]} section(s) · '
        f'{t["definitions"]} definition(s) · {t["figures"]} figure(s)',
        "",
        f'> {vark.CAVEAT}',
        "",
        "Every sentence is copied verbatim from the upload; references are given. "
        "Nothing is paraphrased by a model.",
        "",
    ]
    for d in report["docs"]:
        lines += [f'## {d["name"]}', "", f'*{d["kind"]} · {d["pages"]} page/slide*', ""]
        if d["scanned"]:
            lines += ["> No text layer: this file is image-only, so only figures were extracted.", ""]
        if p["dominant"] == "V" and d["figures"]:
            lines += ["### Figures", ""]
            lines += [f'- `{f["file"]}` — {f["label"]}' for f in d["figures"]]
            lines += [""]
        for s in d["sections"]:
            if not s["points"]:
                continue
            lines += [f'### {s["title"]} ({s["ref"]})', ""]
            lines += [f"- {pt}" for pt in s["points"]]
            lines += [""]
        if d["definitions"]:
            lines += ["### Definitions", ""]
            for x in d["definitions"]:
                lines += [f'**{x["term"]}** — {x["text"]}', f'*{x["ref"]}*', ""]
    if p["dominant"] == "K" and report.get("plan"):
        lines += ["## Do this first", ""]
        for i, step in enumerate(report["plan"], 1):
            check = re.sub(r"<[^>]+>", "", step["check"])
            do = re.sub(r"<[^>]+>", "", step["do"])
            lines += [f'{i}. [ ] {do}', f'   - check: {check}']
        lines += [""]
    return "\n".join(lines).strip() + "\n"


PRINT_CSS = """
@page{size:A4;margin:14mm}
body{font-family:"Plus Jakarta Sans",system-ui,sans-serif;color:#0C2744;margin:0;
  font-size:11pt;line-height:1.5;background:#fff}
h1{font-size:20pt;margin:0 0 4px}
h2{font-size:15pt;margin:0 0 6px}
h3{font-size:12.5pt;margin:14px 0 4px}
h4{font-size:11pt;margin:12px 0 3px}
p{margin:0 0 7px}
/* A panel is a long document section, so it must be allowed to split: keeping
   it whole pushed a tall section to the next page and left the previous one
   almost blank. Small units are the things that stay together. */
.panel{border:1px solid #dfe7ef;border-radius:14px;padding:12px 14px;margin:10px 0;
  break-inside:auto}
.gcard,.say,.vrow,.figgrid figure{break-inside:avoid}
h1,h2,h3,h4{break-after:avoid}
.eyebrow{font-size:8pt;letter-spacing:.09em;text-transform:uppercase;color:#3E5D80;font-weight:700}
.small{font-size:9pt;color:#3E5D80}
.ref{font-size:8.5pt;color:#3E5D80;font-weight:700;white-space:nowrap}
.tag{padding:2px 8px;border-radius:999px;background:#eef4ff;font-size:9pt;font-weight:700}
.meta{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
figure{margin:0;break-inside:avoid}
.figgrid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.figgrid img{width:auto;max-width:100%;max-height:80mm;margin:0 auto;
  border:1px solid #dfe7ef;border-radius:8px}
figcaption{font-size:8.5pt;color:#3E5D80}
.vrow{display:flex;gap:10px;margin:6px 0}
.vrow .ref{min-width:64px}
.gcard{border-left:3px solid #5FEE13;padding-left:10px;margin:8px 0}
.cmap{width:100%;max-width:420px;display:block;margin:6px auto}
.steps{padding-left:18px}
.steps li{margin:8px 0}
.check{font-size:9pt;color:#3E5D80;margin-left:18px}
.provenance{font-size:9pt;color:#3E5D80;border-top:1px solid #dfe7ef;padding-top:8px}
.dochead{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.say{margin:8px 0}
"""


def print_html(report: dict, title: str = "Study report", media_base: str = "") -> str:
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{esc(title)}</title><style>{PRINT_CSS}</style></head><body>"
        f"<h1>{esc(title)}</h1>"
        + render(report, print_mode=True, media_base=media_base)
        + "</body></html>"
    )


def chrome_candidates() -> list[str]:
    """Every Chrome that might render a PDF.

    A snap Chromium is confined and cannot read `/tmp`, and a Playwright shell is
    usually the one that works in a headless session, so the caller tries each in
    turn rather than trusting the first hit on PATH.
    """
    out: list[str] = []
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        found = shutil.which(name)
        if found:
            out.append(found)
    cache = Path.home() / ".cache" / "ms-playwright"
    if cache.is_dir():
        for pattern in (
            "chromium*headless*/chrome-*/chrome-headless*",
            "chromium-*/chrome-linux*/chrome",
        ):
            for candidate in sorted(cache.glob(pattern)):
                if candidate.is_file():
                    out.append(str(candidate))
    seen, unique = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def chrome_path() -> str | None:
    """The first candidate we have, whether or not it can actually run."""
    found = chrome_candidates()
    return found[0] if found else None


def available() -> dict:
    return {
        "pdftotext": bool(shutil.which("pdftotext")),
        "pdftoppm": bool(shutil.which("pdftoppm")),
        "pdfimages": bool(shutil.which("pdfimages")),
        "chrome": chrome_path(),
    }
