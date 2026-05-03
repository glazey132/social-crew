# Social Content Pipeline V1

This project runs a Hermes-orchestrated CrewAI pipeline that discovers source videos, generates short clips, verifies quality, and sends Telegram approvals for manual upload.

## Setup

### Prerequisites
- Python 3.8+
- [Ollama](https://ollama.com) with `qwen3.5:35b-a3b` model installed
- Telegram account (to create a bot via @BotFather)

### 1. Activate your environment
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Clone `.env.example` and configure

```bash
cp .env.example .env
```

Edit `.env` with your values:
- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `TELEGRAM_CHAT_ID` — your Telegram ID (see `.env.example`)
- `LLM_MODEL` and `LLM_BASE_URL` — Ollama configuration

**⚠️ NEVER commit `.env` to git — it's automatically ignored.**

### 3. Required environment variables
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_MODEL` | No | `ollama/qwen3.5:35b-a3b` | Ollama model identifier |
| `LLM_BASE_URL` | No | `http://localhost:11434` | Ollama server endpoint |
| `TELEGRAM_BOT_TOKEN` | **Yes** | — | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | **Yes** | — | Destination chat ID for approvals |
| `DAILY_CLIP_LIMIT` | No | `3` | Max clips per run |
| `MAX_CANDIDATES` | No | `5` | Max candidates to evaluate |
| `DRY_RUN` | No | `false` | Enable testing mode |
| `SINGLE_TEST_VIDEO_URL` | No | — | If set, discovery returns only this YouTube URL (full `watch?v=` or `youtu.be/` link). Stable id `source_<videoId>` for dedupe. |
| `OUTPUT_DIR` | No | `${WORKSPACE_DIR}/outputs` | Final rendered clips ready for upload. |
| `DOWNLOADS_DIR` | No | `${WORKSPACE_DIR}/downloads` | Raw mp4s pulled from YouTube. Cached, so re-runs skip re-downloading. |
| `DOWNLOAD_BACKEND` | No | `pytubefix` | `pytubefix` (default, no plumbing) or `ytdlp` (legacy, requires cookies + PO token plugin). |
| `MAX_DOWNLOAD_RESOLUTION` | No | `1080` | Cap on source resolution. TikTok/Shorts/Reels all serve 1080p — 4K just wastes disk and ffmpeg encode time. |
| `YTDLP_COOKIES_FILE` | No | — | Legacy: Netscape `cookies.txt` path. Only used when `DOWNLOAD_BACKEND=ytdlp`. |
| `YTDLP_COOKIES_FROM_BROWSER` | No | — | Legacy: e.g. `safari` or `chrome:Default`. Only used when `DOWNLOAD_BACKEND=ytdlp`. |
| `YTDLP_FORMAT` | No | `18/best[ext=mp4]/best` | Legacy: yt-dlp format selector. |
| `YTDLP_FORCE_IPV4` | No | `false` | Legacy: pass `source_address=0.0.0.0` to yt-dlp. |
| `YTDLP_PLAYER_CLIENT` | No | — | Legacy: comma-separated `extractor_args.player_client` list, e.g. `web,tv,android`. |
| `CLIP_MIN_SEC` | No | `20` | Minimum clip length from transcript windows. |
| `CLIP_MAX_SEC` | No | `180` | Hard cap (favor trimming in TikTok over too-short cuts). |
| `CLIP_SOFT_BOUNDARY_MIN_SEC` | No | `45` | Do not split on punctuation or silence until at least this duration. |
| `CLIP_SILENCE_GAP_SEC` | No | `2.0` | Pause (seconds) between Whisper lines to treat as a natural split (only after soft min). |

## Video downloads

The default backend is **[pytubefix](https://github.com/JuanBindez/pytubefix)** — pure Python, ships its own bundled Node.js binary for PO Token generation, no cookies / external server / browser extension required.

Per-video flow:
1. Pick the highest-resolution H.264 mp4 video stream `≤ MAX_DOWNLOAD_RESOLUTION` (falls back to non-H.264 mp4 if no H.264 available; warned).
2. Pick the highest-bitrate AAC m4a audio stream.
3. Download both to a temp subdir of `DOWNLOADS_DIR`.
4. Merge with `ffmpeg -c copy` (no re-encode) into `${DOWNLOADS_DIR}/<videoId>.mp4`.
5. Subsequent runs hit the cache and skip the network entirely.

Requirements:
- `ffmpeg` available on `$PATH`. macOS: `brew install ffmpeg`.
- Internet from a residential IP. Datacenter IPs are aggressively blocked by YouTube — if you containerize this, plan on a residential proxy.

### Why H.264 / 1080p caps

- TikTok, YouTube Shorts, and Instagram Reels all serve clips at **1080×1920** maximum. 4K source files don't survive the upload re-encode.
- Every clipping operation re-encodes (subtitle burn, 9:16 crop). H.264 encode/decode on consumer Macs is ~5× faster than AV1 and ~2× faster than VP9.
- These caps are env-overridable (`MAX_DOWNLOAD_RESOLUTION`) if you ever want to revisit.

### Legacy: yt-dlp + bgutil PO Token (opt-in)

If pytubefix ever breaks on a YouTube change, you can flip to the legacy yt-dlp path:

```bash
DOWNLOAD_BACKEND=ytdlp
YTDLP_COOKIES_FILE=cookies.txt
YTDLP_PLAYER_CLIENT=web,tv,android
```

That path requires:
- A fresh Netscape `cookies.txt` exported from your browser (e.g. "Get cookies.txt LOCALLY" extension).
- The [`bgutil-ytdlp-pot-provider`](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) plugin installed and its Node.js companion server running (see `docs/bgutil-po-token-setup.md`).
- Tolerance for periodic version-skew bugs between the plugin and yt-dlp's logger API.

This path is intentionally not the default — it's brittle today (April 2026). Background: [yt-dlp issue #12482](https://github.com/yt-dlp/yt-dlp/issues/12482).

## Run Daily Pipeline

```bash
python social_crew.py
```

Pipeline output:
- Rendered clip artifacts in `OUTPUT_DIR` (default `outputs/`)
- SQLite state in `pipeline_state.db` (unless overridden)
- Telegram messages for approval review

### Quick: download a single video without running the pipeline

Use `--download URL` to grab a single YouTube video into `DOWNLOADS_DIR` and exit. Skips Telegram, agents, transcription, clipping — pure download.

```bash
python social_crew.py --download "https://www.youtube.com/watch?v=EvIBrUDnh8s"
# -> /Users/you/revenue_crew/downloads/EvIBrUDnh8s.mp4
```

Flags:
- `--download URL` — the YouTube watch / `youtu.be` link.
- `--max-resolution N` — override `MAX_DOWNLOAD_RESOLUTION` for this run only (e.g. `--max-resolution 720`).

Uses the configured `DOWNLOAD_BACKEND` (default `pytubefix`). Cached: re-running with the same URL skips the network and returns the existing file.

## Manual slice (time range to TikTok 9:16)

For a **local** video (e.g. a long cached download under `downloads/`), slice between a **start** and **end** time on the source timeline and encode the **same vertical 1080×1920** output as the main pipeline—no Whisper, no Telegram.

```bash
python tools/manual_slice.py downloads/YOURVIDEOID.mp4 --start 3660 --end 3960 --hook "Chapter title here"
```

The script fixes `sys.path` so you normally **do not** need `PYTHONPATH=.`. Outputs go to **`OUTPUT_DIR`** from `.env` by default (`outputs/`), unless you pass `--output-dir`.

**Times:** plain seconds (`3600`, `90.5`), `MM:SS` (`62:45`), or `H:MM:SS` (`1:01:45`). Use `--dry-run` to skip FFmpeg.

## Telegram Approval Commands

Respond with one of:
- `approve <clip_id>`
- `reject <clip_id>`
- `revise <clip_id>`

## Tests

```bash
pytest -q
```

Unit tests cover:
- Schema serialization
- Orchestrator flow and dedupe logic
- pytubefix download path (stream selection, ffmpeg merge, cache hit, fallbacks)
- Legacy yt-dlp option building (cookies / format / IPv4 / player_client)
- State persistence transitions
- Manual time parser (`tools/timeparse`) for HH:MM:SS-style clip bounds

