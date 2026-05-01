# Plan B: Local Source Mode

A reliable downloader-free path for the pipeline. Drop an mp4 in a folder, the pipeline handles the rest. This is what most indie clippers actually do in 2026.

## Why we want this

YouTube programmatic downloading in 2026 is a maintained engineering problem (PO Tokens + cookies + IP gating). Even self-hosted Cobalt still requires periodic env var maintenance. Indie clippers typically:

- Manually grab the source video (~30 seconds in a browser).
- Let the AI pipeline do everything else (transcribe -> clip -> verify -> Telegram).

This plan makes that the supported, first-class flow.

```
Browser:  user grabs mp4 from YouTube
            |
            v
        inputs/ folder (drop file)
            |
            v
   social_crew.py picks it up
            |
            v
   transcribe -> clip -> verify -> telegram
```

---

## What to use to download YouTube videos manually (May 2026)

The pipeline does not care which tool you use. Recommendations, ordered by reliability:

1. **cobalt.tools (web UI)** — free, no ads, no signup, privacy-friendly. Go to <https://cobalt.tools>, paste URL, click download. Most reliable when YouTube has not freshly broken downloaders. **Use this first.**
2. **Video DownloadHelper** browser extension (Chrome/Firefox/Edge). Click the icon while watching the video, save the highest-quality MP4. Survives many cobalt outages.
3. **yout.com** or **y2mate.com** — fallbacks when both above are throttled. More ads, but they do work.
4. (Power user) **yt-dlp from your terminal** with cookies — fine for ad-hoc but you have already seen the maintenance pain.

Save downloaded files into the project's `inputs/` directory (created by this plan).

---

## What in our current architecture changes

Minimal blast radius. No removal of YouTube downloading; we just add a parallel ingest path.

| File | Change | Notes |
|------|--------|-------|
| `pipeline/config.py` | Add `local_source_dir: Optional[Path]` from env `LOCAL_SOURCE_DIR`. | Resolved relative to `WORKSPACE_DIR`; only applied if dir exists. |
| `pipeline/schemas.py` | Add `local_path: Optional[str] = None` to `CandidateVideo`. | Backwards compatible. |
| `tools/research.py` | If `LOCAL_SOURCE_DIR` is set and exists, return local files as candidates and skip demo/forced URL paths. | Stable id `local_<filename>` for dedupe. |
| `pipeline/orchestrator.py` | If `candidate.local_path` is set, skip `download_video` and use that path directly. | Removes downloader / cookie / PO-token risk for local-mode runs. |
| `tools/download.py` | No change. Still used for non-local candidates. | Local mode just bypasses it. |
| `tests/test_research.py` | Add a test for `LOCAL_SOURCE_DIR` discovery. | |
| `tests/test_orchestrator.py` | Add a test for orchestrator skipping download in local mode. | |
| `.env.example` / `README.md` | Document the new env var and the manual download tools. | |
| `.gitignore` | Ignore `inputs/` and `inputs/processed/`. | Avoid accidental media commits. |

No existing tests need to change in semantics; only an additional case is added.

---

## Detailed change sketches

### `pipeline/schemas.py`

```python
@dataclass
class CandidateVideo:
    id: str
    url: str
    title: str
    channel: str
    published_at: str
    reason: str
    engagement_signals: Dict[str, float]
    local_path: Optional[str] = None  # NEW: when set, skip downloader
```

### `pipeline/config.py`

Add to `PipelineConfig`:
- `local_source_dir: Optional[Path]`

In `from_env()`:

```python
local_raw = os.getenv("LOCAL_SOURCE_DIR", "").strip()
local_source_dir: Optional[Path] = None
if local_raw:
    p = Path(local_raw)
    p = (workspace_dir / p).resolve() if not p.is_absolute() else p.resolve()
    if p.is_dir():
        local_source_dir = p
```

### `tools/research.py`

Priority order for `discover_candidates`:

1. `SINGLE_TEST_VIDEO_URL` (existing, unchanged).
2. `LOCAL_SOURCE_DIR` (new): scan for `*.mp4` / `*.mov`, return one `CandidateVideo` per file with `local_path` set, `url` set to a `file://` URI for traceability.
3. Demo list (existing fallback).

Stable id: `local_<file_stem>`. Lets dedupe across runs work the same way as YouTube IDs.

### `pipeline/orchestrator.py`

In `run_daily()` per-candidate loop:

```python
if candidate.local_path:
    source_path = Path(candidate.local_path)
else:
    source_path = self._with_retries(
        lambda: download_video(
            candidate.url,
            self.config.output_dir,
            dry_run=self.config.dry_run,
            ytdlp=self.config.ytdlp,
        ),
        operation="download_video",
        candidate_id=candidate.id,
    )
```

Everything after this point (transcribe / clip / verify / approval / telegram) is unchanged.

### Optional follow-up (not in v1)

- After successful processing, move the file to `inputs/processed/` so the next run only sees new drops.
- Add a `LOCAL_SOURCE_GLOB` env to allow non-mp4 inputs.

---

## How you would use it day-to-day

1. Make the inputs folder once:
   ```bash
   mkdir -p inputs
   ```
2. In `.env`:
   ```
   LOCAL_SOURCE_DIR=inputs
   ```
3. From browser, save an mp4 to `inputs/` using cobalt.tools (or alternative).
4. Run:
   ```bash
   python social_crew.py
   ```
5. Approve / reject in Telegram.
6. Manually upload approved clips to TikTok / YouTube Shorts (this matches the original "manual upload" decision in the V1 plan).

---

## What this gives up

- No automatic discovery of trending YouTube videos. You pick what to clip.
- No batch background scraping. The pipeline runs on what you put in `inputs/`.

For a daily indie clipping workflow, this is the **standard** trade — and is essentially what paid clippers do behind the scenes after their (expensive) discovery layer.

---

## Test strategy

Add unit tests:
- `tests/test_research.py`:
  - `LOCAL_SOURCE_DIR` set and folder contains 2 mp4s -> 2 candidates with `local_path` populated and stable ids.
  - `LOCAL_SOURCE_DIR` set but missing -> falls back to demo list.
- `tests/test_orchestrator.py`:
  - Candidate with `local_path` -> `download_video` is not called; `transcribe_video` is called with that path.

No removal of existing tests required.

---

## Rollout checklist

- [ ] Schema field added (`local_path`).
- [ ] Config wires `LOCAL_SOURCE_DIR` into `PipelineConfig`.
- [ ] `discover_candidates` returns local files when configured.
- [ ] Orchestrator branches on `local_path`.
- [ ] New tests added; all tests still pass.
- [ ] README + `.env.example` updated.
- [ ] `.gitignore` ignores `inputs/`.

---

## Long-term path (if you ever want to revisit auto YouTube fetch)

Local source mode does not block any future automation:
- You can still run yt-dlp + bgutil PO Token plugin (already wired) when it works; it just becomes a *secondary* path that drops files into `inputs/` for you.
- You can later swap in self-hosted Cobalt as a `tools/download_via_cobalt.py` adapter without touching the orchestrator.

The local source mode is the durable backbone; downloaders become interchangeable upstream feeders.
