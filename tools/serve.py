#!/usr/bin/env python3
"""Dev server for the vacuum models: serves the copy you actually just edited,
and reloads the browser tab whenever it changes.

Why this exists
---------------
Claude Code sessions run inside a git worktree under ``.claude/worktrees/<branch>/``
and edit the copy that lives there. A ``file://`` tab opened on the repo root is
therefore looking at a *different file*, not a stale cache of the same one — no
amount of reloading will ever show the new work.

This server scans the repo root and every worktree, serves whichever copy of the
model was modified most recently, and injects a small live-reload script into the
HTML on the way out. The model files themselves are never touched, so they stay
self-contained and portable (the injected script exists only in the served bytes,
and is inert on any host other than localhost).

Usage
-----
    python3 tools/serve.py                    # newest copy of the default model
    python3 tools/serve.py --main             # force the repo-root copy
    python3 tools/serve.py --dir <path>       # force a specific directory
    python3 tools/serve.py --file other.html  # watch a different model
    python3 tools/serve.py --port 8123
"""

import argparse
import json
import subprocess
import sys
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

DEFAULT_MODEL = "bottleneck_pumpdown.html"
DEFAULT_PORT = 8123
HERE = Path(__file__).resolve().parent


# ---------------- worktree discovery ----------------

def repo_root():
    """The *main* worktree root, even when this script runs from a linked worktree."""
    out = subprocess.run(
        ["git", "-C", str(HERE), "rev-parse", "--git-common-dir"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return HERE.parent
    common = Path(out.stdout.strip())
    if not common.is_absolute():
        common = (HERE / common).resolve()
    return common.parent


def git(directory, argv):
    out = subprocess.run(["git", "-C", str(directory)] + argv, capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else ""


def branch_of(directory):
    return git(directory, ["rev-parse", "--abbrev-ref", "HEAD"]) or "?"


def candidates(root, model):
    """Every directory holding a copy of `model`, most-recent work first.

    Ranking by file mtime alone is wrong here: creating a worktree stamps every
    checked-out file with the current time, so a brand-new worktree holding the
    *oldest* content looks like the newest edit. So an unmodified copy is ranked
    by the last commit that touched it, and only a copy with uncommitted changes
    is ranked by its mtime.
    """
    dirs = [root]
    worktrees = root / ".claude" / "worktrees"
    if worktrees.is_dir():
        dirs += sorted(p for p in worktrees.iterdir() if p.is_dir())

    found = []
    for d in dirs:
        f = d / model
        if not f.is_file():
            continue
        mtime = f.stat().st_mtime
        if git(d, ["status", "--porcelain", "--", model]):
            rank, why = mtime, "uncommitted edit"
        else:
            committed = git(d, ["log", "-1", "--format=%ct", "--", model])
            rank = float(committed) if committed else mtime
            why = "committed"
        found.append({
            "dir": d,
            "mtime": mtime,
            "rank": rank,
            "why": why,
            "branch": "main (repo root)" if d == root else branch_of(d),
        })
    found.sort(key=lambda c: c["rank"], reverse=True)
    return found


def clock(ts):
    return time.strftime("%H:%M:%S", time.localtime(ts))


def stamp(ts):
    return time.strftime("%b %d %H:%M", time.localtime(ts))


# ---------------- injected live-reload client ----------------
# Inert unless served from localhost, so a copy saved from the browser or opened
# with file:// behaves exactly like the untouched model file.

LIVE_RELOAD_JS = r"""
<script>
(function () {
  if (!/^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname)) return;

  var FILE = location.pathname, POLL = 700, KEY = "__dev_state:" + FILE;
  var known = null, misses = 0;

  var badge = document.createElement("div");
  badge.style.cssText =
    "position:fixed;left:10px;bottom:10px;z-index:2147483000;pointer-events:none;" +
    "font:11px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace;padding:5px 9px;" +
    "border-radius:7px;white-space:pre;opacity:.7;transition:opacity .15s,color .15s;" +
    "background:var(--surface-1,#fff);color:var(--text-2,#555);" +
    "border:1px solid var(--border,rgba(0,0,0,.15));box-shadow:0 1px 3px rgba(0,0,0,.12);";
  document.body.appendChild(badge);

  function paint(d) {
    if (!d) {
      badge.textContent = "○ serve.py not responding";
      badge.style.opacity = ".45";
      return;
    }
    badge.style.opacity = d.newer ? "1" : ".7";
    badge.style.color = d.newer ? "#b26a00" : "var(--text-2,#555)";
    badge.style.borderColor = d.newer ? "#b26a00" : "var(--border,rgba(0,0,0,.15))";
    badge.textContent = d.newer
      ? "▲ " + d.branch + " · " + d.time +
        "\nnewer copy on " + d.newer.branch + " (" + d.newer.time + ") — restart serve.py"
      : "● " + d.branch + " · " + d.time;
  }

  // Keep slider/checkbox positions across an auto-reload so an edit doesn't
  // reset the run you were looking at. Only written immediately before a reload.
  function controls() {
    return document.querySelectorAll("input, select, textarea");
  }
  function keyFor(el, i) { return el.id || el.name || ("#" + i); }

  function snapshot() {
    var s = {};
    controls().forEach(function (el, i) {
      s[keyFor(el, i)] = (el.type === "checkbox" || el.type === "radio") ? el.checked : el.value;
    });
    try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {}
  }

  function restore() {
    var raw = null;
    try { raw = sessionStorage.getItem(KEY); sessionStorage.removeItem(KEY); } catch (e) {}
    if (!raw) return;
    var s; try { s = JSON.parse(raw); } catch (e) { return; }
    controls().forEach(function (el, i) {
      var k = keyFor(el, i);
      if (!(k in s)) return;
      if (el.type === "checkbox" || el.type === "radio") el.checked = s[k];
      else el.value = s[k];
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  function poll() {
    fetch("/__dev?f=" + encodeURIComponent(FILE), { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        misses = 0;
        if (known === null) known = d.mtime;
        else if (d.mtime !== known) { snapshot(); location.reload(); return; }
        paint(d);
        setTimeout(poll, POLL);
      })
      .catch(function () {
        if (++misses > 2) paint(null);
        setTimeout(poll, POLL);
      });
  }

  restore();
  poll();
})();
</script>
"""


# ---------------- handler ----------------

class DevHandler(SimpleHTTPRequestHandler):
    root = None       # main repo root
    model = None      # watched filename
    all_copies = None # callable -> candidate list

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        if self.path.startswith("/__dev"):
            return  # the poll would drown out everything else
        super().log_message(fmt, *args)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/__dev":
            return self.dev_status()
        if path == "/" and (Path(self.directory) / self.model).is_file():
            self.send_response(302)
            self.send_header("Location", "/" + self.model)
            self.end_headers()
            return
        target = self.resolved(unquote(path))
        if target is not None and target.is_file() and target.suffix.lower() in (".html", ".htm"):
            return self.serve_html(target)
        super().do_GET()

    def resolved(self, rel):
        """Map a URL path to a file inside the served directory, or None."""
        served = Path(self.directory).resolve()
        try:
            target = (served / rel.lstrip("/")).resolve()
            target.relative_to(served)
        except (ValueError, OSError):
            return None
        return target

    def serve_html(self, target):
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return super().do_GET()
        if "</body>" in text:
            text = text.replace("</body>", LIVE_RELOAD_JS + "</body>", 1)
        else:
            text += LIVE_RELOAD_JS
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def dev_status(self):
        query = parse_qs(urlparse(self.path).query)
        rel = unquote(query.get("f", [""])[0]).lstrip("/") or self.model
        target = self.resolved(rel)
        if target is None or not target.is_file():
            self.send_error(404, "not served from here")
            return

        served = Path(self.directory).resolve()
        mtime = target.stat().st_mtime
        payload = {
            "file": rel,
            "mtime": mtime,
            "time": clock(mtime),
            "branch": "main (repo root)" if served == self.root.resolve() else branch_of(served),
            "dir": str(served),
            "newer": None,
        }

        # Did another worktree get newer work than the one we serve? This is the
        # failure mode the server exists to make visible: a second Claude session
        # branching off and editing a copy nobody is looking at.
        copies = self.all_copies(rel)
        mine = next((c for c in copies if c["dir"].resolve() == served), None)
        my_rank = mine["rank"] if mine else mtime
        for other in copies:
            if other["dir"].resolve() == served:
                continue
            if other["rank"] > my_rank + 1.0:
                payload["newer"] = {
                    "branch": other["branch"],
                    "time": stamp(other["rank"]),
                    "dir": str(other["dir"]),
                }
                break

        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------- entry point ----------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=DEFAULT_MODEL, help="model to watch (default: %(default)s)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="default: %(default)s")
    ap.add_argument("--dir", help="serve this directory instead of auto-picking")
    ap.add_argument("--main", action="store_true", help="serve the repo root, not a worktree")
    args = ap.parse_args(argv)

    root = repo_root()
    found = candidates(root, args.file)
    if not found:
        sys.exit("no copy of %s found under %s" % (args.file, root))

    if args.dir:
        served = Path(args.dir).resolve()
        if not (served / args.file).is_file():
            sys.exit("%s does not contain %s" % (served, args.file))
        chosen = next((c for c in found if c["dir"].resolve() == served),
                      {"dir": served, "mtime": (served / args.file).stat().st_mtime,
                       "branch": branch_of(served)})
    elif args.main:
        chosen = next((c for c in found if c["dir"] == root), None)
        if chosen is None:
            sys.exit("repo root has no %s" % args.file)
    else:
        chosen = found[0]

    DevHandler.root = root
    DevHandler.model = args.file
    DevHandler.all_copies = staticmethod(lambda f=None: candidates(root, f or args.file))

    url = "http://127.0.0.1:%d/%s" % (args.port, args.file)
    print("vacuum-models dev server")
    print("  serving   %s" % chosen["dir"])
    print("  branch    %s  (%s %s)" % (chosen["branch"], chosen.get("why", "?"),
                                       stamp(chosen.get("rank", chosen["mtime"]))))
    print("  url       %s" % url)
    print("  watching  %s — the tab reloads itself when this file changes" % args.file)
    others = [c for c in found if c["dir"] != chosen["dir"]]
    if others:
        print("  other copies (not served):")
        for c in others:
            print("    %s  %-14s %s" % (stamp(c["rank"]), c["why"], c["branch"]))
    print(flush=True)

    handler = partial(DevHandler, directory=str(chosen["dir"]))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
