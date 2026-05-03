# Project Baseline — Revenue Crew (v1)
**Last Updated**: May 1, 2026 (08:01 UTC)\
Status: Operational pipeline, pre-Option-2 automation

---

## Executive Summary

Revenue Crew is an automated short-form video clipping pipeline that:

1. Discovers candidate YouTube videos
2. Downloads source videos (1080p max, H.264)
3. Transcribes with Whisper to identify clip-worthy segments
4. Renders 9:16 vertical clips with burned-in captions
5. Delivers Telegram approval messages for manual upload

**Goal**: Produce 3+ TikTok/Reels/Shorts clips per day with minimal human intervention.

**Current State**:
- Download engine: Production-ready (pytubefix backend)
- Transcription: Working but needs optimization
- Clip rendering: Functional, re-encodes audio unnecessarily
- Discovery: Demo data only (no real API integration)
- Human-in-the-loop: Telegram notification with manual approval workflow

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                   social_crew.py (Entry Point)                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         v
┌──────────────────────────────────────────────────────────────────┐
│              HermesOrchestrator (pipeline/orchestrator.py)       │
│  - Manages run lifecycle, dedup logic, state transitions         │
│  - Retries operations (3 attempts per step)                      │
└────────────────────────────┬─────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        v                    v                    v
┌─────────────┐      ┌──────────────┐     ┌──────────────┐
│  Research   │      │     Clips    │      Telegram    │
│(discover)   │      │  (render)    │     (notify)     │
└─────────────┘      └──────────────┘     └──────────────┘
        │                           │
        v                           v
┌─────────────┐              ┌──────────────┐
│Candidate    │              │RenderedClip  │
│Videos       │              │(metadata)    │
└─────────────┘              └──────────────┘
        │                           │
        v                           v
