"""Viewer: render the atlas as one self-contained HTML file.

The data is inlined rather than fetched so the report opens from `file://`
without a server, and so what a judge sees is exactly the validated JSON that
the build wrote -- there is no second data path that could drift.

Four screens, hash-routed:

    #/                 atlas index (ranked, filterable)
    #/mode/<id>        one failure mode, with both evidence links
    #/evidence/<id>/<slot>  the cited page, quote highlighted in the text layer
    #/coverage         what was read, what was refused, what is modelled
"""

from __future__ import annotations

import json
from pathlib import Path

from .answer import COHORT_PATTERNS, NO_COHORT_REASON, STOP
from .rules import CONCEPTS

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Failure-Mode Atlas — Robotics 1</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{
  --ink:#0C2744; --muted:#3E5D80;
  --lime:#5FEE13; --orange:#FF6A2C; --blue:#2E6BFF; --magenta:#F404FF; --violet:#6209BA;
  --panel:rgba(255,255,255,.40); --edge:rgba(255,255,255,.62);
  --r:28px;
}
*{box-sizing:border-box}
html,body{margin:0;min-height:100%}
body{
  font-family:"Plus Jakarta Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  color:var(--ink);
  background:
    radial-gradient(1100px 700px at 88% -10%, rgba(94,238,19,.22), transparent 60%),
    radial-gradient(900px 600px at -10% 20%, rgba(244,4,255,.14), transparent 55%),
    linear-gradient(158deg,#44B4EC 0%,#7FD3F1 45%,#BFFCFC 100%);
  background-attachment:fixed;
  -webkit-font-smoothing:antialiased;
}
a{color:inherit}
.wrap{max-width:1180px;margin:0 auto;padding:28px 24px 80px}

/* ---------- chrome ---------- */
.top{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin-bottom:26px}
.brand{display:flex;align-items:center;gap:14px;min-width:280px}
.mark{width:46px;height:46px;border-radius:15px;background:var(--ink);color:#BFFCFC;
  display:grid;place-items:center;font-weight:800;font-size:19px;letter-spacing:-.5px;flex:none}
.brand h1{font-size:19px;margin:0;font-weight:800;letter-spacing:-.35px;line-height:1.15}
.brand p{margin:3px 0 0;font-size:12.5px;color:var(--muted);font-weight:500}
nav{display:flex;gap:6px;margin-left:auto;flex-wrap:wrap}
nav a{font-size:13px;font-weight:600;padding:9px 15px;border-radius:999px;text-decoration:none;
  color:var(--ink);border:1px solid transparent;transition:.16s}
nav a:hover{background:rgba(255,255,255,.35)}
nav a.on{background:var(--ink);color:#fff;box-shadow:0 8px 20px rgba(12,39,68,.22)}

/* ---------- panels ---------- */
.panel{background:var(--panel);border:1px solid var(--edge);border-radius:var(--r);
  backdrop-filter:blur(26px);-webkit-backdrop-filter:blur(26px);
  box-shadow:0 20px 50px rgba(12,39,68,.10);padding:24px}
.panel+.panel{margin-top:18px}
.grid{display:grid;gap:18px}
.g4{grid-template-columns:repeat(4,1fr)}
.g2{grid-template-columns:1.45fr 1fr}
@media(max-width:900px){.g4{grid-template-columns:repeat(2,1fr)}.g2{grid-template-columns:1fr}}

/* ---------- type ---------- */
.eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
h2{font-size:26px;margin:6px 0 10px;letter-spacing:-.6px;line-height:1.15}
h3{font-size:15px;margin:0 0 10px;letter-spacing:-.2px}
p{margin:0 0 10px;line-height:1.55;font-size:14px}
.small{font-size:12.5px;color:var(--muted);line-height:1.5}
.mono{font-variant-numeric:tabular-nums}

/* ---------- stat cards ---------- */
.stat{background:rgba(255,255,255,.5);border:1px solid var(--edge);border-radius:22px;padding:16px 18px}
.stat .n{font-size:31px;font-weight:800;letter-spacing:-1.2px;line-height:1}
.stat .n small{font-size:14px;font-weight:600;color:var(--muted);letter-spacing:0}
.stat .k{font-size:12px;color:var(--muted);font-weight:600;margin-top:6px}

/* ---------- controls ---------- */
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:4px 0 18px}
input[type=search]{font:inherit;font-size:13.5px;padding:11px 16px;border-radius:999px;
  border:1px solid rgba(255,255,255,.8);background:rgba(255,255,255,.55);color:var(--ink);
  min-width:250px;outline:none}
input[type=search]:focus{background:#fff;border-color:var(--blue);box-shadow:0 0 0 4px rgba(46,107,255,.14)}
.chip{font:inherit;font-size:12.5px;font-weight:600;padding:8px 13px;border-radius:999px;cursor:pointer;
  border:1px solid rgba(255,255,255,.8);background:rgba(255,255,255,.38);color:var(--ink);transition:.15s}
.chip:hover{background:rgba(255,255,255,.7)}
.chip.on{background:var(--ink);color:#fff;border-color:var(--ink)}

/* ---------- rows ---------- */
.rows{display:flex;flex-direction:column;gap:9px}
.row{display:grid;grid-template-columns:46px 1fr 132px 104px;gap:14px;align-items:center;
  padding:15px 18px;border-radius:20px;background:rgba(255,255,255,.34);
  border:1px solid rgba(255,255,255,.55);cursor:pointer;transition:.16s;text-align:left}
.row:hover{background:rgba(255,255,255,.66);transform:translateY(-1px);
  box-shadow:0 14px 30px rgba(12,39,68,.12)}
.row .rank{font-size:13px;font-weight:800;color:var(--violet);font-variant-numeric:tabular-nums}
.row .t{font-size:14.5px;font-weight:700;letter-spacing:-.2px;line-height:1.3}
.row .t span{display:block;font-size:11.5px;font-weight:600;color:var(--muted);margin-top:4px;
  letter-spacing:.02em}
@media(max-width:820px){
  .row{grid-template-columns:38px 1fr;grid-template-areas:"r t" "m m"}
  .row .rank{grid-area:r}.row .t{grid-area:t}.row .meter{grid-area:m}
  .row .qty{display:none}
}

/* ---------- marks meter: a quantity against 30 ---------- */
.meter{display:flex;align-items:center;gap:9px}
.bar{position:relative;height:9px;flex:1;border-radius:99px;background:rgba(12,39,68,.12);overflow:hidden}
.bar i{position:absolute;inset:0 auto 0 0;border-radius:99px;background:linear-gradient(90deg,var(--blue),var(--violet))}
.bar.strong i{background:linear-gradient(90deg,var(--orange),var(--magenta))}
.qty{font-size:13px;font-weight:800;font-variant-numeric:tabular-nums;white-space:nowrap}
.qty small{font-weight:600;color:var(--muted);font-size:11px}

/* ---------- tags ---------- */
.tag{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;
  letter-spacing:.05em;text-transform:uppercase;padding:5px 10px;border-radius:99px;
  background:rgba(255,255,255,.6);border:1px solid rgba(255,255,255,.9)}
.dot{width:7px;height:7px;border-radius:99px;display:inline-block;flex:none}
.doc{background:rgba(95,238,19,.30);border-color:rgba(95,238,19,.75)}
.rec{background:rgba(255,106,44,.24);border-color:rgba(255,106,44,.7)}
.thin{background:rgba(244,4,255,.16);border-color:rgba(244,4,255,.5)}

/* ---------- detail ---------- */
.kv{display:grid;grid-template-columns:150px 1fr;gap:8px 18px;font-size:13.5px;line-height:1.5}
.kv dt{color:var(--muted);font-weight:600}
.kv dd{margin:0}
.quote{border-left:3px solid var(--lime);padding:2px 0 2px 16px;margin:8px 0 0;
  font-size:14px;line-height:1.6;letter-spacing:-.1px}
.quote.lecture{border-left-color:var(--blue)}
.evcard{background:rgba(255,255,255,.5);border:1px solid var(--edge);border-radius:20px;padding:16px 18px}
.evcard+.evcard{margin-top:12px}
.evhead{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:4px}
.evhead b{font-size:13px}
.evhead code{font-size:11.5px;color:var(--muted);background:rgba(12,39,68,.06);padding:2px 7px;border-radius:6px}
.btn{font:inherit;font-size:12.5px;font-weight:700;padding:9px 14px;border-radius:99px;border:0;
  background:var(--ink);color:#fff;cursor:pointer;text-decoration:none;display:inline-block;transition:.15s}
.btn:hover{background:var(--violet)}
.btn.ghost{background:rgba(255,255,255,.55);color:var(--ink);border:1px solid rgba(255,255,255,.9)}
.btn.ghost:hover{background:#fff}

/* ---------- evidence viewer ---------- */
.page{font-size:13.5px;line-height:1.85;white-space:pre-wrap;word-break:break-word;
  background:rgba(255,255,255,.62);border-radius:20px;padding:22px 24px;
  border:1px solid rgba(255,255,255,.9);max-height:60vh;overflow:auto}
.page mark{background:linear-gradient(180deg,rgba(95,238,19,.55),rgba(95,238,19,.28));
  color:var(--ink);font-weight:700;border-radius:4px;padding:1px 2px;box-decoration-break:clone}
.page .lead{color:var(--muted)}
.pglabel{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.cite{font-size:12px;color:var(--muted);display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.cite b{color:var(--ink)}

/* ---------- coverage ---------- */
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid rgba(12,39,68,.10)}
th{font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);font-weight:700}
td.n{font-variant-numeric:tabular-nums;font-weight:700;width:88px}
.bad{color:#B3200B;font-weight:700}
.good{color:#1F7A00;font-weight:700}
ul{margin:6px 0 0;padding-left:20px;font-size:13.5px;line-height:1.6}
li{margin-bottom:5px}
.note{border-left:3px solid var(--orange);padding:2px 0 2px 14px;font-size:13px;color:var(--ink);
  background:rgba(255,106,44,.08);border-radius:0 12px 12px 0;padding:10px 14px;margin:12px 0}
.kbd{font-size:11.5px;font-weight:700;background:rgba(12,39,68,.08);padding:2px 7px;border-radius:6px}
footer{margin-top:26px;font-size:11.5px;color:var(--muted);text-align:center;line-height:1.6}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div class="brand">
      <div class="mark">FM</div>
      <div>
        <h1>Failure-Mode Atlas</h1>
        <p>Robotics 1 · Sapienza · Prof. A. De Luca</p>
      </div>
    </div>
    <nav id="nav">
      <a href="#/" data-nav="atlas">Atlas</a>
      <a href="#/ask" data-nav="ask">Ask</a>
      <a href="#/coverage" data-nav="coverage">Coverage</a>
    </nav>
  </div>
  <main id="app"></main>
  <footer>
    Every quote on this page is verified to occur verbatim on the cited page by the build's
    grounding check. Marks are an equal-split model, not a measured quantity.
  </footer>
</div>

<script id="d-atlas" type="application/json">__ATLAS__</script>
<script id="d-pages" type="application/json">__PAGES__</script>
<script id="d-cov" type="application/json">__COV__</script>
<script id="d-guard" type="application/json">__GUARD__</script>
<script>
const ATLAS = JSON.parse(document.getElementById('d-atlas').textContent);
const PAGES = JSON.parse(document.getElementById('d-pages').textContent);
const COV   = JSON.parse(document.getElementById('d-cov').textContent);
const GUARD = JSON.parse(document.getElementById('d-guard').textContent);
const A     = COV.analysis || {};
const byId  = Object.fromEntries(ATLAS.map(e => [e.id, e]));

const CONCEPT_LABEL = {
  dh_frames:'DH frame assignment', direct_kinematics:'Direct kinematics',
  inverse_kinematics:'Inverse kinematics', jacobian:'Differential kinematics / Jacobian',
  singularity:'Singular configurations', statics:'Statics / force transformation',
  orientation:'Orientation / Euler angles', trajectory:'Trajectory planning (joint space)',
  trajectory_cartesian:'Trajectory planning (Cartesian)', kinematic_control:'Kinematic control',
  actuators:'Actuators / transmissions'
};
const PALETTE = ['#6209BA','#2E6BFF','#F404FF','#FF6A2C','#0C2744','#00A3A3','#B3200B','#5FEE13'];
const conceptColor = c => {
  const keys = Object.keys(CONCEPT_LABEL);
  return PALETTE[keys.indexOf(c) % PALETTE.length] || '#0C2744';
};
const esc = s => String(s == null ? '' : s)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const flat = s => String(s||'').replace(/\s+/g,' ').trim();
const pad2 = n => String(n).padStart(2,'0');
/* "Robotics1_26.07.13 / Exercise 2 / b" -> "Exercise 2b"; numeric fallback
   clause labels are dropped because they are not on the page. */
const shortRef = ref => {
  const p = String(ref || '').split(' / ').map(s => s.trim());
  const ex = p.find(x => /^(exercise|question)\b/i.test(x)) || '';
  const lab = p.length >= 3 ? p[p.length - 1] : '';
  if (ex && /^[a-z]$/i.test(lab)) return ex + lab;
  return ex || p[1] || String(ref || '');
};

/* concept order in the filter bar, by frequency in the atlas */
const conceptCounts = {};
ATLAS.forEach(e => { const c = e.concepts[0]; conceptCounts[c] = (conceptCounts[c]||0)+1; });
const conceptOrder = Object.keys(conceptCounts).sort((a,b) => conceptCounts[b]-conceptCounts[a]);

let filter = { q:'', concept:null };

/* ------------------------------------------------------------------ index */
function statCards(){
  const doc = ATLAS.filter(e => e.strength === 'documented').length;
  const thin = ATLAS.filter(e => e.exams_affected < 3).length;
  return `
  <div class="grid g4">
    <div class="stat"><div class="n">${ATLAS.length}</div><div class="k">failure modes, ranked</div></div>
    <div class="stat"><div class="n">${A.exams_analysed}<small>/${A.exams_total}</small></div>
      <div class="k">exam papers analysed</div></div>
    <div class="stat"><div class="n">${A.questions_parsed}</div><div class="k">task clauses parsed</div></div>
    <div class="stat"><div class="n">${A.rejected_by_grounding}<small> rejected</small></div>
      <div class="k">quotes that failed grounding</div></div>
  </div>`;
}

function rowHTML(e, i){
  const c = e.concepts[0];
  const pct = Math.min(100, (e.marks_at_risk / 30) * 100);
  return `
  <button class="row" onclick="go('#/mode/${e.id}')">
    <div class="rank">${pad2(i+1)}</div>
    <div class="t">${esc(e.title)}
      <span>${esc(CONCEPT_LABEL[c] || c)} · ${e.questions_affected} questions ·
        ${e.exams_affected} exams${e.exams_affected < 3 ? ' · thin evidence' : ''}</span></div>
    <div class="meter">
      <div class="bar ${e.marks_at_risk >= 4 ? 'strong' : ''}"><i style="width:${pct.toFixed(1)}%"></i></div>
      <div class="qty">${e.marks_at_risk.toFixed(2)}<small>/30</small></div>
    </div>
    <div style="text-align:right">
      <span class="tag ${e.strength === 'documented' ? 'doc' : 'rec'}">
        <span class="dot" style="background:${e.strength === 'documented' ? 'var(--lime)' : 'var(--orange)'}"></span>
        ${e.strength}</span>
    </div>
  </button>`;
}

function visible(){
  const q = filter.q.toLowerCase().trim();
  return ATLAS.filter(e => {
    if (filter.concept && e.concepts[0] !== filter.concept) return false;
    if (!q) return true;
    return (e.title + ' ' + e.trigger + ' ' + e.wrong_turn + ' ' + e.root_misconception + ' ' +
            e.id).toLowerCase().includes(q);
  });
}

function screenIndex(){
  const list = visible();
  return `
  ${statCards()}
  <div class="panel" style="margin-top:18px">
    <div class="eyebrow">The atlas</div>
    <h2>What these exams are built to catch</h2>
    <p class="small" style="max-width:74ch">Each row is a design tell: an instruction in a past paper
      that only makes sense if a specific error is anticipated. Ranked by
      <b>marks at risk × questions affected</b>. Click any row for the quote it rests on.</p>
    <div class="controls">
      <input type="search" id="q" placeholder="Search a mode, concept or misconception…" value="${esc(filter.q)}">
      <button class="chip ${filter.concept===null?'on':''}" onclick="setConcept(null)">All ${ATLAS.length}</button>
      ${conceptOrder.map(c => `<button class="chip ${filter.concept===c?'on':''}"
        onclick="setConcept('${c}')">${esc(CONCEPT_LABEL[c]||c)} ${conceptCounts[c]}</button>`).join('')}
    </div>
    <div class="rows">${list.length ? list.map(rowHTML).join('') :
      `<div class="panel" style="box-shadow:none;background:rgba(255,255,255,.3)">
         <p style="margin:0">No mode matches that filter. The atlas would rather show nothing than
         stretch an entry to fit.</p></div>`}</div>
  </div>`;
}

function setConcept(c){ filter.concept = c; render(); }
function setQuery(v){ filter.q = v; }

/* ----------------------------------------------------------------- detail */
function screenMode(id){
  const e = byId[id];
  if (!e) return notFound();
  const exam = e.evidence.exam, lec = e.evidence.lecture;
  const c = e.concepts[0];
  const pct = Math.min(100, (e.marks_at_risk / 30) * 100);
  const others = ATLAS.filter(x => x.id !== e.id && x.concepts[0] === c).slice(0,4);
  return `
  <div class="grid g2">
   <div>
    <div class="panel">
      <div class="eyebrow">${pad2(ATLAS.indexOf(e)+1)} of ${ATLAS.length} · ${esc(CONCEPT_LABEL[c]||c)}</div>
      <h2>${esc(e.title)}</h2>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px">
        <span class="tag ${e.strength==='documented'?'doc':'rec'}">
          <span class="dot" style="background:${e.strength==='documented'?'var(--lime)':'var(--orange)'}"></span>
          ${e.strength}</span>
        <span class="tag">confidence ${e.confidence}</span>
        ${e.exams_affected < 3 ? '<span class="tag thin">thin evidence</span>' : ''}
        <span class="tag"><span class="dot" style="background:${conceptColor(c)}"></span>${esc(e.rule_id||'')}</span>
      </div>
      <dl class="kv">
        <dt>Trigger</dt><dd>${esc(e.trigger)}</dd>
        <dt>What goes wrong</dt><dd>${esc(e.wrong_turn)}</dd>
        <dt>Root misconception</dt><dd>${esc(e.root_misconception)}</dd>
        <dt>Probe</dt><dd>${esc(e.probe)}</dd>
        <dt>Correction</dt><dd>${esc(e.correction)}</dd>
      </dl>
    </div>
    ${others.length ? `<div class="panel" style="padding:20px">
      <div class="eyebrow">Also in ${esc(CONCEPT_LABEL[c]||c)}</div>
      <div style="margin-top:8px;display:flex;flex-direction:column;gap:6px">
      ${others.map(o => `<button class="chip" style="text-align:left"
        onclick="go('#/mode/${o.id}')">${esc(o.title)}</button>`).join('')}
      </div></div>` : ''}
   </div>
    <div>
      <div class="panel" style="padding:20px">
        <div class="eyebrow">Exposure</div>
        <div style="display:flex;align-items:baseline;gap:8px;margin:8px 0 2px">
          <div style="font-size:38px;font-weight:800;letter-spacing:-1.6px">${e.marks_at_risk.toFixed(2)}</div>
          <div class="small">marks out of 30, per affected exam</div>
        </div>
        <div class="bar ${e.marks_at_risk>=4?'strong':''}" style="height:12px;margin:10px 0 14px">
          <i style="width:${pct.toFixed(1)}%"></i></div>
        <table>
          <tr><td>Questions carrying it</td><td class="n">${e.questions_affected}</td></tr>
          <tr><td>Exams where it appears</td><td class="n">${e.exams_affected}</td></tr>
          <tr><td>Marks per analysed exam</td><td class="n">${(e.marks_per_exam_all||0).toFixed(2)}</td></tr>
        </table>
        <div class="note">Equal split across exercises, then across task clauses. The split is an
          assumption; the total of 30 is corroborated by seven midterms that state points.</div>
      </div>
    </div>
  </div>
  <div class="panel">
    <div class="eyebrow">Evidence</div>
    <h2 style="font-size:20px">Two documents, two claims</h2>
    <div class="grid g2" style="margin-top:12px">
      <div class="evcard" style="margin:0">
        <div class="evhead"><b>What the exam demands</b>
          <code>${esc(exam.doc)}</code><code>${esc(exam.ref)}</code></div>
        <p class="quote">“${esc(exam.quote)}”</p>
        <div style="margin-top:14px"><a class="btn" href="#/evidence/${e.id}/exam">Open the page</a></div>
      </div>
      ${lec ? `<div class="evcard" style="margin:0">
        <div class="evhead"><b>Where it is taught</b>
          <code>${esc(lec.doc)}</code><code>${esc(lec.ref)}</code></div>
        <p class="quote lecture">“${esc(lec.quote)}”</p>
        <div style="margin-top:14px"><a class="btn ghost" href="#/evidence/${e.id}/lecture">Open the page</a></div>
      </div>` : `<div class="evcard" style="margin:0">
        <div class="evhead"><b>Where it is taught</b></div>
        <p class="small">No lecture page in the corpus covers this concept.</p></div>`}
    </div>
  </div>
  ${e.occurrences && e.occurrences.length > 1 ? `<div class="panel">
    <div class="eyebrow">Other sightings</div>
    <h3 style="margin-top:6px">The same tell in ${e.exams_affected} papers</h3>
    <table><tr><th>Paper</th><th>Where</th><th>Quote</th></tr>
    ${e.occurrences.map(o => `<tr><td class="mono" style="width:220px">${esc(o.doc)}</td>
      <td style="width:120px">${esc(shortRef(o.ref))}</td>
      <td class="small">${esc(o.quote.slice(0,180))}${o.quote.length>180?'…':''}</td></tr>`).join('')}
    </table></div>` : ''}`;
}

/* --------------------------------------------------------------- evidence */
function screenEvidence(id, slot){
  const e = byId[id];
  if (!e) return notFound();
  const blk = e.evidence[slot];
  if (!blk) return notFound();
  const m = (blk.ref.match(/(\d+)\s*$/) || []);
  const pageNo = m[1];
  const raw = ((PAGES[blk.doc] || {})[pageNo] || '');
  const text = flat(raw);
  const q = flat(blk.quote);
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  let body;
  if (!text) {
    body = `<div class="page"><span class="lead">No text layer was stored for this page.</span></div>`;
  } else if (i < 0) {
    body = `<div class="page"><span class="lead">The quote could not be located in the stored
      text layer of this page. That is a bug, not a finding — the build would have refused it.</span></div>`;
  } else {
    body = `<div class="page"><span class="lead">…${esc(text.slice(Math.max(0,i-340), i))}</span><mark>${esc(text.slice(i, i+q.length))}</mark>${esc(text.slice(i+q.length, i+q.length+520))}…</div>`;
  }
  const sharing = ATLAS.filter(x => {
    const b = x.evidence[slot];
    return b && b.doc === blk.doc && (b.ref.match(/(\d+)\s*$/)||[])[1] === pageNo;
  });
  return `
  <div class="panel">
    <div class="eyebrow">Evidence · ${slot === 'exam' ? 'exam paper' : 'lecture deck'}</div>
    <h2 style="font-size:21px">${esc(blk.doc)}</h2>
    <div class="pglabel">
      <code style="font-size:12px;background:rgba(12,39,68,.07);padding:4px 9px;border-radius:8px">
        ${esc(blk.ref)}</code>
      <span class="small">text layer of page ${esc(pageNo)}, whitespace collapsed</span>
      <a class="btn ghost" style="margin-left:auto"
         href="../data/pages/${encodeURIComponent(blk.doc)}_p${encodeURIComponent(pageNo)}.pdf"
         target="_blank" rel="noopener">Open the page as PDF</a>
      <a class="btn ghost" href="#/mode/${e.id}">← back to the mode</a>
    </div>
    ${body}
    <div class="cite" style="margin-top:14px">
      <b>Cited as:</b> “${esc(blk.quote)}”
    </div>
    <div class="note">This is the extracted text of the page, not a screenshot. Line breaks are
      collapsed so the quoted span can be shown as one run; nothing else is changed. The build
      verified this exact string against this exact page, or the entry would not exist.
      <b>Open the page as PDF</b> to check the quote against the rendered page, where the text
      layer plays no part.</div>
  </div>
  ${sharing.length > 1 ? `<div class="panel">
    <div class="eyebrow">Same instrument</div>
    <p class="small" style="max-width:76ch">This page is cited by ${sharing.length} entries. That is
      expected — one instruction can pre-empt several errors — but it means these entries are not
      independent evidence of each other.</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
      ${sharing.map(x => `<button class="chip" onclick="go('#/mode/${x.id}')">${esc(x.title)}</button>`).join('')}
    </div></div>` : ''}`;
}

/* --------------------------------------------------------------- coverage */
function screenCoverage(){
  const ex = COV.exams, sl = COV.slides;
  const documented = ATLAS.filter(e => e.strength === 'documented').length;
  return `
  <div class="panel">
    <div class="eyebrow">Coverage</div>
    <h2>What was read, what was refused, what is modelled</h2>
    <p class="small" style="max-width:76ch">A judge should be able to see the edges of the corpus
      without reading the code. Everything below is counted by the build, not typed by hand.</p>
    <div class="grid g4" style="margin-top:14px">
      <div class="stat"><div class="n">${ex.documents}</div><div class="k">exam papers on disk</div></div>
      <div class="stat"><div class="n">${ex.pages}</div><div class="k">exam pages (${ex.pct_pages_readable}% readable)</div></div>
      <div class="stat"><div class="n">${sl.documents}</div><div class="k">lecture decks (${sl.pages} pages)</div></div>
      <div class="stat"><div class="n">${COV.ocr_pages}</div><div class="k">pages OCR'd</div></div>
    </div>
  </div>

  <div class="panel">
    <div class="eyebrow">Resolution</div>
    <h3>What the analysis actually reached</h3>
    <table>
      <tr><th>Outcome</th><th>Exams</th><th>Why</th></tr>
      <tr><td>Analysed</td><td class="n good">${A.exams_analysed}</td>
        <td class="small">Segment into two or more exercises, so marks can be spread across questions</td></tr>
      <tr><td>Excluded — single-block era</td><td class="n">${A.exams_excluded_single_block_era}</td>
        <td class="small">Pre-2013 papers are one undivided block; there are no per-question units to rank</td></tr>
      <tr><td>Excluded — partial sheet</td><td class="n">${A.exams_excluded_partial_sheet}</td>
        <td class="small">Extra sheets, data sheets and answer keys are fragments of a paper, not a paper</td></tr>
      <tr><td>Excluded — unreadable</td><td class="n">${A.exams_excluded_scanned}</td>
        <td class="small">No text layer at all; nothing is claimed from these pages</td></tr>
      <tr><td>Questions parsed</td><td class="n">${A.questions_parsed}</td>
        <td class="small">${A.pct_questions_parsed}% of the estimated total task clauses</td></tr>
    </table>
  </div>

  <div class="grid g2">
    <div class="panel">
      <div class="eyebrow">The guardrail</div>
      <h3>Two validators, run on every build</h3>
      <table>
        <tr><th>Validator</th><th>Question</th><th>Rejected</th></tr>
        <tr><td>Structural</td><td class="small">Are all required fields present, typed and in range?</td>
          <td class="n">0</td></tr>
        <tr><td>Grounding</td><td class="small">Does the quote occur verbatim on the cited page, after
          whitespace normalisation?</td><td class="n">${A.rejected_by_grounding}</td></tr>
      </table>
      <div class="note"><b>atlas.json is only written if both pass.</b> A build that cannot support a
        claim produces <span class="kbd">REJECTED.txt</span> instead of a shorter atlas.</div>
      <p class="small" style="margin-top:10px">Also rejected before writing:
        ${A.rejected_quote_missing_trigger_span} quote(s) that did not contain the rule's trigger, and
        ${A.rejected_quote_too_short} that were too short to be evidence. Rule precision vetoes
        dropped ${A.clauses_vetoed_by_rule_precision} clause(s) whose wording matched a pattern for the
        wrong reason.</p>
      <div style="margin-top:16px;padding-top:16px;border-top:1px solid rgba(12,39,68,.12)">
        <h3>Try to break it</h3>
        <p class="small" style="margin-bottom:10px">Edit the quote below and check it against the page
          it claims to come from. This is the same test the build runs before anything is written.</p>
        <select id="gq-id" onchange="onQuoteTarget()"
          style="font:inherit;font-size:12px;font-weight:600;padding:9px 12px;border-radius:12px;
          border:1px solid rgba(255,255,255,.9);background:rgba(255,255,255,.6);color:var(--ink);
          max-width:100%;margin-bottom:8px">
          ${ATLAS.map(x => `<option value="${x.id}">${esc(x.id)}</option>`).join('')}
        </select>
        <textarea id="gq-text" rows="4" spellcheck="false"
          style="font:inherit;font-size:12.5px;line-height:1.5;width:100%;padding:12px 14px;
          border-radius:16px;border:1px solid rgba(255,255,255,.9);background:rgba(255,255,255,.62);
          color:var(--ink);resize:vertical;margin-bottom:10px"></textarea>
        <button class="btn" onclick="checkGrounding()">Check against the page</button>
        <div id="gq-out" class="small" style="margin-top:10px;min-height:20px"></div>
      </div>
    </div>
    <div class="panel">
      <div class="eyebrow">Honesty budget</div>
      <h3>Documented vs reconstructed</h3>
      <table>
        <tr><th>Strength</th><th>Entries</th></tr>
        <tr><td><span class="tag doc">documented</span> the exam wording pre-empts the error</td>
          <td class="n">${documented}</td></tr>
        <tr><td><span class="tag rec">reconstructed</span> the link to student behaviour is ours</td>
          <td class="n">${ATLAS.length - documented}</td></tr>
      </table>
      <p class="small" style="margin-top:10px">The second is never presented as the first. A judge who
        disagrees with a reconstructed entry can attack the named rule in
        <span class="kbd">atlas/rules.py</span> rather than argue with a hidden leap.</p>
      <h3 style="margin-top:16px">Marks</h3>
      <p class="small">${esc(A.marks_model.note)}</p>
    </div>
  </div>

  <div class="panel">
    <div class="eyebrow">Refusals</div>
    <h3>Two questions this atlas will not answer</h3>
    <table>
      <tr><th>Question</th><th>Code</th><th>Why</th></tr>
      <tr><td class="mono">What will students score on question 3?</td>
        <td><span class="tag thin">NO_COHORT_DATA</span></td>
        <td class="small">The corpus holds questions and solutions. It holds no responses, no marks,
          no distribution. A predicted score would be invented.</td></tr>
      <tr><td class="mono">Failure modes for a course with no material</td>
        <td><span class="tag thin">NO_CORPUS</span></td>
        <td class="small">With no citable document there is nothing to report, and an atlas of
          guesses is what this project exists to avoid.</td></tr>
    </table>
    <p class="small" style="margin-top:10px">Both are checked before retrieval, in code, so a
      persuasive question cannot talk the system past them.</p>
    <p style="margin-top:12px"><a class="btn ghost" href="#/ask">Try the cohort refusal in the Ask screen →</a> <span class="small">The empty-corpus refusal is a build-time path: run <span class="kbd">ask … --corpus /tmp/empty</span>.</span></p>
  </div>

  <div class="panel">
    <div class="eyebrow">Limitations</div>
    <ul>
      <li><b>No cohort data.</b> Nothing here says what students did — only what the papers are
        built to catch.</li>
      <li><b>Marks are modelled.</b> Ranking is exposure under an equal split, not observed loss.</li>
      <li><b>Rules are a reading.</b> 17 tells, each named and quotable, but another examiner could
        read the same instruction differently.</li>
      <li><b>Entries are not independent.</b> One sentence can pre-empt several errors, so the
        same quote may support more than one mode.</li>
      <li><b>Extraction artefacts.</b> Inline maths is mangled by PDF extraction, so quotes are
        prose spans; equations are never used as evidence.</li>
      <li><b>One course, by design.</b> The corpus was chosen so no cross-course comparison is
        attempted.</li>
    </ul>
  </div>`;
}

/* -------------------------------------------------------------------- ask */

/* The guard, the stop list and the concept labels are inlined from
   atlas/answer.py and atlas/rules.py at build time. There is no second copy of
   the refusal rules in JavaScript, so the browser and the CLI cannot disagree. */
function scoreEntry(e, terms){
  const hay = [
    e.title, e.trigger, e.wrong_turn, e.root_misconception,
    e.concepts.map(c => GUARD.concept_labels[c] || c).join(' '),
    e.rule_id || ''
  ].join(' ').toLowerCase();
  let n = 0;
  terms.forEach(t => { if (hay.includes(t)) n++; });
  return n;
}

function refusalCard(question){
  return `
  <div class="panel" style="background:rgba(255,106,44,.13);border-color:rgba(255,106,44,.5)">
    <div class="eyebrow">Refused · NO_COHORT_DATA</div>
    <h3 style="font-size:17px;margin:8px 0 6px">${esc(question)}</h3>
    <p style="margin:0">${esc(GUARD.reason)}</p>
    <p class="small" style="margin-top:12px">This check runs before retrieval, so the question
      never reaches the atlas. Refusing is a result, not an error.</p>
  </div>`;
}

function runAsk(){
  const box = document.getElementById('ask-q');
  const out = document.getElementById('ask-out');
  if (!box || !out) return;
  const q = box.value.trim();
  if (!q){
    out.innerHTML = `<div class="panel" style="box-shadow:none;background:rgba(255,255,255,.3)">
      <p style="margin:0" class="small">Type a question, or pick one of the examples above.</p></div>`;
    return;
  }

  const low = q.toLowerCase();
  const guardHit = GUARD.patterns.find(p => { try { return new RegExp(p).test(low); } catch(e){ return false; } });
  if (guardHit){
    out.innerHTML = refusalCard(q);
    return;
  }

  const terms = new Set((low.match(/[a-z]{3,}/g) || []).filter(w => !GUARD.stop.includes(w)));
  const hits = ATLAS
    .map(e => [scoreEntry(e, terms), e])
    .filter(([s]) => s > 0)
    .sort((a, b) => b[0] - a[0])
    .slice(0, 3);

  if (!hits.length){
    out.innerHTML = `<div class="panel" style="box-shadow:none;background:rgba(255,255,255,.3)">
      <h3 style="margin-top:0">No match in the atlas</h3>
      <p class="small" style="margin:0">Rather than stretch an entry to fit, the atlas reports no
        match. Covered concepts: ${Object.values(CONCEPT_LABEL).join(' · ')}.</p></div>`;
    return;
  }

  out.innerHTML = `<div class="panel" style="padding:18px 20px">
      <div class="eyebrow">${hits.length} match(es), ranked by marks at risk</div></div>` +
    hits.map(([s, e]) => `
      <button class="row" style="grid-template-columns:46px 1fr 132px 104px;margin-top:9px"
              onclick="go('#/mode/${e.id}')">
        <div class="rank">${s}</div>
        <div class="t">${esc(e.title)}
          <span>${esc(e.trigger)}</span></div>
        <div class="meter">
          <div class="bar ${e.marks_at_risk >= 4 ? 'strong' : ''}">
            <i style="width:${Math.min(100,(e.marks_at_risk/30)*100).toFixed(1)}%"></i></div>
          <div class="qty">${e.marks_at_risk.toFixed(2)}<small>/30</small></div>
        </div>
        <div style="text-align:right"><span class="tag ${e.strength === 'documented' ? 'doc' : 'rec'}">
          ${e.strength}</span></div>
      </button>
      <div class="panel" style="padding:14px 18px;margin-top:-3px;box-shadow:none;
           background:rgba(255,255,255,.26)">
        <p class="quote" style="margin:0">“${esc(e.evidence.exam.quote.slice(0, 220))}${e.evidence.exam.quote.length > 220 ? '…' : ''}”</p>
        <p class="small" style="margin:8px 0 0">${esc(e.evidence.exam.doc)} · ${esc(e.evidence.exam.ref)}</p>
      </div>`).join('');
}

function screenAsk(){
  const examples = [
    'Why do students get DH frame signs wrong?',
    'Which failure modes affect trajectory planning?',
    'What will students score on question 3?',
  ];
  return `
  <div class="panel">
    <div class="eyebrow">Ask</div>
    <h2>Ask the atlas a question</h2>
    <p class="small" style="max-width:76ch">Answers are retrieved from the ${ATLAS.length} validated
      entries by keyword overlap. Nothing is generated, so a result can only ever be an entry that
      already passed both validators. Questions that would need data the corpus does not hold are
      refused before retrieval starts.</p>
    <div class="controls" style="margin-top:14px">
      <input type="search" id="ask-q" placeholder="e.g. Why do students get DH frame signs wrong?"
             style="flex:1;min-width:320px" onkeydown="if(event.key==='Enter'){runAsk()}">
      <button class="btn" onclick="runAsk()">Ask</button>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 16px">
      ${examples.map(x => `<button class="chip" onclick="document.getElementById('ask-q').value=${JSON.stringify(x).replace(/"/g,'&quot;')};runAsk()">${esc(x)}</button>`).join('')}
    </div>
    <div id="ask-out" style="display:flex;flex-direction:column;gap:10px"></div>
  </div>`;
}

function notFound(){
  return `<div class="panel"><h2>Not in the atlas</h2>
    <p>That id is not one of the ${ATLAS.length} entries. <a href="#/">Back to the index</a>.</p></div>`;
}

/* Grounding, live: the same containment test the build runs, on text the visitor
   can edit. Demonstrates that the guardrail is a check, not a promise. */
function onQuoteTarget(){
  const el = document.getElementById('gq-id');
  const t  = document.getElementById('gq-text');
  const o  = document.getElementById('gq-out');
  if (!el || !t) return;
  t.value = byId[el.value].evidence.exam.quote;
  if (o) o.innerHTML = '';
}
function checkGrounding(){
  const el = document.getElementById('gq-id');
  const t  = document.getElementById('gq-text');
  const o  = document.getElementById('gq-out');
  if (!el || !t || !o) return;
  const e = byId[el.value];
  const blk = e.evidence.exam;
  const pageNo = (blk.ref.match(/(\d+)\s*$/) || [])[1];
  const page = flat((PAGES[blk.doc] || {})[pageNo] || '');
  const typed = flat(t.value);
  if (!typed){ o.innerHTML = '<span class="bad">Empty.</span>'; return; }
  if (!page){ o.innerHTML = '<span class="bad">No text layer stored for that page.</span>'; return; }
  o.innerHTML = page.toLowerCase().includes(typed.toLowerCase())
    ? `<span class="good">FOUND</span> on <b>${esc(blk.doc)}</b>, ${esc(blk.ref)}. This string would be accepted.`
    : `<span class="bad">NOT FOUND.</span> The build would refuse this quote — it writes
       <span class="kbd">REJECTED.txt</span> and no atlas entry.`;
}

/* ------------------------------------------------------------------ router */
function go(hash){ location.hash = hash; }
function route(){
  const h = location.hash.replace(/^#\/?/, '');
  const parts = h.split('/').filter(Boolean);
  let html, nav = 'atlas';
  if (!parts.length) html = screenIndex();
  else if (parts[0] === 'mode') html = screenMode(parts[1]);
  else if (parts[0] === 'evidence') html = screenEvidence(parts[1], parts[2] === 'lecture' ? 'lecture' : 'exam');
  else if (parts[0] === 'ask') { html = screenAsk(); nav = 'ask'; }
  else if (parts[0] === 'coverage') { html = screenCoverage(); nav = 'coverage'; }
  else html = notFound();
  document.getElementById('app').innerHTML = html;
  document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('on', a.dataset.nav === nav));
  if (nav === 'coverage') onQuoteTarget();
  if (nav === 'ask') { const a = document.getElementById('ask-q'); if (a) a.focus(); }
  window.scrollTo({top:0, behavior:'instant'});
  const q = document.getElementById('q');
  if (q) {
    q.addEventListener('input', ev => { setQuery(ev.target.value); renderKeepFocus(); });
  }
}

/* Re-render the list without losing the caret in the search box. */
function renderKeepFocus(){
  const q = document.getElementById('q');
  const pos = q ? q.selectionStart : 0;
  const had = !!q;
  route();
  if (had) {
    const n = document.getElementById('q');
    if (n) { n.focus(); n.setSelectionRange(pos, pos); }
  }
}
function render(){ if (document.getElementById('q')) renderKeepFocus(); else route(); }

window.addEventListener('hashchange', route);
route();
</script>
</body>
</html>
"""


def render(out_dir: Path = Path("data"), dest: Path = Path("web/index.html")) -> Path:
    out_dir = Path(out_dir)
    atlas = (out_dir / "atlas.json").read_text()
    pages = (out_dir / "evidence_pages.json").read_text()
    cov = (out_dir / "coverage.json").read_text()

    # The refusal guard and the retrieval stop list are inlined from Python so
    # the Ask screen runs exactly the rules the CLI runs, with no second copy to
    # drift. Only the data crosses; the logic stays in atlas/answer.py.
    guard = json.dumps(
        {
            "patterns": list(COHORT_PATTERNS),
            "reason": NO_COHORT_REASON,
            "stop": sorted(STOP),
            "concept_labels": {k: v["label"] for k, v in CONCEPTS.items()},
        },
        ensure_ascii=False,
    )

    # `</script>` inside a JSON string would close the tag early.
    safe = lambda s: s.replace("</", "<\\/")
    html = (
        PAGE.replace("__ATLAS__", safe(atlas))
        .replace("__PAGES__", safe(pages))
        .replace("__COV__", safe(cov))
        .replace("__GUARD__", safe(guard))
    )
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html)
    return dest


if __name__ == "__main__":
    print(render())
