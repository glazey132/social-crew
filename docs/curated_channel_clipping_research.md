# Curated Channel Clipping System (Feature 2)
## Deep Research Document

**Project**: revenue_crew  
**Feature**: Daily curation of high-fidelity clips from pre-screened YouTube channels  
**Status**: Research (April 30, 2026)  
**Target**: 3-5 clips/day from 10 known channels, 1080p+ quality, human approval workflow

---

## Overview

This document outlines the technical and operational requirements for **Feature 2** of revenue_crew — a system that polls known YouTube channels known for quality content (e.g., Danny Jones Clips, Alex Hormozi clips), identifies the most interesting segments, and auto-clips them for human review.

Unlike Feature 1 (which transcribes and identifies segments from long-form content), Feature 2 targets *already-edited short clips* that need final selection and reformatting for social platforms.

---

## Use Case Definition

### Scenario
- User maintains a list of ~10 YouTube channels known for high engagement
- Each channel posts "mini-episode" clips (1-10 mins long) that are partially edited
- Content is already engaging, but requires:
  - Quality assessment (finding the 3-5 best per day)
  - Format conversion to 9:16 TikTok/Reels (if source is 16:9)
  - Final subtitle burns
  - Human approval before posting

---

## Data Source Analysis

### Option 1: YouTube Data API v3

**Pros:**
- Official Google API — reliable, stable, well-documented
- Channel upload playlist retrieval via `playlistItems.list`
- Video metadata via `search.list`, `videos.list`, `channels.list`
- Thumbnail URLs, view counts, duration, description all accessible
- No browser automation required

**Cons:**
- 10,000 quota units/day (sufficient for polling 10 channels daily)
- Requires API key registration
- No direct video file access (only metadata + thumbnail URLs)
- Streaming/download would still require alternative tools

**Relevant Endpoints:**
| Endpoint | Purpose | Quota Cost |
|----------|---------|-----------|
| `channels.list` | Get `uploads` playlist ID | 1 |
| `playlistItems.list` | Get most recent video IDs | 1 per page |
| `videos.list` | Get duration, title, description, thumbnails | 1 |
| `search.list` | Query by channel ID | 100 |

**Example Workflow:**
```python
# 1. Get channel uploads playlist ID
channels = youtube.channels().list(
    part="contentDetails",
    forUsername="DannyJonesClips"
)

# 2. Get recent video IDs (up to 50)
playlistItems = youtube.playlistItems().list(
    playlistId=channel["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"],
    maxResults=50,
    pageToken=None
)

# 3. Fetch video metadata
videos = youtube.videos().list(
    part="snippet,contentDetails,statistics",
    id=" ,".join(video_ids)
)
```

**Quota Calculation:**
- Polling 10 channels/day × ~50 videos each = 100 `playlistItems` calls
- 100 `videos` calls to get metadata
- **Total: ~200 quota units/day** (well under 10,000 limit)

---

### Option 2: RSS Feed Scraping

**Pros:**
- No API key required
- No quota limits
- Simple XML parsing
- All metadata available in feed

**Cons:**
- YouTube RSS format not officially documented
- May change without notice
- Slower than API for bulk operations
- Rate limiting risk if scraping frequently

**RSS Format:**
```xml
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <yt:videoId>dQw4w9WgXcQ</yt:videoId>
    <yt:duration>PT5M27S</yt:duration>
    <title>Danny Jones - Best Moment From Today's Show</title>
    <media:thumbnail url="https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg" />
  </entry>
</feed>
```

**RSS URL Pattern:**
`https://www.youtube.com/feeds/videos.xml?channel_id=UCxxxxx`

**Pros:**
- Fast initial scraping (can get 50+ videos in one request)
- Duration already parsed in RSS format (PT5M27S)
- View counts not available, but enough for filtering

---

### Recommendation: **Hybrid Approach**

1. **Primary**: RSS scraping for initial video discovery (no quota, fast)
2. **Fallback/Enrichment**: YouTube API for view counts, like counts, detailed metadata
3. **Storage**: Cache RSS feed data in `outputs/cache/rss_cache.json`

