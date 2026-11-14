"""Studio server: one command, one page, uploads that never leave the machine.

Design notes that matter:

* **Bound to 127.0.0.1.** This is a local tool. `--host` exists so a demo can be
  shown on a phone over a LAN, and it prints a warning when used.
* **Raw-body uploads, one file per request.** Python 3.13 removed `cgi`, and a
  hand-written multipart parser is a liability for a page that processes
  arbitrary files. The browser sends the bytes and the filename in the query.
* **Sessions are directories.** `data/uploads/<sid>/` holds the original file,
  the figures, and `doc.json` — the parse result. Analysis never re-parses, so
  the report is built from exactly what the upload produced.
* **Nothing is shared between sessions.** The sid is a random token; a request
  naming an unknown one gets 404 rather than a new directory.
"""

from __future__ import annotations

import json
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import studio, vark
from .studio_view import page as studio_page

ROOT = Path(__file__).resolve().parent
# Anchored to the repository, not the shell's cwd, so `./studio.sh` and
# `python -m atlas.cli studio` put uploads in the same place. Read on demand:
# a demo should not need a restart to pick up a CSS edit.
UPLOADS = ROOT.parent / "data" / "uploads"


def theme() -> str:
    return (ROOT / "theme.css").read_text(encoding="utf-8")

MAX_BYTES = 30 * 1024 * 1024
SID = re.compile(r"^[0-9a-f]{16}$")
SAFE = re.compile(r"[^A-Za-z0-9._ -]+")
KINDS = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


# ------------------------------------------------------------------ sessions


def session_dir(sid: str) -> Path:
    """Resolve a session id to a directory, refusing anything we did not issue."""
    if not SID.match(sid or ""):
        raise FileNotFoundError("bad session id")
    d = (UPLOADS / sid).resolve()
    if UPLOADS.resolve() not in d.parents:
        raise FileNotFoundError("bad session id")
    if not d.is_dir():
        raise FileNotFoundError("unknown session")
    return d


def new_session() -> tuple[str, Path]:
    sid = secrets.token_hex(8)
    d = UPLOADS / sid
    (d / "docs").mkdir(parents=True, exist_ok=True)
    return sid, d


def safe_name(name: str) -> str:
    """A filename we are willing to write to disk, with a known extension."""
    base = Path(unquote(name or "upload")).name
    base = SAFE.sub("_", base).strip(" ._-") or "upload"
    ext = Path(base).suffix.lower()
    if ext not in (".pdf", ".pptx", ".docx"):
        ext = ".pdf"
        base = Path(base).stem + ext
    if len(base) > 120:
        base = Path(base).stem[:100] + ext
    return base


