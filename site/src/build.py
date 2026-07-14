"""Build public/index.html: terminal page + frame assets as a self-extracting bundle.

Inputs (all in src/): terminal-src.html (the editable page), loader.js (the
bundler runtime), frames-manifest.json (the four CF0..CF3 frame assets,
gzip+base64, extracted once from the original Frosted Terminal export).
Run from the repo root:  python src/build.py
"""

import json
from pathlib import Path

SRC = Path(__file__).parent
OUT = SRC.parent / "public" / "index.html"

loader = (SRC / "loader.js").read_text(encoding="utf-8")
manifest = json.loads((SRC / "frames-manifest.json").read_text(encoding="utf-8"))
body = (SRC / "terminal-src.html").read_text(encoding="utf-8")

# hosted build: PAPER 01 links to the co-hosted research page
body = body.replace("https://taylor-hobbs.github.io/asx/", "research/")

cut = body.index("</title>") + len("</title>")
title, rest = body[:cut], body[cut:]
cf_tags = "\n".join(f'<script src="{u}"></script>' for u in manifest)
rest = rest.replace("<!--CFSCRIPTS-->", cf_tags)
template = (
    '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    + title
    + "\n</head>\n<body>"
    + rest
    + "\n</body>\n</html>"
)

esc = lambda s: s.replace("</", "<\\/")  # noqa: E731
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(
    '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    "<title>ASX Alpha — Forward Paper Terminal</title>\n"
    "<style>body{background:#000;margin:0}"
    "#__bundler_loading{position:fixed;bottom:20px;right:20px;"
    "font:13px/1.4 ui-monospace,Menlo,monospace;color:rgba(243,241,234,.6);"
    "background:#0a0b0d;padding:8px 14px;border-radius:8px;z-index:10000}</style>\n"
    "</head>\n<body>\n"
    '<div id="__bundler_loading">Unpacking…</div>\n'
    "<script>" + loader + "</script>\n"
    '<script type="__bundler/manifest">' + esc(json.dumps(manifest)) + "</script>\n"
    '<script type="__bundler/template">' + esc(json.dumps(template)) + "</script>\n"
    "</body>\n</html>\n",
    encoding="utf-8",
)
print(f"built {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
