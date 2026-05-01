# Known Issues — Pipeline Stages After Download

The download stage is solid as of May 2026 (`pytubefix` default backend,
H.264 ≤ 1080p, ffmpeg `-c copy` merge into `downloads/<videoId>.mp4`).
Everything *after* download — transcribe, clip render, agent wiring —
has known gaps documented here.

---

## P0 — blockers for any real end-to-end run

### `tools/transcribe.py:85` — confidence calc is broken

Current code:

```python
confidence = (sum(seg.words) for seg in seg.words) / len(seg.words) if seg.words else 0.8
```

Three problems stacked:

1. `(sum(seg.words) for seg in seg.words)` is a generator expression that
   shadows the outer loop variable `seg`. Even ignoring the shadow, the
   contents are wrong — `seg.words` is a list of `faster_whisper.Word`
   objects, not numbers, so `sum(seg.words)` raises `TypeError`.
2. Dividing a generator by an int raises `TypeError`.
3. Even if it ran, the result would be meaningless.

This blocks every transcription call once an actual video reaches the
function.

Proposed fix:

```python
confidence = (
    sum(w.probability for w in seg.words) / len(seg.words)
    if seg.words else 0.8
)
```

`Word.probability` is the per-token confidence score that
`faster-whisper` exposes when `word_timestamps=True`.

---

### `tools/clipping.py:122` — ffmpeg `-vf` filter is malformed

Current code:

```python
"-vf", f"scale='min(1080*1080/{1080*1080}':1080:-1,'cropmax=1080:1920',crop=1080:1920",
```

Three problems:

1. `cropmax` is not a real ffmpeg filter. ffmpeg will reject the filter
   chain outright.
2. The single quotes are unbalanced. `'min(...` opens an expression that
   never closes; the `'` in front of `cropmax` opens another that never
   closes. Even with a valid filter name, this would parse error.
3. The math `1080*1080/{1080*1080}` evaluates to literal `1` after the
   f-string substitutes — the expression is a no-op.

**Goal:** scale the source so the *smaller* axis becomes ≥ the target
dimension, then center-crop to 1080×1920 (TikTok / Shorts / Reels
portrait).

Proposed fix:

```python
"-vf", "scale=w=1080:h=1920:force_original_aspect_ratio=increase,"
       "crop=1080:1920"
```

`force_original_aspect_ratio=increase` makes ffmpeg pick the larger of
the two scale factors so neither axis ends up smaller than the target,
then `crop=1080:1920` (defaults to centered) trims the overflow.

---

## P1 — secondary issues (won't block, but will hurt soon)

- **Whisper model is loaded per call.** `tools/transcribe.py:49`
  instantiates `WhisperModel(size="medium", device="auto")` inside
  `transcribe_video()`. The model load (~1 GB to disk, ~30 s on CPU)
  dominates per-candidate runtime. Cache it module-level (e.g.
  `functools.lru_cache`) or make it a `dataclass` field that's reused
  across the loop.
- **Language is hardcoded to English.** `tools/transcribe.py:77` passes
  `language="en"`. Make this configurable via env
  (`TRANSCRIBE_LANGUAGE`, default `"en"`, blank = autodetect).
- **SRT timestamps break for clips > 60 s.**
  `tools/clipping.py:72` builds the SRT line as
  `00:00:{int(duration):02d},000`, so a 90-second clip would write
  `00:00:90,000` — invalid SRT. Use a proper `H:MM:SS,mmm` formatter,
  e.g. `f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"`.
- **Audio is needlessly re-encoded.** `tools/clipping.py` re-encodes
  audio to AAC, but our `pytubefix` source is already AAC at 128 kbps.
  Switch to `-c:a copy` for the rough cut to save time and avoid
  generation loss; only re-encode when subtitles or other audio
  changes are involved.

---

## P2 — broader hygiene

- **`social_crew.py:49` builds CrewAI agents and discards them.**
  `build_social_crew(config.llm_model, config.llm_base_url)` returns a
  dict that's not assigned. The CrewAI agents are constructed and
  immediately garbage-collected; the orchestrator runs its own
  non-AI logic. Decide CrewAI's actual role: either wire the agents
  into the orchestrator (e.g. for hook copywriting / segment scoring)
  or delete the factory call.
- **`tools/research.py` returns a hardcoded demo list.** Real candidate
  ingestion is unbuilt. Two paths already drafted in this repo:
  - `docs/curated_channel_clipping_research.md` — poll a known list of
    high-fidelity channels.
  - `docs/clip_finder_research.md` — accept a user-supplied URL and
    let the AI pick clips inside it.
- **Plan B (manual ingest) is documented but not wired.**
  `docs/plan-b-local-source-mode.md` describes a `LOCAL_SOURCE_DIR`
  ingest mode. We didn't need it once `pytubefix` worked, but if YT
  ever breaks the default backend, it's the cheapest contingency.

---

## Suggested order of attack

1. **Fix `transcribe.py:85` and `clipping.py:122`.** Both P0s. Without
   them, no end-to-end run produces a real clip.
2. **Run `python social_crew.py`** with `SINGLE_TEST_VIDEO_URL` set to
   the test video (`EvIBrUDnh8s`) and watch the full pipeline succeed
   or surface the next failure.
3. **Cache the Whisper model.** Single-line fix that immediately
   makes multi-candidate days viable.
4. **Decide CrewAI's role** (wire in or delete the factory call).
5. **Replace demo discovery** with one of the two researched
   approaches in `docs/`.
