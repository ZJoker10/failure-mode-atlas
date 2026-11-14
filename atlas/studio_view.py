"""Studio page: the quiz, the dropzone and the report, in one self-contained HTML.

What is server-side and what is browser-side is deliberate:

* the **quiz** ships as data (`vark.payload()`), so the twelve questions and the
  letter weights exist once, in `vark.py`. Scoring is a four-counter tally in
  JavaScript, and a node parity test compares it with the Python version;
* **uploads** go to the local server because `pdftotext` and the OOXML parsers
  are much better than anything that runs in a page, and because the server is
  the only thing that can write the figure files;
* the **report** is rendered by Python (`studio.render`) and injected as HTML,
  so the four presentations are not re-implemented in JavaScript;
* **speech** is the browser's own `speechSynthesis`; nothing is uploaded.

The only state that survives a reload is the VARK result, in localStorage. The
uploaded files live in a session directory on this machine and nowhere else.
"""

from __future__ import annotations

import json

from . import vark

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Studio — Failure-Mode Atlas</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/theme.css">
</head>
<body>
<div class="wrap">

  <header class="top">
    <div class="brand">
      <div class="mark">ST</div>
      <div>
        <h1>Studio</h1>
        <p>Upload your material. Get it back in the shape you learn in.</p>
      </div>
    </div>
    <nav class="tabs">
      <a href="#quiz" data-tab="quiz">Preference</a>
      <a href="#material" data-tab="material">Material</a>
      <a href="#report" data-tab="report">Report</a>
    </nav>
  </header>

  <div id="banner"></div>

  <!-- ------------------------------------------------------------ quiz -->
  <section id="quiz" class="panel" hidden>
    <div class="eyebrow">Preference quiz · <span id="qcount">1</span> of <span id="qtotal">12</span></div>
    <div class="prog"><i id="qprog" style="width:0%"></i></div>
    <h2 class="qstem" id="qstem">Loading…</h2>
    <div class="opts" id="qopts"></div>
    <div class="qfoot">
      <button class="btn ghost" id="qback" onclick="quizBack()" style="visibility:hidden">← Back</button>
      <span class="small">Keys 1–4 answer · ← goes back. Saved on this device, so you only do this once.</span>
    </div>
    <p class="small" style="margin-top:14px" id="qshort"></p>
  </section>

  <!-- -------------------------------------------------------- quiz result -->
  <section id="result" class="panel" hidden>
    <div class="eyebrow">Your preference · saved on this device</div>
    <h2 id="rname">—</h2>
    <p class="small" id="rquad" style="margin-top:0"></p>
    <div class="bars" id="rbars"></div>
    <p id="rblurb" style="margin-top:14px"></p>
    <div class="warn" style="margin-top:14px">
      <b>What this is not:</b> <span id="rcaveat"></span>
    </div>
    <div class="qfoot">
      <button class="btn ghost" onclick="quizRetake()">Retake the quiz</button>
      <button class="btn lime" onclick="go('material')">Upload your material →</button>
    </div>
  </section>

  <!-- ---------------------------------------------------------- material -->
  <section id="material" class="panel" hidden>
    <div class="eyebrow">Step 2 · your files</div>
    <h2>What should the report be built from?</h2>
    <p class="small">PDF, PowerPoint (.pptx) or Word (.docx). Everything is parsed on this machine
      and never leaves it. A scanned PDF has no text layer, so it will be flagged rather than
      quietly summarised.</p>

    <div class="drop" id="drop" onclick="document.getElementById('picker').click()">
      <div class="big">Drop files here, or click to choose</div>
      <p class="small">PDF · PPTX · DOCX — up to 30 MB each</p>
    </div>
    <input id="picker" type="file" accept=".pdf,.pptx,.docx" multiple hidden>

    <div class="files" id="files"></div>
    <div class="status" id="ustatus"></div>

    <div class="qfoot" style="margin-top:18px">
      <span class="small" id="usummary">No files yet.</span>
      <button class="btn" id="build" onclick="buildReport()" disabled>Build my report →</button>
    </div>
  </section>

  <!-- ------------------------------------------------------------ report -->
  <section id="report" hidden>
    <div class="panel" id="reportbar" hidden>
      <div class="eyebrow">Step 3 · your report</div>
      <div style="display:flex;gap:12px;align-items:center;justify-content:space-between;
            flex-wrap:wrap">
        <div>
          <h2 style="margin:0 0 4px" id="rhead">Your report is ready</h2>
          <p class="small" style="margin:0" id="rmeta"></p>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn ghost" onclick="exportAs('md', this)">Download Markdown</button>
          <button class="btn" onclick="exportAs('pdf', this)">Download PDF</button>
        </div>
      </div>
    </div>
    <div id="rbody"></div>
  </section>

  <footer>
    <p>Same extracted sentences and page references for every preference — only the order and
      the emphasis change. No model is called: nothing here is paraphrased or generated.<br>
      <a href="http://localhost:8787/">Open the Robotics 1 atlas →</a></p>
  </footer>
