"""
preferences.py - the "brain" that learns what news you care about.

It keeps a weight (a number, starting at 1.0) for every topic and keyword.
Stories are scored against these weights, and your thumbs up/down feedback
nudges them over time. This is a small ONLINE-LEARNING loop: no heavy ML,
just a running score per topic that drifts toward your taste with each vote.
"""

import json
from pathlib import Path

PREFS_PATH = Path(__file__).parent / "preferences.json"

DEFAULT_PREFS = {
    "category_weights": {
        "ai": 1.0,
        "technology": 1.0,
        "current_affairs": 1.0,
        "sports": 1.0,
    },
    "keyword_weights": {},      # e.g. {"cricket": 1.4, "layoffs": 0.6}
    "learning_rate": 0.15,      # how strongly each vote moves a weight
    "last_feedback_row": 0,     # how many feedback rows we've already learned from
}

MIN_WEIGHT = 0.1                # weights are clamped so nothing goes to zero/infinity
MAX_WEIGHT = 3.0


def load_preferences():
    """Read preferences.json, or start fresh with defaults."""
    if PREFS_PATH.exists():
        with open(PREFS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(json.dumps(DEFAULT_PREFS))  # a clean copy


def save_preferences(prefs):
    with open(PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2, ensure_ascii=False)


def _clamp(value):
    return max(MIN_WEIGHT, min(MAX_WEIGHT, value))


def score_story(story, prefs):
    """Higher score = more likely to match your taste."""
    category = story.get("category", "").lower()
    base = prefs["category_weights"].get(category, 1.0)

    # Blend in any keywords we've already learned an opinion about.
    kw_scores = [prefs["keyword_weights"].get(kw.lower(), 1.0)
                 for kw in story.get("keywords", [])]
    kw_factor = sum(kw_scores) / len(kw_scores) if kw_scores else 1.0

    return base * kw_factor


def apply_feedback(prefs, feedback_rows):
    """
    Nudge weights based on new thumbs up/down votes.

    feedback_rows: list of dicts like
        {"category": "sports", "keywords": ["cricket"], "vote": "up"}
    Only rows we haven't processed before are applied (tracked by index),
    so re-reading the whole log every day never double-counts a vote.
    """
    lr = prefs["learning_rate"]
    already = prefs.get("last_feedback_row", 0)
    new_rows = feedback_rows[already:]

    for row in new_rows:
        direction = 1.0 if row.get("vote") == "up" else -1.0

        cat = row.get("category", "").lower()
        if cat in prefs["category_weights"]:
            prefs["category_weights"][cat] = _clamp(
                prefs["category_weights"][cat] + lr * direction
            )

        for kw in row.get("keywords", []):
            kw = kw.lower()
            current = prefs["keyword_weights"].get(kw, 1.0)
            prefs["keyword_weights"][kw] = _clamp(current + lr * direction)

    prefs["last_feedback_row"] = len(feedback_rows)
    return prefs