┌──────────────────────────────────────────────────────────────────┐
│                   StateStore (SQLite)                            │
│  - Run records, processed sources, approval items                │
└──────────────────────────────────────────────────────────────────┘
```

---

## Core Modules

### Entry Point (`social_crew.py`)

**Responsibilities**:
- CLI argument parsing (`--download URL`, `--max-resolution N`)
- Environment loading (`.env`)
- Initialization of orchestrator, state store, Telegram client
- Main pipeline orchestration (`run_daily()`)

**Notable Features**:
- Direct video download mode (`--download`) for testing
- DRY_RUN mode for local execution without Telegram
- Strict Telegram credential validation (fails if missing in non-dry-run)

**Code Quality**: Clean separation of concerns, appropriate error handling

---

### Orchestrator (`pipeline/orchestrator.py`)

**Class**: `HermesOrchestrator`

**Responsibilities**:
- Run lifecycle management
- Candidate deduplication (excludes already-processed sources)
- Segmentation selection (highest confidence Whisper segment)
- Quality verification (basic duration check)
- Approval item assembly and Telegram notification

**Key Methods**:
```python
run_daily() -> str           # Main pipeline execution
handle_telegram_decision()   # Processes approve/reject/revise
_with_retries()             # 3-attempt retry wrapper
_select_candidates()        # Dedup + ranking
_choose_segment()           # Picks highest-confidence segment
_verify()                   # Basic policy validation
_build_approval_items()     # Constructs Telegram messages
```

**Design Pattern**: Dataclass-based orchestrator with injected dependencies (config, state, telegram)

**Issues**:
- CrewAI agents instantiated but discarded without use
- Verification logic too minimal (only checks duration > 60s)

---

### Schemas (`pipeline/schemas.py`)

**Data Classes**:

| Class | Purpose | Key Fields |
|-------|---------|-----------|
| `ApprovalStatus` | Enum for pipeline state | CREATED, PENDING_APPROVAL, APPROVED_MANUAL_UPLOAD, REJECTED, NEEDS_REVISION |
| `CandidateVideo` | Discovered video metadata | id, url, title, channel, engagement_scores |
| `ClipSegment` | Whisper-identified segment | candidate_id, start_sec, end_sec, hook_text, confidence |
| `RenderedClip` | Output file metadata | clip_id, candidate_id, video_path, subtitle_path, thumbnail_path, duration_sec, aspect_ratio |
| `VerificationResult` | Quality check outcome | clip_id, quality_score, policy_flags, recommendation, notes |
| `ApprovalItem` | Telegram message payload | run_id, clip_id, title, caption_suggestion, video_path, metadata |
| `RunRecord` | Pipeline run summary | run_id, created_at, status, total_candidates, total_clips |

**Quality**: Clean, serialization-friendly dataclasses. `to_dict()` method present for state persistence.

---

### Configuration (`pipeline/config.py`)

**Classes**:
- `YtdlpConfig` - Legacy yt-dlp options (cookies, format, player_clients)
- `PipelineConfig` - Main configuration loaded from `.env`

**Environment Variables**:
```bash
LLM_MODEL                    # ollama/qwen3.5:35b-a3b
LLM_BASE_URL                # http://localhost:11434
WORKSPACE_DIR               # Pipeline root
OUTPUT_DIR                  # /outputs
DOWNLOADS_DIR               # /downloads
STATE_DB_PATH               # pipeline_state.db
TELEGRAM_BOT_TOKEN          # Required
TELEGRAM_CHAT_ID            # Required
DAILY_CLIP_LIMIT            # 3 (max clips per run)
MAX_CANDIDATES              # 5 (max discovered)
MAX_DOWNLOAD_RESOLUTION     # 1080
DOWNLOAD_BACKEND            # pytubefix or ytdlp
DRY_RUN                     # false
```

**Validation**: Strong validation (raises on invalid values, not silent failures)

---

### Agent Factory (`pipeline/agent_factory.py`)

**Current State**: Minimal wrapper for CrewAI compatibility.

**Issue**: Calls `build_social_crew()` but discards the result. No CrewAI agents are actually used.

**Code**: ~20 lines, provides OllamaLLM wrapper for single-user operation

---

### Download Engine (`tools/download.py`)

**Backend Support**: Both `pytubefix` (default) and `yt-dlp` (legacy)

**pytubefix Flow**:
1. Extract streams from YouTube
2. Pick H.264 mp4 video ≤ MAX_DOWNLOAD_RESOLUTION (highest bitrate)
3. Pick AAC m4a audio (highest bitrate)
4. Download both to temp dir
5. Merge via `ffmpeg -c copy` (no re-encode)
6. Cache in `downloads/<videoId>.mp4` for future runs

**Quality**: Production-ready, handles dedup via file existence, appropriate error handling

**Optimizations**:
- Resolution filtering prevents unnecessary 4K downloads
- H.264 preference (faster encode during clipping)
- AAC audio preference (matches TikTok/Reels target)

**Issues**:
- Fallback to non-H.264 triggers warning (appropriate)
- No explicit stream selection logging beyond basic metadata

---

### Transcription Engine (`tools/transcribe.py`)

**Technology**: `faster-whisper` (medium model, default)

**Processing Flow**:
1. Load Whisper model (module-level LRU cache)
2. Transcribe video with beam search (beam_size=5)
3. Extract word-level confidence scores
4. Identify clip segments via sliding-window merge
5. Score segments for engagement

**Key Algorithms**:

**Clip Segment Identification** (`_identify_clip_segments`):
- Sliding window starting from each ASR boundary
- Merges segments until:
  - Soft boundary (45s default) crossed + punctuation/silence indicates boundary
  - Hard cap (180s default) reached
  - Silence gap ≥ 2s after soft boundary
- Output: clips 20-180s with average confidence ≥ 0.35

**Engagement Scoring** (`_calculate_engagement_score`):
```python
Base score = whisper confidence
+0.12 if text ends with sentence terminator
-0.03 if incomplete sentence
+0.1 if starts with engaging question (Why/What/How...)
+0.05 if 10-120 words
+0.08 if duration ≥ 90s
+0.05 if 55-89s
-0.06 if < 30s
```

**Quality**: Working, but has optimization opportunities (see P1 issues)

**Issues**:
- Whisper model loads once per process (acceptable)
- Language hardcoded to English (configurable needed)
- Compute type not specified (fp16 on CPU = slow, high RAM)

---

### Clipping Engine (`tools/clipping.py`)

**FFmpeg Pipeline**:

1. **Source extraction**:
   - Seek to start_time, extract duration
   - Scale to 1080p while preserving aspect ratio (`force_original_aspect_ratio=increase`)
   - Crop to 1080x1920 (9:16 vertical)
   - Encode: H.264 video, AAC audio (128k)

2. **Subtitle burn** (not actually burned, referenced separately):
   - Creates `.srt` file with clip hook text
   - Format: single cue from t=0 to clip duration

3. **Thumbnail extraction**:
   - Extracts frame from rendered clip at t=0
   - Resizes to 1080x1920, quality level 2

**FFmpeg Filters**:
```bash
-scale=w=1080:h=1920:force_original_aspect_ratio=increase,crop=1080:1920
-c:v h264 -c:a aac -b:a 128k -preset medium -r 30 -pix_fmt yuv420p
```

**Quality**: Correct operation, fixed in April 2026 (was `cropmax`, broken quotes)

**Issues**:
- **Audio re-encode wastes time** (source already AAC — should use `-c:a copy`)
- Subtitles not burned into video (stored separately)
- Subtitle font size not configurable

---

### Discovery Engine (`tools/research.py`)

**Current State**: Demo data only

**Modes**:
1. **Single test URL** (`SINGLE_TEST_VIDEO_URL` env var) — returns forced single candidate
2. **Demo rotation** — rotates through hardcoded YouTube video IDs with fake metadata

**Demo IDs** (real, for testing):
- EvIBrUDnh8s, dQw4w9WgXcQ, 9bZkp7q19f0, kJQP7kiw5Fk, OPf0YbXqDm0, CevxZvSJLk8

**Issues**:
- **NO real video discovery** (P0 blocker for scaling)
- Engagement scores fabricated
- No channel source tracking (hardcoded "Demo Channel")

---

### Telegram Client (`tools/telegram.py`)

**Capabilities**:
- Send approval bundles (summary + item-by-item messages)
- Parse callback commands (`approve <clip_id>`, `reject <clip_id>`, `revise <clip_id>`)

**Format**:
```
Run {run_id} generated {n} approval candidates.