</div>

<div id="toast"></div>
<script id="d-vark" type="application/json">__VARK__</script>
<script>
"use strict";

const VARK = JSON.parse(document.getElementById('d-vark').textContent);
const STORE = 'fma.vark.v1';
const MAXBYTES = 30 * 1024 * 1024;

const S = { sid: null, files: [], answers: null, report: null, busy: false };

/* ------------------------------------------------------------------ utils */
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const kb = n => n > 1024 * 1024 ? (n / 1024 / 1024).toFixed(1) + ' MB'
                                 : Math.max(1, Math.round(n / 1024)) + ' KB';

function toast(msg, ms) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('on');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove('on'), ms || 2200);
}

/* Tab routing. The hash is the only history entry, so reload keeps the screen. */
function go(name) {
  ['quiz', 'result', 'material', 'report'].forEach(id => {
    $(id).hidden = id !== name;
  });
  document.querySelectorAll('nav.tabs a').forEach(a => {
    const t = a.dataset.tab;
    a.classList.toggle('on', t === name ||
      (name === 'result' && t === 'quiz') ||
      (name === 'report' && t === 'material'));
  });
  location.hash = name === 'result' ? 'preference' : name;
  /* instant, not smooth: a report can be long, and a mid-scroll capture is a bug report */
  window.scrollTo(0, 0);
}

/* ------------------------------------------------------------- quiz state */
function loadSaved() {
  try {
    const raw = localStorage.getItem(STORE);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed.answers) || parsed.answers.length !== VARK.length) return null;
    return parsed;
  } catch (e) { return null; }
}

function save(answers) {
  try { localStorage.setItem(STORE, JSON.stringify({answers: answers, saved: Date.now()})); }
  catch (e) { toast('Could not save the preference in this browser'); }
}

/* The scorer. Four counters, one per letter; ties are reported as ties. */
function score(answers) {
  const counts = {};
  VARK.letters.forEach(l => { counts[l] = 0; });
  answers.forEach((choice, i) => {
    const letter = VARK.questions[i].options[choice].letter;
    counts[letter] += 1;
  });
  return counts;
}

function topLetters(counts) {
  const best = Math.max.apply(null, VARK.letters.map(l => counts[l]));
  const top = VARK.letters.filter(l => counts[l] === best);
  const rest = Math.max.apply(null,
    VARK.letters.filter(l => top.indexOf(l) === -1).map(l => counts[l]));
  return {top: top, best: best, second: rest};
}

/* ------------------------------------------------------------------- quiz */
let QANS = [];
let QSTEP = 0;

function renderQuestion() {
  const q = VARK.questions[QSTEP];
  $('qcount').textContent = QSTEP + 1;
  $('qtotal').textContent = VARK.length;
  $('qprog').style.width = ((QSTEP) / VARK.length * 100).toFixed(1) + '%';
  $('qstem').textContent = q.stem;
  $('qopts').innerHTML = q.options.map((o, i) =>
    `<button class="opt" onclick="quizAnswer(${i})">
       <span class="n">${i + 1}</span><span>${esc(o.label)}</span>
     </button>`).join('');
  $('qback').style.visibility = QSTEP === 0 ? 'hidden' : 'visible';
  $('qshort').textContent = VARK.short;
}

function quizAnswer(i) {
  QANS[QSTEP] = i;
  if (QSTEP < VARK.length - 1) { QSTEP += 1; renderQuestion(); return; }
  const answers = QANS.slice();
  save(answers);
  S.answers = answers;
  showResult(answers);
}

function quizBack() {
  if (QSTEP === 0) return;
  QSTEP -= 1;
  renderQuestion();
}

