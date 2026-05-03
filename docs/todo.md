# Roadmap — P0 → Option 2

Living TODO. Updated as work lands. Each item has a brief acceptance criterion.

## Status legend

- `[ ]` — not started
- `[~]` — in progress
- `[x]` — done

---

## P0 — blockers (do first)

Without these, no real clip ever renders.

- [x] **Fix `tools/transcribe.py:85` confidence calc.** *(May 1)*
  Now calls `sum(w.probability for w in seg.words) / len(seg.words)`
  per `faster_whisper.transcribe.Word.probability`.
- [x] **Fix `tools/clipping.py:122` ffmpeg `-vf` filter.** *(May 1)*
  Now `scale=w=1080:h=1920:force_original_aspect_ratio=increase,crop=1080:1920`.
  Verified live: produces a 1080x1920 h264+aac mp4 from a horizontal
  source (smoke run cut a 15s vertical from `zAgVf3Ab0fA.mp4`).
- [~] **End-to-end smoke run.**
  `python social_crew.py` with `SINGLE_TEST_VIDEO_URL` set should
  succeed: download → transcribe → segment → render → Telegram approval
  message.
  *Done when:* a clip lands in `outputs/` and an approval message
  arrives in Telegram.
  *Changelog (May 1):*
    - `WhisperModel(size=...)` wrong kwarg → positional
      `model_size_or_path` + `lru_cache` on `_get_whisper_model()`.
    - Orchestrator poisoned dedupe on failure → only successful
      renders go to `processed_sources`.
    - **Segment finder:** `_identify_clip_segments` rewrote to sliding-window
      merge (was 0 clips for typical Whisper output). Tests:
      `tests/test_segmenter.py`. `faster_whisper` lazy-imported for safe
      pytest collection.
  *Re-verify:* run `social_crew.py` again; expect `Found N potential clip
  segments` with `N >> 0` before render. Long videos on CPU still spend
  ~15–30+ min in Whisper `medium`.

---

## Pre-Option-1 (closes the approval loop)

- [ ] **Decide CrewAI's role.**
  Today `social_crew.py:49` builds agents and discards them. Pick:
  - (a) Wire CrewAI into segment selection / hook generation. The
    name "social crew" becomes meaningful.
  - (b) Drop the factory call. Keep raw Ollama wrapper for direct LLM
    calls. Simpler, less framework lock-in.
  *Done when:* either agents are exercised in `run_daily()` OR the
  factory call is removed and the imports cleaned up.
- [ ] **Inbound Telegram approval handler.**
  `orchestrator.handle_telegram_decision()` exists but nothing calls
  it from real Telegram traffic. Build either:
  - long-poll loop in a `python social_crew.py --listen` mode, or
  - a webhook endpoint (overkill for a personal bot).
  *Done when:* sending `approve <clip_id>` from Telegram updates
  `pipeline_state.db` to `APPROVED_MANUAL_UPLOAD`.

---

## Option 1 — find clips in videos we pass

User-curated input. Best per-clip quality. Building block of Option 2.

- [ ] **AI-driven segment selection.**
  Replace the current "highest confidence wins" heuristic in
  `_choose_segment` with an LLM pass: feed transcript + timestamps
  to Ollama, ask "which 15-60s window is most engaging?", return
  start/end. Depends on CrewAI decision above.
  *Done when:* the chosen segment for a known video reliably picks
  the actual hook of the video, not just the highest-Whisper-confidence
  block.
- [ ] **AI-driven hook text generation.**
  Replace `_generate_hook_text` (first sentence of segment) with an
  LLM rewrite optimized for short-form on-screen text.
  *Done when:* generated hook text reads as a punchy on-screen line,
  not a transcript fragment.
- [ ] **Multi-segment per video.**
  Today the orchestrator picks one segment per video. For Option 1
  let the user opt into N segments per source.
  *Done when:* `--segments-per-video N` (or env var) controls how
  many clips get rendered per input URL.
- [ ] **Quality verification beyond duration.**
  `_verify` only flags `too_long`. Add: clip is silent? clip starts
  mid-word? hook text empty? Any of those → reject before Telegram.

---

## Option 1.5 — curated URL list + cron

Cheap automation. ~20 lines of code. Reuses Option 1 entirely.

- [ ] **`--discover-from FILE` flag.**
  Read URLs from a text file (one per line, `#` comments allowed),
  dedupe against `processed_sources`, feed into the existing
  pipeline as candidates.
  *Done when:* `python social_crew.py --discover-from inputs/daily.txt`
  processes new URLs and skips already-handled ones.
- [ ] **Daily cron / launchd setup.**
  Document a launchd plist (or cron entry) that runs the pipeline
  once a day with the curated list.
  *Done when:* a tested macOS launchd config lives in
  `docs/cron-setup.md` (or similar).
- [ ] **Curate the initial list.**
  Pick 5-10 channels worth following. Keep the URL list in version
  control (channels themselves can stay private as identifiers).
  *Done when:* `inputs/daily.txt.example` ships with a starter set.

---

## Option 2 — automated discovery

The hard one. Don't start before Option 1 is producing usable clips.

- [ ] **Pick a discovery strategy.**
  Two viable paths, listed in `docs/curated_channel_clipping_research.md`:
  - YouTube Data API v3 search (needs API key, has quota).
  - RSS feed polling per channel (no key, less metadata).
  *Done when:* one is chosen and prototyped.
- [ ] **Implement candidate scoring.**
  Beyond "is new" — needs some "is this clip-worthy" signal. Could be
  views/age ratio, channel-specific recency, or LLM read of the title
  + description.
  *Done when:* a scoring function ranks discovered candidates and
  feeds the top N into `daily_clip_limit`.
- [ ] **Long-term dedup.**
  `processed_sources` already exists; verify discovery layer respects
  it across runs.
- [ ] **Rate limit + error handling.**
  Discovery layer should retry / back off without exploding the
  daily run.

---

## P1 / P2 hygiene (do anytime)

Track separately so the main path stays clean. Pulled from
[`docs/known-issues.md`](known-issues.md).

- [ ] **Cache the Whisper model** (`tools/transcribe.py`).
  Today `WhisperModel(size="medium")` loads on every call. Cache
  module-level. *Cheap; do before Option 1.*
- [ ] **Configurable transcribe language** (`TRANSCRIBE_LANGUAGE`).
- [x] **SRT timestamp fix** — `_format_srt_timestamp` in `tools/clipping.py` (was invalid for >99 s).
- [ ] **`-c:a copy`** for audio in `tools/clipping.py` rough cut.
- [ ] **Replace demo discovery** in `tools/research.py` (folded into
  Option 1.5 / Option 2).
