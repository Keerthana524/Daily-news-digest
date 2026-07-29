"""
dedup.py - collapse stories about the same event into one.

Different sources report the same story with different wording. This uses a
small SENTENCE-EMBEDDING model that runs locally (no external API, no third
party) to turn each story into a vector, then merges stories whose vectors are
very similar (cosine similarity above a threshold). The best-scored story in a
group is kept as the representative, and it remembers how many stories merged
into it ('sources'), which the email and archive can show.

Why local embeddings? It keeps the whole project first-party, and clustering
by meaning rather than exact words is a genuinely better dedup than string
matching. Trade-off: the model download makes the first CI run slower.
"""

import numpy as np

_MODEL = None
SIMILARITY_THRESHOLD = 0.80    # 0-1; higher = only near-identical stories merge


def _model():
    """Load the embedding model once, lazily (keeps import cheap)."""
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def _cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def deduplicate(stories):
    """Return stories with near-duplicates merged, each tagged with a
    'sources' count of how many raw stories collapsed into it."""
    if len(stories) < 2:
        for s in stories:
            s.setdefault("sources", 1)
        return stories

    texts = [f"{s.get('headline', '')} {s.get('summary', '')}" for s in stories]
    embeddings = _model().encode(texts)

    clusters = []  # each: {"rep": story, "emb": vector, "count": int}
    for story, emb in zip(stories, embeddings):
        placed = False
        for c in clusters:
            if _cosine(emb, c["emb"]) >= SIMILARITY_THRESHOLD:
                c["count"] += 1
                # keep the higher-scored story as the group's representative
                if story.get("_score", 0) > c["rep"].get("_score", 0):
                    c["rep"], c["emb"] = story, emb
                placed = True
                break
        if not placed:
            clusters.append({"rep": story, "emb": emb, "count": 1})

    merged = []
    for c in clusters:
        c["rep"]["sources"] = c["count"]
        merged.append(c["rep"])

    print(f"[ok] dedup: {len(stories)} stories -> {len(merged)} unique events")
    return merged
