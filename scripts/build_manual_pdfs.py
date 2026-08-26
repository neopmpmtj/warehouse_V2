#!/usr/bin/env python3
"""Build PDFs for all CentCompras user manuals (docs/user-manuals/*.md -> *.pdf).

Uses python-markdown + WeasyPrint. Outputs one PDF per manual, same basename,
next to the .md source (docs/user-manuals/). Emoji that DejaVu cannot render
are mapped to plain text markers so the PDF has no tofu boxes. Internal
"xx-name.md" links are rewritten to "xx-name.pdf" so cross-manual links work
inside the PDF viewer (relative to the served /docs/user-manuals/ URL).

Usage:  python3 scripts/build_manual_pdfs.py [--out DIR]
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path

import markdown
from weasyprint import HTML

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("build_manual_pdfs")

REPO_ROOT = Path(__file__).resolve().parent.parent
MANUALS_DIR = REPO_ROOT / "docs" / "user-manuals"

# Emoji -> plain text (DejaVu has no colour emoji glyphs; keep PDFs clean).
EMOJI_MAP = {
    "✅": "[OK]",
    "❌": "[NO]",
    "💡": "Tip:",
    "📷": "[SCREENSHOT]",
}
EMOJI_RE = re.compile("|".join(re.escape(e) for e in EMOJI_MAP))

# Internal cross-manual links: "05-edge-cases-and-limits.md" -> ".pdf"
LINK_RE = re.compile(r"(?P<pre>\]\()(?P<name>[0-9]{2}-[a-z0-9-]+)\.md(?P<post>\))")


def emoji_to_text(text: str) -> str:
    return EMOJI_RE.sub(lambda m: EMOJI_MAP[m.group(0)], text)


def rewrite_links(html: str) -> str:
    return LINK_RE.sub(lambda m: m.group("pre") + m.group("name") + ".pdf" + m.group("post"), html)


PDF_CSS = """
@page {
    size: A4;
    margin: 18mm 16mm 20mm 16mm;
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-size: 8pt;
        color: #888;
    }
}
body {
    font-family: "DejaVu Sans", sans-serif;
    font-size: 10pt;
    line-height: 1.45;
    color: #1a1a1a;
}
h1 { font-size: 17pt; color: #1c4e80; border-bottom: 2px solid #2f78c4; padding-bottom: 4px; }
h2 { font-size: 13.5pt; color: #2f78c4; border-bottom: 1px solid #ccd6e0; padding-bottom: 3px; margin-top: 18px; }
h3 { font-size: 11.5pt; color: #333; margin-top: 14px; }
h4 { font-size: 10.5pt; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9pt; }
th, td { border: 1px solid #b8c2cc; padding: 4px 7px; text-align: left; vertical-align: top; }
th { background: #eef4fb; font-weight: bold; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.5pt; background: #f2f4f7; padding: 1px 3px; border-radius: 3px; }
pre { background: #f6f8fa; border: 1px solid #dde3ea; padding: 8px 10px; font-size: 8.5pt; white-space: pre-wrap; border-radius: 4px; }
pre code { background: none; padding: 0; }
img { max-width: 100%; }
blockquote { border-left: 3px solid #2f78c4; margin: 10px 0; padding: 4px 12px; color: #444; background: #f7fafd; }
blockquote code { background: #e9eef5; }
a { color: #2f78c4; text-decoration: none; }
hr { border: none; border-top: 1px solid #d5dbe2; margin: 16px 0; }
strong { font-weight: bold; }
"""


def build_one(md_path: Path, out_path: Path) -> int:
    """Convert one manual to PDF. Returns page count."""
    start = time.time()
    raw = md_path.read_text(encoding="utf-8")
    text = emoji_to_text(raw)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    body = rewrite_links(body)
    html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{PDF_CSS}</style></head><body>{body}</body></html>"
    doc = HTML(string=html, base_url=str(md_path.parent)).render()
    doc.write_pdf(str(out_path))
    pages = len(doc.pages)
    log.info("built %s -> %s (%d pages, %.1fs)", md_path.name, out_path.name, pages, time.time() - start)
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description="Build user-manual PDFs.")
    parser.add_argument("--out", type=Path, default=MANUALS_DIR, help="Output dir (default: docs/user-manuals)")
    parser.add_argument("--only", default=None, help="Build only one manual basename, e.g. 01-items")
    args = parser.parse_args()

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    manuals = sorted(MANUALS_DIR.glob("[0-9][0-9]-*.md"))
    if not manuals:
        log.error("no manuals found in %s", MANUALS_DIR)
        return 1

    total_pages = 0
    failures = 0
    for md in manuals:
        if args.only and md.stem != args.only:
            continue
        out = out_dir / (md.stem + ".pdf")
        try:
            total_pages += build_one(md, out)
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            log.exception("FAILED %s: %s", md.name, exc)

    log.info("done: %d manual(s), %d total pages, %d failure(s)", len(manuals), total_pages, failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
