"""
digest.py - main entry point.

Daily pipeline:
  1. Learn from yesterday's thumbs up/down feedback.
  2. Ask Claude (with live web search) for today's news as structured JSON.
  3. Score & rank every story against your learned preferences.
  4. Build an HTML email where each story has a 👍 / 👎 link.
  5. Send it to your inbox via Gmail.

Runs automatically every morning via GitHub Actions
(see .github/workflows/daily.yml).
"""

import os
import json
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from google import genai
from google.genai import types

from preferences import (
    load_preferences, save_preferences,
    score_story, apply_feedback,
)
from dedup import deduplicate
from archive import save_digest

# ---- config comes from environment variables, never hard-coded secrets ----
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", GMAIL_ADDRESS)
FEEDBACK_SHEET_CSV_URL = os.environ.get("FEEDBACK_SHEET_CSV_URL", "")
FEEDBACK_APPS_SCRIPT_URL = os.environ.get("FEEDBACK_APPS_SCRIPT_URL", "")

STORIES_PER_CATEGORY = 3
CATEGORIES = ["ai", "technology", "current_affairs", "sports"]

LABELS = {
    "ai": "🤖 AI",
    "technology": "💻 Technology",
    "current_affairs": "🇮🇳 Current Affairs",
    "sports": "🏏 Sports",
}


# ---------------------------------------------------------------- feedback in
def fetch_feedback():
    """Read the 👍/👎 log from the published Google Sheet (as CSV)."""
    if not FEEDBACK_SHEET_CSV_URL:
        return []
    try:
        resp = requests.get(FEEDBACK_SHEET_CSV_URL, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[warn] could not read feedback sheet: {e}")
        return []

    rows = []
    for line in resp.text.strip().splitlines()[1:]:   # skip header row
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        # sheet columns: timestamp, category, keywords(;-separated), vote
        _, category, keywords, vote = parts[0], parts[1], parts[2], parts[3]
        rows.append({
            "category": category,
            "keywords": [k for k in keywords.split(";") if k],
            "vote": vote,
        })
    return rows


# ------------------------------------------------------------------- news in
def get_news():
    """Ask Gemini for today's news as structured JSON, using Google Search grounding.

    Uses the free tier (gemini-flash-latest, an alias that always points to the
    current Flash model, so it won't break when Google rotates versions).
    """
    client = genai.Client(api_key=GEMINI_API_KEY)
    today = datetime.date.today().strftime("%A, %d %B %Y")

    prompt = f"""Search for today's most important news ({today}) for a reader in India.
Return ONLY valid JSON (no prose, no markdown fences) in exactly this shape:
{{
  "stories": [
    {{
      "headline": "one crisp line",
      "summary": "one short factual sentence, no fluff",
      "category": "ai" | "technology" | "current_affairs" | "sports",
      "keywords": ["lowercase", "topic", "tags"]
    }}
  ]
}}
Give 4-5 stories per category. Keep it factual and current.
Sports should lean cricket. Current affairs should lean India."""

    resp = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    text = (resp.text or "").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        return json.loads(text).get("stories", [])
    except json.JSONDecodeError:
        print("[error] Gemini did not return clean JSON. First 500 chars:")
        print(text[:500])
        return []


# --------------------------------------------------------------------- rank
def rank_stories(stories):
    """Bucket the (already scored) stories, keeping the top few per category."""
    ranked = {}
    for cat in CATEGORIES:
        in_cat = [s for s in stories if s.get("category", "").lower() == cat]
        in_cat.sort(key=lambda s: s.get("_score", 0), reverse=True)
        ranked[cat] = in_cat[:STORIES_PER_CATEGORY]
    return ranked


# -------------------------------------------------------------------- email
def feedback_link(category, keywords, vote):
    if not FEEDBACK_APPS_SCRIPT_URL:
        return "#"
    kw = requests.utils.quote(";".join(keywords))
    return f"{FEEDBACK_APPS_SCRIPT_URL}?category={category}&keywords={kw}&vote={vote}"


def build_email(ranked):
    today = datetime.date.today().strftime("%A, %d %B %Y")
    parts = [
        f"<h2 style='margin-bottom:4px'>📅 Daily Brief — {today}</h2>",
        "<p style='color:#777;margin-top:0'>Tap 👍 or 👎 on any story — "
        "tomorrow's brief learns from it.</p>",
    ]

    for cat in CATEGORIES:
        parts.append(f"<h3>{LABELS[cat]}</h3><ul style='padding-left:18px'>")
        for s in ranked.get(cat, []):
            up = feedback_link(cat, s.get("keywords", []), "up")
            down = feedback_link(cat, s.get("keywords", []), "down")
            src = (f" <span style='color:#888;font-size:12px'>· {s['sources']} sources</span>"
                   if s.get("sources", 1) > 1 else "")
            parts.append(
                f"<li style='margin-bottom:10px'><b>{s['headline']}</b>{src}<br>"
                f"<span style='color:#444'>{s['summary']}</span><br>"
                f"<a href='{up}' style='text-decoration:none'>👍</a>&nbsp;&nbsp;"
                f"<a href='{down}' style='text-decoration:none'>👎</a></li>"
            )
        parts.append("</ul>")

    return ("<div style='font-family:-apple-system,Segoe UI,sans-serif;"
            "max-width:640px;line-height:1.45'>" + "".join(parts) + "</div>")


def send_email(html):
    today = datetime.date.today().strftime("%d %b %Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📅 Your Daily Brief — {today}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print("[ok] email sent")


# --------------------------------------------------------------------- main
def main():
    prefs = load_preferences()

    # 1. Learn from yesterday's votes
    feedback = fetch_feedback()
    if feedback:
        prefs = apply_feedback(prefs, feedback)
        save_preferences(prefs)
        print(f"[ok] processed {len(feedback)} total feedback rows")

    # 2. Fetch today's news
    stories = get_news()
    if not stories:
        print("[error] no stories fetched; aborting")
        return

    # 3. Score, then merge stories about the same event (embeddings dedup)
    for s in stories:
        s["_score"] = score_story(s, prefs)
    stories = deduplicate(stories)
    ranked = rank_stories(stories)

    # 4. Save to the public archive (served by GitHub Pages)
    save_digest(ranked)

    # 5. Build + send the email
    send_email(build_email(ranked))


if __name__ == "__main__":
    main()