function quizRetake() {
  try { localStorage.removeItem(STORE); } catch (e) {}
  S.answers = null;
  QANS = [];
  QSTEP = 0;
  renderQuestion();
  go('quiz');
}

function showResult(answers) {
  const counts = score(answers);
  const t = topLetters(counts);
  const names = t.top.map(l => VARK.names[l]);
  const label = (t.top.length > 1 ? 'Multimodal: ' : '') + names.join(' + ');
  const hints = t.top.map(l => VARK.hints[l]).join(' · ');
  const mm = t.top.length > 1 || (t.second === t.best - 1);

  $('rname').textContent = label;
  $('rquad').textContent = hints;
  $('rbars').innerHTML = VARK.letters.map(l => {
    const pct = (counts[l] / VARK.length) * 100;
    return `<div class="bar ${t.top.indexOf(l) !== -1 ? 'on' : ''}">
      <div class="l">${esc(VARK.names[l])}</div>
      <div class="v">${counts[l]}<span class="small">/${VARK.length}</span></div>
      <div class="track"><i style="width:${pct.toFixed(1)}%"></i></div>
    </div>`;
  }).join('');
  $('rblurb').textContent = mm
    ? 'Your counts are close together, which is common. The report will lead with the first '
      + 'letter but keep the others present — read the shape as a lean, not a box.'
    : 'The report puts the material in this order first, and keeps the rest available. '
      + 'The same sentences are used either way.';
  $('rcaveat').textContent = VARK.caveat;
  go('result');
}

/* ----------------------------------------------------------------- upload */
function bindDrop() {
  const drop = $('drop');
  ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => {
    e.preventDefault(); drop.classList.add('hot');
  }));
  ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => {
    e.preventDefault(); drop.classList.remove('hot');
  }));
  drop.addEventListener('drop', e => {
    Array.from(e.dataTransfer.files || []).forEach(upload);
  });
  $('picker').addEventListener('change', e => {
    Array.from(e.target.files || []).forEach(upload);
    e.target.value = '';
  });
}

async function upload(file) {
  const ok = /\.(pdf|pptx|docx)$/i.test(file.name);
  if (!ok) { toast('Only PDF, PPTX and DOCX are read'); return; }
  if (file.size > MAXBYTES) { toast('That file is over 30 MB'); return; }
  if (S.busy) { toast('One file at a time'); return; }

  S.busy = true;
  $('ustatus').textContent = 'Reading ' + file.name + '…';
  try {
    const url = '/api/upload?name=' + encodeURIComponent(file.name)
      + (S.sid ? '&sid=' + encodeURIComponent(S.sid) : '');
    const res = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/octet-stream'},
      body: file
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
    S.sid = data.sid;
    S.files.push(data.file);
    if (data.file.scanned) {
      toast('No text layer in that PDF — only its images can be used', 4200);
    }
    renderFiles();
    $('ustatus').textContent = '';
  } catch (err) {
    $('ustatus').textContent = 'Could not read ' + file.name + ': ' + err.message;
  } finally {
    S.busy = false;
  }
}

function renderFiles() {
  $('files').innerHTML = S.files.map((f, i) => `
    <div class="file">
      <div style="min-width:0">
        <div class="name">${esc(f.name)}</div>
        <div class="meta">${esc(f.kind.toUpperCase())} · ${f.pages} page/slide ·
          ${f.sections} section(s) · ${f.figures} figure(s)${f.scanned ? ' · no text layer' : ''}</div>
      </div>
      <button class="x" title="Remove" onclick="removeFile(${i})">×</button>
    </div>`).join('');

  const n = S.files.length;
  $('build').disabled = n === 0 || !S.answers;
  $('usummary').textContent = n === 0 ? 'No files yet.'
    : n + ' file(s) ready' + (S.answers ? '' : ' — take the preference quiz first');
}

function removeFile(i) {
  S.files.splice(i, 1);
  renderFiles();
  $('reportbar').hidden = true;
  $('rbody').innerHTML = '';
}

