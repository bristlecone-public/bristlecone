#!/usr/bin/env python3
"""Wrap the masthead fragment into a standalone document at web/public/index.html.

The masthead was authored for the Artifact publishing skeleton, which supplies
<!doctype>, <html>, <head> and <body> automatically — so the fragment starts at
<title> and has no document wrapper. Serving it at the apex needs a real
document, which this adds: the charset and viewport the skeleton provided, plus
a favicon so the apex does not answer /favicon.ico with a 404.

    python tools/build_masthead.py <fragment.html>

Everything else is copied verbatim; the fragment's own <style> paints body, so
no reset is needed.

web/public/index.html is now THE canonical copy — edit it directly. This script
was the one-time wrapper and is kept only to document how the document was
produced; re-running it against an old fragment would clobber later edits, and
the apex copy has already diverged (the hero's list of sources was corrected
after the wrap). To refresh the Artifact instead, strip the wrapper back off
web/public/index.html.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "public" / "index.html"

# A bristlecone, matching the Artifact's favicon.
FAVICON = (
    '<link rel="icon" href="data:image/svg+xml,'
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E"
    "%3Ctext y='14' font-size='14'%3E%F0%9F%8C%B2%3C/text%3E%3C/svg%3E\">"
)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    src = Path(sys.argv[1])
    text = src.read_text(encoding="utf-8")

    marker = "</style>"
    i = text.find(marker)
    if i == -1:
        raise SystemExit("no </style> found — cannot split head from body")
    head = text[: i + len(marker)]
    body = text[i + len(marker):].lstrip("\n")

    if "<!doctype" in text.lower():
        raise SystemExit("fragment already looks like a full document")

    doc = (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f"{FAVICON}\n"
        f"{head}\n"
        "</head>\n"
        "<body>\n"
        f"{body}"
        "</body>\n"
        "</html>\n"
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(doc)/1024:.1f} KB)")


if __name__ == "__main__":
    main()
