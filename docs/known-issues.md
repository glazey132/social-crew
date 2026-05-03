# Known Issues — Pipeline Stages After Download

The download stage is solid as of May 2026 (`pytubefix` default backend,
H.264 ≤ 1080p, ffmpeg `-c copy` merge into `downloads/<videoId>.mp4`).
Everything *after* download — transcribe, clip render, agent wiring —
has known gaps documented here.

---

## Recently resolved May 2026

Issues that formerly blocked clips from rendering:

| Area | Problem | Fix |
|------|---------|-----|
| **Transcript confidence** | Broken generator/`sum(seg.words)` on `Word` objects | Mean of `Word.probability` when `word_timestamps=True`. |
| **Vertical FFmpeg filter** | Malformed `-vf` (`cropmax`, broken quotes) | `scale=w=1080:h=1920:force_original_aspect_ratio=increase,crop=1080:1920` in [`tools/clipping.py`](tools/clipping.py). |
| **Segment finder (“0 clips”)** | `_identify_clip_segments` required each raw Whisper line to be ≥13s; Whisper emits 2–10s phrases → every line skipped | Sliding-window merge from each ASR boundary (`_identify_clip_segments` in [`tools/transcribe.py`](tools/transcribe.py); defaults favor **long coherent units** — see `CLIP_*` env; tests in [`tests/test_segmenter.py`](tests/test_segmenter.py)). |

`faster_whisper` is **lazy-imported** inside `_get_whisper_model()` so pytest can import `_identify_clip_segments` without loading CTranslate2 at collection time.

---

## P1 — secondary issues (won't block, but will hurt soon)

- **Whisper model load is cached once per process** via
  `functools.lru_cache` on `_get_whisper_model()`. Retries and
  multi-source runs reuse the same instance.
- **`WHISPER_COMPUTE_TYPE` not wired.** Medium weights download as fp16;
  CPU on Apple Silicon falls back to fp32 (slow, high RAM). Prefer
  `compute_type=int8` for CPU (faster, smaller) — plumb through env
  like `WHISPER_MODEL_SIZE`.
- **Language is hardcoded to English.** `tools/transcribe.py:77` passes
  `language="en"`. Make this configurable via env
  (`TRANSCRIBE_LANGUAGE`, default `"en"`, blank = autodetect).
- **SRT sidecar is minimal** (single cue, hook text only). End timestamps
  use proper `H:MM:SS,mmm` via `_format_srt_timestamp` in
  [`tools/clipping.py`](tools/clipping.py); burned-in subs on export are a
  separate path if added later.
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

1. **Re-run `python social_crew.py`** with your `SINGLE_TEST_VIDEO_URL`
   after clearing `processed_sources` if needed. Expect `Found N potential
   clip segments` where `N >> 0`, then a rendered file in `outputs/`.
2. **`WHISPER_COMPUTE_TYPE=int8`** wiring + README (CPU speed / RAM).
3. **Inbound Telegram listener** (`--listen` or webhook).
4. **Decide CrewAI's role** (wire agents into scoring or drop the stub).
5. **Replace demo discovery** — curated URL file or Option 2 API.