---

## Video Source Characteristics

### Danny Jones Clips (Example Channel)

| Attribute | Typical Value |
|-----------|--------------|
| Video Length | 3-10 minutes |
| Format | 16:9 horizontal |
| Subtitles | Often embedded (burned-in) in original |
| Quality | 720p minimum, often 1080p |
| Content | Podcast/stand-up highlights |
| Posting Frequency | 1-3x/day |

### Key Implications for Clipping Pipeline:

1. **Subtitles may already exist** — need to detect if burned-in or separate
2. **Already-edited content** — skip segment selection logic, just pick full video or trimmed segments
3. **Quality preservation** — source likely ≥1080p, should transcode without quality loss (re-encode minimally)
4. **Thumbnail already exists** — no need to extract from first frame

---

## Technical Architecture

### Feature 2 Module Structure

```
/
├── social_crew.py                    # Main orchestrator (feature selection)
├── tools/
│   ├── transcribe.py                 # Feature 1 only (skip for Feature 2)
│   ├── clipping.py                   # Shared (can use for 1080p output)
│   ├── channel_poller.py             # Feature 2 specific
│   └── quality_scoring.py            # Feature 2 specific
├── pipeline/
│   ├── orchestrator.py               # Update to support Feature 2
│   └── agent_factory.py              # Reuse for LLM quality analysis
├── models/
│   └── curation_schema.py            # New: curate_run, curated_clip schemas
├── outputs/
│   └── curation/                     # New: store curated clips separately
└── features/
    └── feature_2_config.yaml         # Channel list, API configs
```

---

## Feature 2 Configuration Schema

### `features/feature_2_config.yaml`

```yaml
# Feature 2: Curated Channel Clipping Configuration

curated_channels:
  - name: "Danny Jones Clips"
    channel_id: "UCxxxxx"  # or forUsername "DannyJonesClips"
    min_duration_sec: 60
    max_duration_sec: 600  # 10 minutes
    tags: ["clips", "highlights", "podcast"]
    quality_threshold: "1080p"
    poll_count_daily: 50  # How many videos to fetch per day

  - name: "Alex Hormozi Clips"
    channel_id: "UCxxxxx"
    # ... same structure

feature_2_defaults:
  output_resolution: "1080p"  # 1080x1920 vertical
  min_clip_confidence: 0.75   # LLM quality score threshold
  max_clips_daily: 5          # Cap on output clips
  subtitle_processing:         # How to handle existing/subtitles
    detect_burned_in: true
    auto_add_if_missing: true
    font: "Arial"
    size: 32
    positions: ["top-40%", "bottom-40%"]
```

---

## Quality Assessment Strategy

### Algorithm: Multi-Factor Scoring

```python
def score_clip_quality(video_metadata, video_download_path):
    """
    Score a clip for posting eligibility using:
    1. View count (engagement)
    2. Duration match (60-600s preferred)
    3. Title optimization (keyword presence)
    4. Visual quality (resolution check)
    5. LLM content quality (semantic analysis)
    """
    score = {
        'views_normalized': video_metadata.view_count / 100000,
        'duration_score': 1.0 if 60 <= video.duration <= 600 else 0.5,
        'title_quality': llm_title_score(video_metadata.title),
        'resolution': video_metadata.resolution_quality,
        'content_quality': llm_content_quality_score(transcript)
    }
    
    return sum(score.values()) / len(score)
```

### LLm-Based Content Quality Analysis

```python
def llm_content_quality_score(transcript, title):
    """
    Prompt: "Analyze this clip transcript and title. 
    Score 0-1 on:
    - Engagement potential
    - Clarity of message
    - Humor/entertainment value
    - Shareability score
    
    Video: {title}\nTranscript: {transcript}"
    """
```

**Why LLM?**
- Human-like understanding of "interesting"
- Can detect sarcasm, puns, clever wordplay
- Understands context-specific references

---

## Clipping Pipeline (Feature 2 Specific)

### Processing Flow

