"""
archive.py - persist each day's digest into docs/ so GitHub Pages can serve a
public, searchable archive of every brief.

Two things are written per run:
  1. docs/archive/YYYY-MM-DD.html  - a readable page for that day
  2. docs/archive/index.json       - a compact search index the front page reads

GitHub Pages serves the docs/ folder, so the archive is live at
https://<username>.github.io/<repo>/ with zero hosting cost.
"""

import json
import html
import datetime
from pathlib import Path

DOCS = Path(__file__).parent / "docs"
ARCHIVE_DIR = DOCS / "archive"
INDEX_JSON = ARCHIVE_DIR / "index.json"

CATEGORIES = ["ai", "technology", "current_affairs", "sports"]
LABELS = {
    "ai": "🤖 AI",
    "technology": "💻 Technology",
    "current_affairs": "🇮🇳 Current Affairs",
    "sports": "🏏 Sports",
}

_FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500&"
          "family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@500;600&display=swap")


def _page_html(date_str, ranked):
    parts = [f"<a class='back' href='../index.html'>← all briefs</a>",
             f"<h1>📅 {date_str}</h1>"]
    for cat in CATEGORIES:
        items = ranked.get(cat, [])
        if not items:
            continue
        parts.append(f"<h2>{LABELS[cat]}</h2><ul>")
        for s in items:
            src = (f" <span class='src'>· {s['sources']} sources</span>"
                   if s.get("sources", 1) > 1 else "")
            parts.append(f"<li><b>{html.escape(s['headline'])}</b>{src}<br>"
                         f"{html.escape(s['summary'])}</li>")
        parts.append("</ul>")
    body = "".join(parts)
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>Brief · {date_str}</title>"
            f"<link href='{_FONTS}' rel='stylesheet'>"
            f"<link rel='stylesheet' href='../style.css'></head>"
            f"<body><main class='wrap brief'>{body}</main></body></html>")


def save_digest(ranked):
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()

    # 1. the readable per-day page
    (ARCHIVE_DIR / f"{today}.html").write_text(_page_html(today, ranked), encoding="utf-8")

    # 2. rebuild this day's entry in the search index
    index = []
    if INDEX_JSON.exists():
        index = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    index = [e for e in index if e["date"] != today]  # drop old copy if re-run

    all_stories = [s for cat in CATEGORIES for s in ranked.get(cat, [])]
    searchable = []
    for s in all_stories:
        searchable += [s["headline"], s["summary"]] + s.get("keywords", [])

    index.append({
        "date": today,
        "url": f"archive/{today}.html",
        "headlines": [s["headline"] for s in all_stories],
        "text": " ".join(searchable).lower(),   # what the search box matches against
    })
    index.sort(key=lambda e: e["date"], reverse=True)
    INDEX_JSON.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] archived {today} ({len(all_stories)} stories)")