def docs_of(d: Path) -> list[dict]:
    out = []
    for f in sorted((d / "docs").glob("*.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


def report_for(sid: str, answers) -> tuple[dict, dict]:
    d = session_dir(sid)
    seq = vark.decode(answers)
    if seq is None:
        raise ValueError("answers must be 12 indices, each 0-3")
    docs = docs_of(d)
    if not docs:
        raise ValueError("no files have been read in this session")
    profile = vark.profile(seq)
    return studio.analyse(docs, profile), profile


# ------------------------------------------------------------------- handler


class Handler(BaseHTTPRequestHandler):
    server_version = "Studio/1.0"

    # ---- helpers
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, obj: dict) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _error(self, code: int, msg: str) -> None:
        self._json(code, {"error": msg})

    def log_message(self, fmt: str, *args) -> None:  # quieter than the default
        if self.path.startswith("/api/"):
            sys.stderr.write("  %s %s\n" % (self.command, self.path.split("?")[0]))

    # ---- GET
    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = url.path

        if path in ("/", "/index.html"):
            self._send(200, studio_page().encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/theme.css":
            self._send(200, theme().encode("utf-8"), "text/css; charset=utf-8")
            return
        if path == "/api/health":
            self._json(200, {"ok": True, "tools": studio.available()})
            return
        if path.startswith("/media/"):
            self._media(path)
            return

        self._error(404, "not found")

    def _media(self, path: str) -> None:
        rel = path[len("/media/"):]
        sid, _, name = rel.partition("/")
        try:
            d = session_dir(sid)
        except FileNotFoundError:
            self._error(404, "unknown session")
            return
        target = (d / Path(name).name).resolve()
        if d not in target.parents or not target.is_file():
            self._error(404, "no such figure")
            return
        ctype = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp",
        }.get(target.suffix.lower(), "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)

    # ---- POST
    def do_POST(self) -> None:
        url = urlparse(self.path)
        try:
            if url.path == "/api/upload":
                self._upload(parse_qs(url.query))
            elif url.path == "/api/analyze":
                self._analyze()
            elif url.path == "/api/export":
                self._export()
            else:
                self._error(404, "not found")
        except FileNotFoundError as exc:
            self._error(404, str(exc))
        except ValueError as exc:
            self._error(400, str(exc))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # noqa: BLE001 - a local tool should say what broke
            sys.stderr.write("  error: %r\n" % (exc,))
            self._error(500, "internal error: %s" % exc)

    def _body(self, limit: int = MAX_BYTES) -> bytes:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("bad Content-Length")
        if n <= 0:
            raise ValueError("empty request body")
        if n > limit:
            # Refusing before reading leaves the client mid-write, and it sees a
            # broken pipe rather than the refusal. Drain what it is already
            # sending, bounded so a lying Content-Length cannot pin the thread.
            left = min(n, limit + (8 << 20))
            while left > 0:
                chunk = self.rfile.read(min(left, 1 << 20))
                if not chunk:
                    break
                left -= len(chunk)
            raise ValueError("file is larger than %d MB" % (limit // (1024 * 1024)))
        return self.rfile.read(n)

    def _upload(self, query: dict) -> None:
        name = (query.get("name") or ["upload"])[0]
        sid = (query.get("sid") or [""])[0]
        raw = self._body()

        if sid:
            d = session_dir(sid)
        else:
            sid, d = new_session()

        fname = safe_name(name)
        target = d / fname
        # two files with the same name in one session: keep both
        n = 1
        while target.exists():
            n += 1
            target = d / ("%s-%d%s" % (Path(fname).stem, n, Path(fname).suffix))
        target.write_bytes(raw)

        try:
            doc = studio.parse(target, d)
        except ValueError as exc:
            target.unlink(missing_ok=True)
            raise ValueError(str(exc))
        except Exception:
            target.unlink(missing_ok=True)
            raise ValueError("that file could not be parsed as %s" % target.suffix)

        doc["stored"] = target.name
        idx = len(list((d / "docs").glob("*.json"))) + 1
        (d / "docs" / ("%03d.json" % idx)).write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8"
        )

        self._json(200, {
            "sid": sid,
            "file": {
                "name": doc["name"],
                "kind": doc["kind"],
                "pages": doc["pages"],
                "sections": len(doc["sections"]),
                "figures": len(doc["figures"]),
                "scanned": doc.get("scanned", False),
            },
        })

    def _analyze(self) -> None:
        data = json.loads(self._body(1 << 20) or b"{}")
        sid = data.get("sid") or ""
        answers = data.get("answers")

        d = session_dir(sid)
        report, profile = report_for(sid, answers)
        html = studio.render(report, media_base="/media/%s/" % sid)
        t = report["totals"]
        summary = (
            "%d file(s) · %d page/slide · %d section(s) · %d definition(s) · %d figure(s)"
            % (t["files"], t["pages"], t["sections"], t["definitions"], t["figures"])
        )
        self._json(200, {
            "html": html,
            "label": profile["label"],
            "summary": summary,
            "wants": profile["dominant"],
            "figures": t["figures"],
            "totals": t,
        })

    def _export(self) -> None:
        data = json.loads(self._body(1 << 20) or b"{}")
        sid = data.get("sid") or ""
        fmt = (data.get("fmt") or "md").lower()
        report, profile = report_for(sid, data.get("answers"))
        d = session_dir(sid)

        stem = "study-report-%s" % (profile["dominant"].lower())
        if fmt == "md":
            body = studio.markdown(report).encode("utf-8")
            name = stem + ".md"
            ctype = "text/markdown; charset=utf-8"
        elif fmt == "json":
            body = json.dumps(report, indent=1, ensure_ascii=False).encode("utf-8")
            name = stem + ".json"
            ctype = "application/json; charset=utf-8"
        elif fmt == "pdf":
            body = self._pdf(report, d, profile)
            name = stem + ".pdf"
            ctype = "application/pdf"
        else:
            raise ValueError("fmt must be md, json or pdf")

        self._send(200, body, ctype, {
            "Content-Disposition": 'attachment; filename="%s"' % name,
        })

    def _pdf(self, report: dict, d: Path, profile: dict) -> bytes:
        candidates = studio.chrome_candidates()
        if not candidates:
            raise ValueError(
                "no Chrome found for PDF export; use the Markdown download instead"
            )

        title = "Study report — %s" % profile["label"]
        html = studio.print_html(report, title, media_base=d.as_uri() + "/")

        # Staging inside the session directory matters: a snap browser is confined
        # and cannot read /tmp, which is exactly the failure this replaces.
        stage = d / ".export"
        stage.mkdir(exist_ok=True)
        src = stage / "report.html"
        out = stage / "report.pdf"
        src.write_text(html, encoding="utf-8")
        out.unlink(missing_ok=True)

        last = ""
        try:
            for chrome in candidates:
                cmd = [
                    chrome, "--headless", "--disable-gpu", "--no-sandbox",
                    "--no-pdf-header-footer",
                    "--virtual-time-budget=8000",
                    "--print-to-pdf=%s" % out,
                    src.as_uri(),
                ]
                try:
                    run = subprocess.run(cmd, capture_output=True, timeout=120)
                    last = (run.stderr or b"").decode("utf-8", "replace")[-400:]
                except (OSError, subprocess.TimeoutExpired) as exc:
                    last = str(exc)
                    continue
                if out.is_file() and out.stat().st_size > 1024:
                    return out.read_bytes()
                out.unlink(missing_ok=True)
        finally:
            shutil.rmtree(stage, ignore_errors=True)

        raise ValueError(
            "PDF rendering produced no output (%s)" % (last.strip() or "no details")
        )


# --------------------------------------------------------------------- serve


def serve(host: str = "127.0.0.1", port: int = 8788, open_browser: bool = True) -> None:
    UPLOADS.mkdir(parents=True, exist_ok=True)
    tools = studio.available()
    missing = [k for k, v in tools.items() if not v]
    if "pdftotext" in missing:
        print("warning: poppler is not installed, so PDFs cannot be read.", file=sys.stderr)

    httpd = ThreadingHTTPServer((host, port), Handler)
    url = "http://%s:%d/" % (host, port)
    print("Studio is at %s" % url)
    if host not in ("127.0.0.1", "localhost"):
        print("warning: bound to %s, so anything on the network can reach this." % host,
              file=sys.stderr)
    print("Uploads stay in %s. Ctrl-C to stop." % UPLOADS.resolve())
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="studio", description="Failure-Mode Atlas Studio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--no-open", action="store_true", help="do not open a browser")
    args = ap.parse_args(argv)
    serve(args.host, args.port, not args.no_open)
    return 0


if __name__ == "__main__":
    sys.exit(main())