{title}
clip_id={clip_id}
video={path}
caption={suggestion}
metadata={quality_score, aspect_ratio, duration_sec}

Reply with: approve <clip_id> | reject <clip_id> | revise <clip_id>
```

**Issues**:
- **No webhook handler** (handle_telegram_decision() exists but no caller)
- Manual polling or webhook endpoint needed

---

### State Store (`pipeline/state_store.py`)

**Technology**: SQLite (via SQLAlchemy)

**Persistence**:
- Run records (created_at, status, totals)
- Processed source IDs (dedup blacklist)
- Approval items (clip → status mapping)

**Quality Appropriate**: ACID operations, transactional safety

---

## Infrastructure & Environment

=== Prerequisites ===

- **Python**: 3.8+ (currently pinned to 3.9)
- **Ollama**: With `qwen3.5:35b-a3b` model
- **Telegram Bot**: Created via @BotFather
- **FFmpeg**: Required for video processing (`brew install ffmpeg`)
- **Internet**: Residential IP (YouTube blocks datacenter IPs)

=== Dependencies (79 pinned)===

- **Core**: `crewai==0.5.0`, `faster-whisper==1.2.1`, `pytubefix==10.4.0`, `yt-dlp==2025.10.14`
- **AI/LLM**: `ctranslate2==4.7.1` (Whisper), `huggingface_hub==1.8.0`
- **Web**: `aiohttp==3.13.5`, `httpx==0.28.1`, `requests==2.32.5`
- **Testing**: `pytest==8.4.2`
- **Data**: `SQLAlchemy==2.0.49`, `pydantic==2.13.3`, `dataclasses-json==0.6.7`

**Notable Omissions**:
- No logging rotation
- No error tracking (Sentry, etc.)
- No metrics collection

=== Environment Structure ===

```
revenue_crew/
├── pipeline/
│   ├── __init__.py
│   ├── agent_factory.py      # CrewAI wrapper (unused)
│   ├── config.py             # Config classes + env parsing
│   ├── env_loader.py         # .env loading
│   ├── llm.py                # OllamaLLM wrapper
│   ├── mock_llm.py           # Testing mock
│   ├── orchestrator.py       # HermesOrchestrator
│   ├── schemas.py            # Dataclasses
│   └── state_store.py        # SQLite persistence
├── tools/
│   ├── __init__.py
│   ├── clipping.py           # FFmpeg rendering
│   ├── download.py           # YouTube download engine
│   ├── manual_slice.py       # Manual time-slice tool
│   ├── research.py           # Discovery (demo only)
│   ├── telegram.py           # Telegram client
│   ├── timeparse.py          # Time string parser
│   └── transcribe.py         # Whisper transcription
├── tests/
│   ├── conftest.py
│   ├── manual_integration.py
│   ├── test_download.py
│   ├── test_download_opts.py
│   ├── test_manual_slice_timeparse.py
│   ├── test_orchestrator.py
│   ├── test_research.py
│   ├── test_schemas.py
│   ├── test_segmenter.py     # Whisper segmenter tests
│   ├── test_state_store.py
│   └── test_telegram.py
├── docs/
│   ├── bgutil-po-token-setup.md
│   ├── clip_finder_research.md
│   ├── curated_channel_clipping_research.md
│   ├── known-issues.md
│   ├── plan-b-local-source-mode.md
│   └── todo.md
├── outputs/                    # Rendered clips
├── downloads/                  # Cached source videos
├── pipeline_state.db           # SQLite state
├── social_crew.py              # Main entry point
├── requirements.txt            # Pinned deps
└── .env.example                # Template
```

=== FFmpeg Requirements ===

Required filters/flags verified:
```
scale=w=1080:h=1920:force_original_aspect_ratio=increase,crop=1080:1920
-h264 -aac -pix_fmt yuv420p -r 30
```

---

## Testing & QA

**Test Coverage**:
- `test_segmenter.py`: Core clip-finding algorithm (no faster_whisper import at collection)
- `test_download.py`: Download backend behavior, cache hits
- `test_download_opts.py`: Download configuration options
- `test_orchestrator.py`: Flow and dedup logic
- `test_schemas.py`: Serialization correctness
- `test_state_store.py`: Persistence operations
- `test_telegram.py`: Parsing, API calls
- `test_manual_slice_timeparse.py`: Manual time parsing

**Quality**: Good test coverage for core logic, lazy-import for faster_whisper avoids import-time dependencies

**Gaps**:
- No integration tests (requires live API keys)
- No performance benchmarks (Whisper timing, ffmpeg encoding speed)
- No fault injection testing (network failures, corrupt downloads)

---

## Documented Known Issues

P0 issues (resolved April-May 2026):
| Area | Problem | Fix |
|------|---------|-----|
| Transcript confidence | Broken generator/`sum(seg.words)` on Word objects | Mean of `Word.probability` with `word_timestamps=True` |
| Vertical FFmpeg filter | Malformed `-vf` (`cropmax`, broken quotes) | `scale=w=1080:h=1920:force_original_aspect_ratio=increase,crop=1080:1920` |
| Segment finder ("0 clips") | Required Whisper lines ≥13s, but emits 2-10s phrases | Sliding-window merge from each ASR boundary |

P1 issues (secondary, won't block but will hurt):
| Problem | Location | Recommendation |
|---------|----------|----------------|
| Audio unnecessarily re-encoded | `tools/clipping.py` | Switch to `-c:a copy` (source already AAC at 128kbps) |
| Whisper COMUTE_TYPE unspecified | `tools/transcribe.py` | Default to `compute_type=int8` (faster on CPU, less RAM) |
| Language hardcoded to English | `tools/transcribe.py:77` | Add `TRANSCRIBE_LANGUAGE` env var, default "en" or autodetect |
| SRT sidecar minimal | `tools/clipping.py` | Single cue, hook text only |

P2 issues (hygiene):
| Problem | Location |
|---------|----------|
| CrewAI agents built but discarded | `social_crew.py:49` |
| Demo discovery data only | `tools/research.py` |
| No inbound Telegram listener | No `--listen` mode |
| Plan B (manual ingest) documented but unused | `docs/plan-b-local-source-mode.md` |

---

## Operational Considerations

**Scalability**:
- Single-threaded pipeline (runs sequentially)
- Whisper medium ≈ 15-30 min per video on Apple Silicon CPU
- Max 3 clips/run (configurable via `DAILY_CLIP_LIMIT`)
- Storage: Each source ≈ 50-200MB, 3 clips/day ≈ 5-20GB/month

**Failure Modes**:
- YouTube PO Token rotation (handled by pytubefix bundled Node.js)
- Datacenter IP blocking (requires residential IP if containerized)
- Network timeouts (3-attempt retry in orchestrator)
- Whisper model load failures (lru_cache ensures one-time load)
- Telegram API failures (no retry, logs exception)

**Cost Implications** (real-time only):
- Compute: CPU-bound (no GPU required, but MPS/CUDA faster)
- Storage: Bounded by `downloads_dir` retention (no cleanup policy)
- Network: 3-6GB/day if running full pipeline
- Bot API: Telegram free (20MB/file limit, not hit by 1080p clips)

---

## Strategic Assessment

**Strengths**:
- ✅ Solid download foundation (pytubefix, no cookiestubebakery)
- ✅ Working Whisper transcription with engagement scoring
- ✅ Clean architecture (separate concerns, dependency injection)
- ✅ State persistence for dedup and audit trail
- ✅ Production-ready error handling (retries, timeouts)

**Weaknesses**:
- ❌ No real video discovery (demo data only)
- ❌ CrewAI integration incomplete (agents instantiated but unused)
- ❌ Audio re-encode wastes time
- ❌ No automated clip quality verification beyond duration
- ❌ No inbound Telegram handler (approval loop unsealed)

**Opportunities**:
- 🔮 Option 1.5: Curated URL list + cron (20 lines, high value)
- 🔮 AI-driven segment selection (replace confidence heuristic)
- 🔮 AI hook text generation (optimize for short-form)
- 🔮 Multi-segment per video support
- 🔮 Integration with TikTok/Reels upload APIs (later stage)

**Threats**:
- ⚠️ YouTube API changes (PO Token bypass may break)
- ⚠️ Whisper model drift (accuracy degradation over time)
- ⚠️ Telegram rate limits (user accounts, not bots)
- ⚠️ Platform policy changes (automated content posting restrictions)

---

## Priority Improvements

**P0** (blockers for meaningful scaling):
1. **Inbound Telegram listener** — `--listen` mode or webhook handler
2. **Real discovery mechanism** — curated URL file or YouTube API
3. **Decide CrewAI's role** — wire into segment selection or remove stub

**P1** (quality of life):
1. **Audio copy instead of re-encode** — 5-10 min savings per clip
2. **Configurable compute type** — `WHISPER_COMPUTE_TYPE=int8`
3. **Better quality verification** — silent clip detection, missing audio

**P2** (technical debt):
1. **Logging rotation** — prevent logs directory from filling up
2. **Deduplicated source retention policy** — auto-clean old downloads
3. **Error tracking integration** — Sentry, Rollbar, etc.

---

## Next Steps for Review

**Immediate** (this week):
- Run `social_crew.py` with `SINGLE_TEST_VIDEO_URL` configured
- Verify: download → transcribe → segment → render → Telegram notification
- Confirm N clip segments found (expect N > 0, not "0 clips" error)

**Short-term** (this month):
- Implement `--listen` mode for Telegram callback handling
- Replace demo discovery with curated URL file ingestion
- Add audio copy mode to clipping pipeline

**Medium-term** (Q2):
- AI-driven segment selection via Ollama
- Multi-segment per video support  
- Quality verification expansion (silent detection, audio presence)

**Long-term** (Q3+):
- Automated TikTok/Reels upload (API-based)
- Channel ranking / video quality scoring
- Multi-language support

---

## Conclusion

Revenue Crew V1 is a **functional foundation** for automated short-form video clipping. The pipeline successfully handles the core operations (download, transcribe, render, notify) with appropriate error handling and state management.

The **critical blocker** is replacing demo discovery with real video ingestion. Until that's resolved, the pipeline can only work with manually-specified URLs.

The **secondary blocker** is the incomplete approval loop — Telegram sends notifications but provides no feedback mechanism back into the system.

**Verdict**: Solid engineering, ready for Option 1.5 (curated URL list) as immediate next step, with Telegram listener as parallel workstream.
