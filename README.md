# Personalized Daily News Digest

An automated daily email brief (AI, technology, current affairs, sports) that
**learns what I actually care about**, **merges stories about the same event**,
and **publishes a searchable public archive**.

- **Learns** — every story carries a 👍 / 👎 link; my votes nudge the ranking so
  topics I like rise and ones I ignore fade (a small online-learning loop).
- **Deduplicates** — a local sentence-embedding model clusters stories by
  *meaning*, so the same event reported by several sources collapses into one.
- **Archives** — each brief is saved and published to GitHub Pages as a
  searchable log of every day's news.

Built with the Gemini API (free tier, Google Search grounding) + Python, delivered by email, and
scheduled with GitHub Actions. No paid services and no third-party messaging
bridges — only Google (Gemini + Gmail), first-party and free. Embeddings run locally.

---

## How it works

```
┌──────────────────────────┐
│ GitHub Actions (daily)   │   cron: 07:00 IST
└────────────┬─────────────┘
             ▼
   ┌───────────────────┐   reads yesterday's votes
   │ 1. Learn          │◄──────────────┐
   │  update weights   │               │
   └─────────┬─────────┘        ┌──────┴───────┐
             ▼                  │ Google Sheet │  (👍/👎 log)
   ┌───────────────────┐        └──────▲───────┘
   │ 2. Fetch news     │               │
   │  Claude + search  │        ┌──────┴───────────┐
   └─────────┬─────────┘        │ Apps Script      │  receives clicks
             ▼                  │ web app          │
   ┌───────────────────┐        └──────▲───────────┘
   │ 3. Rank by taste  │               │
   └─────────┬─────────┘               │
             ▼                         │
   ┌───────────────────┐   email with  │
   │ 4. Email via Gmail│───────────────┘
   └───────────────────┘
```

### The learning loop
Each topic and keyword has a **weight** (starts at `1.0`). A story's score is
its category weight blended with its keyword weights. Thumbs feedback moves
those weights by a small **learning rate** (`0.15`), clamped to a sane range so
nothing runs away. It's a lightweight **online preference-learning** loop — a
tiny recommender, not heavy ML — and it's easy to reason about and explain.

### The dedup step
After scoring, each story is embedded with a local `all-MiniLM-L6-v2` model.
Stories whose embeddings exceed a cosine-similarity threshold (`0.80`) are
treated as the same event and merged; the highest-scored one represents the
group and remembers how many sources it absorbed. Clustering by *meaning* beats
string matching — "RBI holds rates" and "Central bank keeps repo unchanged"
merge correctly.

### The archive
Every run writes a readable per-day page and updates a small JSON search index
under `docs/`. GitHub Pages serves that folder, giving a live, searchable
archive at `https://<username>.github.io/<repo>/` for free.

---

## Project structure

| File | Purpose |
|------|---------|
| `digest.py` | Main pipeline: learn → fetch → dedup → rank → archive → send |
| `preferences.py` | The "brain": scoring and weight-update logic |
| `dedup.py` | Local embedding + clustering to merge duplicate stories |
| `archive.py` | Writes the per-day page and search index into `docs/` |
| `preferences.json` | The learned weights (updated and committed each run) |
| `docs/` | The GitHub Pages archive (front page, styles, per-day pages) |
| `feedback_receiver.gs` | Google Apps Script that logs 👍/👎 clicks to a Sheet |
| `.github/workflows/daily.yml` | Scheduled daily run + auto-commit of weights & archive |
| `.env.example` | Template of required config (real `.env` is git-ignored) |

---

## Setup

1. **Clone and install**
   ```bash
   git clone https://github.com/Keerthana524/news-digest.git
   cd news-digest
   pip install -r requirements.txt
   ```

2. **Add secrets** — copy `.env.example` to `.env` and fill in:
   - `GEMINI_API_KEY` — free from aistudio.google.com
   - `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` — a Gmail App Password (Google
     Account → Security → App passwords)

3. **Run it once locally**
   ```bash
   python digest.py
   ```
   Check your inbox.

4. **Feedback loop (Phase 2)** — deploy `feedback_receiver.gs` as a Google
   Apps Script web app, publish the Sheet as CSV, and paste both URLs into
   `.env` (`FEEDBACK_APPS_SCRIPT_URL`, `FEEDBACK_SHEET_CSV_URL`).

5. **Automate** — add the same values as **repository secrets** (Settings →
   Secrets and variables → Actions), and GitHub runs it every morning for free.

6. **Publish the archive** — Settings → Pages → Source: *Deploy from a branch*,
   branch `main`, folder `/docs`. Your archive goes live at
   `https://<username>.github.io/<repo>/`.

---

## Design notes

- **Why email, not WhatsApp?** WhatsApp automation needs either an unofficial
  bridge (ban risk) or a business API with template approvals — overkill for a
  personal digest. Email is first-party, format-friendly, and searchable.
- **Why Gemini with Search grounding, not a news API?** One free call both researches and
  formats the digest, instead of wiring up and normalising several feeds.
- **Secrets** live only in `.env` (git-ignored) and GitHub Secrets — never in
  the code.

## Roadmap
- [ ] Weekly "what you learned" summary of how weights shifted
- [ ] Searchable web archive of past digests (GitHub Pages)
- [ ] Retry + failure alert if a run errors