```
1. Poll channels (RSS/API)
   ↓
2. Fetch metadata for each video
   ↓
3. Score videos on quality factors (views, duration, title)
   ↓
4. Select top 3-5 videos
   ↓
5. For each selected:
   a. Check resolution (≥1080p requirement)
   b. Detect existing subtitles (FFmpeg metadata)
   c. Extract or add subtitles
   d. Convert to 9:16 resolution
   e. Burn subtitles dynamically
   f. Generate thumbnail
   ↓
6. Store in outputs/curated/
   ↓
7. Send to user via Telegram (approval request)
```

### FFmpeg Commands for Feature 2

**Option A: Already 1080p, just reformat to vertical**
```bash
ffmpeg -i input.mp4 \
  -vf "crop=iw*0.5625:ih:0:0,split[o0][o1];[o0]scale=1080:-1[ng];[o1]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='%{text}':fontcolor=white:fontsize=32:x=50:y=h-50,scale=1080:-1[v]" \
  -map "[v]" -f mp4 output_1080x1920.mp4
```

**Option B: Add subtitles dynamically (if burned-in detection fails)**
```bash
ffmpeg -i input.mp4 \
  -vf "subtitles=subs_ass.srt:force_style='FontSize=32,Primary=&H00FFFFFF,BorderStyle=1'" \
  -c:a copy -strict experimental output_1080x1920_srt.mp4
```

---

## Implementation Strategy

### Phase 1: Channel Polling Infrastructure (2-3 hours)
- Add `tools/channel_poller.py` with RSS scraping
- Add `features/feature_2_config.yaml` template
- Update `social_crew.py` to support Feature 2 mode
- Store cached RSS data in `outputs/cache/`

### Phase 2: Quality Assessment (3-4 hours)
- Implement `tools/quality_scoring.py` with multi-factor scoring
- LLM prompt integration for semantic quality check
- Threshold configuration (confidence ≥0.75)
- Top-N selection algorithm

### Phase 3: Feature-2 Clipping Pipeline (2-3 hours)
- Update `tools/clipping.py` to accept already-edited input
- Support subtitle detection (FFmpeg `probe`)
- High-fidelity transcoding pipeline
- Skip segment selection (full clips or large segments only)

### Phase 4: Workflow Integration (1-2 hours)
- Update orchestrator to chain polling → scoring → selecting → clipping
- Telegram output format for approval requests (image + metadata)
- Human approval callback handling
- Separate output storage (avoid mixing with Feature 1 clips)

### Phase 5: Testing & Verification (1-2 hours)
- Test with real YouTube channels (Danny Jones, Hormozi)
- Verify 1080p output quality (FFmpeg probe)
- Validate human approval flow
- Quota unit tracking (ensure API remains under limits)

---

## Risk Analysis

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| RSS feed format changes | Medium | Parse both RSS and API; have fallback |
| YouTube API quota limits | Low | Track quota usage; implement caching |
| Source videos <1080p | Medium | Detect early, skip, log warning |
| Burned-in subtitles detection | Medium | Use FFmpeg `mediainfo` to detect stream |
| LLM quality assessment slow | Low | Limit to top-20 candidates after initial filters |
| Channel accounts deleted | Low | Graceful error handling; skip missing channels |

---

## API Quota Management

### Daily Usage Projection:
| Operation | Calls/Day | Units |
|-----------|-----------|-------|
| RSS scraping (10 channels) | 10 | 0 (free) |
| YouTube API: videos.list (top-50 views) | 10 | 10 |
| LLM content quality (top-20 after RSS) | 20 | 20 (Ollama local) |
| **Total Daily Cost** | — | **~30 units** |

**Safe for indefinite operation** without paid API key.

---

## Output File Organization

```
outputs/
├── curated/
│   ├── pending/
│   │   ├── 20260430_123456_clips_danny_jones_1080p.mp4
│   │   ├── 20260430_123456_clips_danny_jones_1080p_thumb.jpg
│   │   └── ...
│   ├── approved/
│   │   └── ... (after Telegram approval)
│   └── rejected/
│       └── ... (user rejects clips)
├── logs/
│   └── feature2_poll.log
└── cache/
    └── rss_cache.json  # Stores recent video IDs to avoid re-polling
```