/* ----------------------------------------------------------------- report */
async function buildReport() {
  if (!S.files.length || !S.answers) return;
  const btn = $('build');
  btn.disabled = true;
  const was = btn.textContent;
  btn.textContent = 'Building…';
  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sid: S.sid, answers: S.answers})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
    S.report = data;
    $('rbody').innerHTML = data.html;
    $('rmeta').textContent = data.summary;
    $('rhead').textContent = 'Report for ' + data.label;
    $('reportbar').hidden = false;
    go('report');
    if (!data.figures && data.wants === 'V') {
      toast('No figures were found in these files; the page-render fallback is shown', 4000);
    }
  } catch (err) {
    toast('Could not build the report: ' + err.message, 5000);
  } finally {
    btn.textContent = was;
    btn.disabled = false;
  }
}

async function exportAs(fmt, btn) {
  if (!S.report) return;
  const was = btn.textContent;
  btn.textContent = 'Preparing…';
  btn.disabled = true;
  try {
    const res = await fetch('/api/export', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sid: S.sid, answers: S.answers, fmt: fmt})
    });
    if (!res.ok) {
      let msg = 'HTTP ' + res.status;
      try { msg = (await res.json()).error || msg; } catch (e) {}
      throw new Error(msg);
    }
    const blob = await res.blob();
    const name = (res.headers.get('Content-Disposition') || '')
      .match(/filename="([^"]+)"/);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name ? name[1] : ('study-report.' + fmt);
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  } catch (err) {
    toast('Export failed: ' + err.message, 5000);
  } finally {
    btn.textContent = was;
    btn.disabled = false;
  }
}

/* ------------------------------------------------------------------ speech */
function speak(btn) {
  const p = btn.closest('.say');
  if (!p) return;
  const text = p.querySelector('p').getAttribute('data-say') || p.querySelector('p').textContent;
  if (!('speechSynthesis' in window)) { toast('This browser has no speech synthesiser'); return; }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.98;
  u.onstart = () => { btn.textContent = 'Speaking…'; };
  u.onend = () => { btn.textContent = 'Listen'; };
  window.speechSynthesis.speak(u);
}

let SPEAKING = false;
function speakAll() {
  if (!('speechSynthesis' in window)) { toast('This browser has no speech synthesiser'); return; }
  if (SPEAKING) { window.speechSynthesis.cancel(); SPEAKING = false; return; }
  const blocks = Array.from(document.querySelectorAll('.say p[data-say]'));
  if (!blocks.length) return;
  SPEAKING = true;
  window.speechSynthesis.cancel();
  blocks.slice(0, -1).forEach(p => {
    const u = new SpeechSynthesisUtterance(p.getAttribute('data-say'));
    u.rate = 0.98;
    window.speechSynthesis.speak(u);
  });
  const btn = document.querySelector('.sayall');
  if (btn) btn.textContent = 'Stop';
  const last = blocks[blocks.length - 1];
  const done = () => { SPEAKING = false; if (btn) btn.textContent = 'Listen to everything'; };
  /* the last real utterance carries the completion callback; a silent one is
     not guaranteed to fire onend in every engine */
  const probe = new SpeechSynthesisUtterance(last.getAttribute('data-say') || ' ');
  probe.rate = 0.98;
  probe.onend = done;
  probe.onerror = done;
  window.speechSynthesis.speak(probe);
}

/* --------------------------------------------------------------- keyboard */
document.addEventListener('keydown', ev => {
  if (ev.target && /^(INPUT|TEXTAREA|SELECT)$/.test(ev.target.tagName)) return;
  if (location.hash !== '#quiz' && location.hash !== '') return;
  if (ev.key >= '1' && ev.key <= String(VARK.questions[QSTEP].options.length)) {
    ev.preventDefault();
    quizAnswer(Number(ev.key) - 1);
  } else if (ev.key === 'ArrowLeft' || ev.key === 'Backspace') {
    ev.preventDefault();
    quizBack();
  }
});

/* ------------------------------------------------------------------- boot */
function boot() {
  bindDrop();
  renderFiles();
  const saved = loadSaved();
  if (saved) {
    S.answers = saved.answers;
    showResult(saved.answers);
    if (saved.answers) renderFiles();
    return;
  }
  renderQuestion();
  go('quiz');
}

document.addEventListener('DOMContentLoaded', boot);
</script>
</body>
</html>
"""


def page() -> str:
    """The Studio page, with the quiz inlined as data rather than re-written."""
    payload = json.dumps(vark.payload(), ensure_ascii=False)
    # `</script>` inside a JSON string would close the tag early.
    safe = payload.replace("</", "<\\/")
    return PAGE.replace("__VARK__", safe)


def caveat() -> str:
    return vark.CAVEAT