---

## Telegram Approval Workflow

### Message Format:
```
📺 New Clip Ready for Approval
─────────────────────────────
Channel: Danny Jones Clips
Title: "The Most Interesting Part of Today's Show"
Duration: 3:42
Views: 12,453

🔍 Quality Score: 8.7/10 (LLM verified)

▶️ Preview: [IMAGE of thumbnail]
💬 Caption: "Wait until you hear this... 💀"

[Approve] / [Reject]
─────────────────────────────
Auto-post at: 6:00 PM EST
```

### Callback Data:
- `curate_approve:channel_id:clip_id:timestamp`
- `curate_reject:channel_id:clip_id:timestamp`

---

## Required Dependencies

| Package | Purpose | Installation |
|---------|---------|-------------|
| `google-api-python-client` | YouTube Data API v3 | `pip install` |
| `requests` | RSS scraping | Already present |
| `ffmpeg-python` | Video processing | Already present |
| `faster-whisper` | LLM transcript scoring | Feature 2 optional |

---

## Estimated Time Investment

| Component | Hours | Dependencies |
|-----------|------|-------------|
| RSS scraping + caching | 2.5 | None |
| Quality scoring algorithm | 3.0 | RSS complete |
| LLM quality assessment | 2.0 | Quality scoring |
| Clipping pipeline updates | 2.5 | Scoring complete |
| Telegram approval flow | 1.5 | Clipping complete |
| Testing + verification | 1.5 | All features |
| **Total** | **~13 hours** | N/A |

**One day of work (6-8 hours) can complete MVP; full polish needs 2 days.**

---

## Integration with Feature 1

### Shared Components:
| Component | Reuse | Change |
|-----------|-------|--------|
| `tools/clipping.py` | ✅ Yes | Add parameter for subtitle source detection |
| `pipeline/agent_factory.py` | ✅ Yes | LLM calls identical |
| `models/run_schema.py` | ✅ Yes | Add `CuratedClip` schema |
| `outputs/` structure | ⚠️ Partial | Add `curated/` subdirectory |

### Unique Components (Feature 2 Only):
- `tools/channel_poller.py`
- `tools/quality_scoring.py`
- `models/curated_run_schema.py`
- Feature 2 config YAML
- Telegram approval logic

---

## Next Research: API vs RSS Deep Dive

### Open Questions:
1. **Subtitles detection** — can we reliably detect burned-in text in any source video?
   - Need: FFmpeg `mediainfo` probe + OCR fallback (tesseract)
2. **Video download for LLM analysis** — YouTube to local disk for full transcript analysis.
   - Need: `yt-dlp` CLI integration for high-quality download
3. **Rate limiting** — YouTube RSS may throttle after aggressive polling
   - Need: Retry with exponential backoff; cache per-channel

### Recommended Next Steps:
1. Create test script to probe subtitle streams in Danny Jones clips
2. Implement yt-dlp download pipeline for local transcript analysis
3. Start Feature 1 implementation with minimal working version, then iterate

---

## Appendix: Sample Channels for Polling

| Channel | Format | Avg Duration | Notes |
|---------|-------|-------------|-------|
| Danny Jones Clips | 16:9 | 3-8 min | Always high engagement |
| Alex Hormozi Clips | 16:9 | 2-5 min | Business/motivation |
| MrBeast Shorts | 9:16 | 50-60 sec | Already vertical |
| GaryVee Clips | 16:9 | 1-4 min | High energy |
| Joe Rogan clips | 16:9 | 5-12 min | Variable quality |
| Andrew Tate clips | 16:9 | 2-6 min | Controversial but engaging |
| ... | ... | ... | User's list of 10 |

---

## Document Metadata

- Created: April 30, 2026
- Author: revenue_crew research assistant
- Version: 1.0
- Status: Final draft for review
- Next: Phase 1 implementation (channel polling)
