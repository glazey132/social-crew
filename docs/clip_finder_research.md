# Smart Clip Finder — Feature 3: Video-to-Clip AI
## Deep Research Document

**Project**: revenue_crew  
**Feature**: Extract optimal clips from user-provided video URLs  
**Status**: Research (April 30, 2026)  
**Target**: User provides video URL → AI finds 3-10 best clips → Auto-process → Human approval

---

## Overview

This document outlines the technical and operational requirements for **Feature 3** of revenue_crew — a system that accepts a user-specified YouTube video URL, transcribes and analyzes its full content, identifies the most engaging/potentially viral segments (15-60s), and auto-processes them into TikTok/Reels-ready clips.

This addresses a real workflow pain point: finding valuable content in long-form videos, capturing those segments manually via OBS, transferring files between devices, and losing momentum.

---

## Use Case Definition

### Current Pain Points (User's Workflow)

```
1. Discover long-form video worth clipping (e.g., 2-hour podcast)
2. Manually watch through to find interesting moments
3. Open OBS, record the segment you like
4. Transfer recorded clip from laptop to phone
5. Edit captions/title, post
6. Repeat for each valuable segment
```

**Issues:**
- Time-intensive (watching entire video, manual recording)
- Human error (miss moments, poor timing)
- Friction point (laptop → phone transfer)
- Inconsistent output (varying quality, no captions)

### Feature 3 Solution

```
1. User provides YouTube URL (or uploads local video)
2. AI transcribes entire video, analyzes content quality
3. System identifies top 3-10 best segments
4. Auto-clips each to 1080p vertical with captions
5. User reviews clips via Telegram
6. Approve/reject → auto-post or save to library
```

**Benefits:**
- Saves 2-3 hours per video (no manual watching/recording)
- Consistent quality output (1080p, captions, same style)
- No file transfer friction (direct from script to phone)
- AI finds high-value moments you might miss

---

## Technical Approach

### Two Implementation Paths

#### Option A: Pure YouTube URL (Recommended for MVP)

**Pros:**
- No local file storage required
- Leverages existing YouTube Infrastructure
- Automatic metadata (view count, duration)
- Seamless integration with current Feature 1 codebase

**Cons:**
- Only works for public YouTube videos
- Requires API key for certain operations
- Transcription must be done via transcript API or download

**Flow:**
```
User provides: https://youtube.com/watch?v=VIDEO_ID
↓
1. Extract video ID and metadata via YouTube API
2. Download transcript (YouTube auto-generated or speech_recognition)
3. Score transcript segments
4. Download video segment via yt-dlp
5. Clip to 9:16 with captions
6. Return results to user
```

**YouTube Transcript Access:**

| Method | Cost | Quality | Time |
|--------|------|---------|------|
| YouTube API transcripts (auto-generated) | 0 quota | 70-85% accuracy | Fast |
| yt-dlp download transcript (manual uploads) | Local only | 100% accuracy | Medium |
| Whisper transcription (download + process) | Ollama local | 90%+ accuracy | Slow but best |

**Recommendation**: Start with YouTube API auto-generated transcripts, fallback to local Whisper if poor quality.

---

#### Option B: Local Video File Upload

**Pros:**
- Works offline
- Any video format (MP4, MOV, MKV, etc.)
- Full control over source quality
- No API dependencies

**Cons:**
- Requires disk storage for upload buffer
- Manual file transfer (user must upload first)
- Slower initial workflow (file size can be 500MB-2GB)

**Flow:**
```
User uploads: /Users/alex/Downloads/podcast_episode_42.mp4
↓
1. Store to temp directory
2. Run local Whisper transcription
3. Segment scoring and selection
4. Clip rendering
5. Delete temp files after processing
```

**FFmpeg Compatibility Check:**
- Must detect video codec (H.264, HEVC, VP9)
- Audio codec detection (AAC, MP3, Vorbis)
- Resolution detection (for cropping strategy)
- Duration detection (for segment bounds)

---

### Recommended Hybrid Approach

**Feature 2.5**: Accept both YouTube URLs and local files — user preference via CLI flag or config.

```bash
# Clip from YouTube URL
python social_crew.py --mode clip_finder --url "https://youtube.com/watch?v=abc123"

# Clip from local file
python social_crew.py --mode clip_finder --file "/path/to/podcast.mp4"
```

Both routes converge on the same segment scoring → clipping pipeline.

---

## Core Algorithm: Segment Identification

### Multi-Phase Scoring Pipeline

```
Input: Full video transcript (or local audio transcript)
↓
PHASE 1: Quick filters (duration, keywords)
  - Discards segments <15s or >120s
  - Scores based on keyword presence (hook words)
  - Result: Top 50 candidates
↓
PHASE 2: Semantic quality analysis (LLM)
  - Analyze top 50 for engagement potential
  - Score: humor, emotion, controversy, value proposition
  - Result: Top 10 candidates
↓
PHASE 3: Human-friendly curation (LLM + heuristics)
  - Ensure diversity (not all in same topic)
  - Spread out segments across full video
  - Result: Final 3-10 segments for output
```

### Scoring Criteria (Detailed)

#### Phase 1: Keyword-Based Scoring (Instant, 0ms per segment)

**Keywords and Weights:**
| Word/Phrase | Score |
|------------|-----|
| "Here's the thing", "Wait", "Listen to this" | +0.8 |
| "The biggest mistake", "Never do this", "Don't" | +0.7 |
| "Why", "How", "What if", "Secret" | +0.6 |
| "I was shocked", "This changed my life" | +0.5 |
| "Here's how", "Step 1", "First", "Second" | +0.4 |

**Duration Scoring:**
```python
def duration_score(seconds):
    if seconds < 15: return 0.0
    if 15 ≤ seconds ≤ 30: return 0.4
    if 31 ≤ seconds ≤ 60: return 0.8
    if 61 ≤ seconds ≤ 90: return 1.0
    if 91 ≤ seconds ≤ 120: return 0.7
    return 0.0
```

**Result**: Each segment gets a `quick_score` between 0.0-1.0.

---

#### Phase 2: Semantic Quality Analysis (LLM, ~500ms per segment)

**Prompt Design:**
```
You are a social media content curator. Analyze this video segment transcript:

Segment Start Time: {start_time}
Duration: {duration_seconds} seconds
Transcript: "{full_transcript_text}"

Score 0.0-10.0 on:
- **Hook Strength** (opening 3 words grab attention?)
- **Value Proposition** (clear benefit/insight delivered?)
- **Emotion** (excitement, tension, humor, empathy)
- **Shareability** (would people screenshot/share this?)

Provide:
1. Numeric score (0-10)
2. One-sentence reason
3. Best social caption (if applicable)
```

**Expected Output (JSON):**
```json
{
  "engagement_score": 8.7,
  "reason": "Strong opening hook with 'wait until you hear this' followed by actionable advice on time management.",
  "caption": "The one time management trick that saved me 2hrs/day 🧵"
}
```

**Implementation:**
- Use local Ollama + Qwen3.5 35B (already available)
- Batch process top 50 segments (max 25 seconds total)
- Cache results in `outputs/clip_finder_cache.json`

---

#### Phase 3: Diversity & Spacing Optimization (Heuristic)

**Constraints:**
- Output max 10 clips (user preference configurable)
- Spread clips across video (no 10 clips in first 5 minutes)
- Avoid duplicate topics (if 5 clips are "productivity tips", select 5 "different topics")

**Algorithm:**
```python
def optimize_clip_selection(candidates, target_count=5):
    """
    Greedy selection with diversity + spacing constraints
    """
    selected = []
    remaining = candidates.copy()
    
    while len(selected) < target_count and remaining:
        # Score each remaining candidate on spacing + uniqueness
        for candidate in remaining:
            space_score = calculate_distance_to_current(selected)
            topic_score = calculate_topic_diversity(selected, candidate)
            candidate.total_score = candidate.llm_score * (space_score * 0.5 + topic_score * 0.5)
        
        # Pick highest-scoring
        best = max(remaining, key=lambda x: x.total_score)
        selected.append(best)
        remaining.remove(best)
        
        # Enforce min spacing (30s between clips to avoid overlap)
        remaining = [c for c in remaining if abs(c.start_time - best.start_time) > 30]
    
    return sorted(selected, key=lambda x: x.start_time)
```

---

## Technical Stack

### YouTube URL Processing

| Dependency | Purpose | Installation |
|------------|---------|-------------|
| `yt-dlp` | YouTube video download + metadata | `pip install yt-dlp` |
| `google-api-python-client` | YouTube Data API v3 (optional, for transcripts) | `pip install google-api-python-client` |
| `ffmpeg-python` | Video segment extraction | Already present |
| `faster-whisper` | Transcript extraction (if local upload) | Already present |

**Why `yt-dlp`?**
- More reliable than youtube-dl (maintenance, updates)
- Works offline once installed (no API quota)
- Extracts metadata (title, duration, views, thumbnail)
- Downloads subtitles (auto-translated) if available
- Can also extract transcripts from video file

**Installation for macOS:**
```bash
brew install yt-dlp
# Or pip install yt-dlp (works cross-platform)
```

**Verification:**
```bash
yt-dlp --version
yt-dlp --extractor-args "youtube:skip=dash,audio" --dump-json "https://youtube.com/watch?v=VIDEO_ID"
```

---

### Local File Processing

| Dependency | Purpose | Installation |
|------------|---------|-------------|
| `ffmpeg` | Video metadata detection | Already present |
| `faster-whisper` | Full transcript generation | Already present |
| `ctranslate2` | Whisper inference backend | Already present |

**File Upload Handling:**
```python
class UploadedVideoFile:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.duration_sec = ffmpeg_probes_duration(self.file_path)
        self.resolution = ffmpeg_probes_resolution(self.file_path)
        self.has_audio_stream = ffmpeg_probes_has_audio(self.file_path)
        
    def get_temp_storage(self) -> Path:
        temp_dir = Path("/tmp/revenue_crew/uploaded")
        temp_dir.mkdir(exist_ok=True)
        return temp_dir / self.file_path.name
```

**Processing Flow:**
```python
video = UploadedVideoFile("/Users/alex/Downloads/podcast.mp4")
video_storage = video.get_temp_storage()
whisper_transcript = faster_whisper.transcript(video.file_path, model="medium")
segments = segment_scorer(whisper_transcript, max_segments=10)
clips = clip_renderer(segments, output_path=video_storage.parent / "clips")
```

---

## Integration with Existing Codebase

### Reuse from Feature 1 (Pure YouTube URL Processing)

| Component | Reuse? | Modification |
|----------|-------|--------------|
| `tools/transcribe.py` | ✅ Yes | Add URL download logic, extract transcript |
| `tools/clipping.py` | ✅ Yes | Accept input from local file path (already works) |
| `models/run_schema.py` | ✅ Yes | Add `ClipFinderRun` schema |
| `pipeline/agent_factory.py` | ✅ Yes | LLM scoring pipeline identical |
| `outputs/` structure | ✅ Yes | Add `clip_finder/` subdirectory |

**New Components (Feature 3 Only):**
- `tools/clip_finder.py` — orchestrates URL/file processing, scoring
- `tools/segment_scorer.py` — multi-phase scoring algorithm
- `models/clip_finder_schema.py` — output schemas
- `cli.py` — CLI interface for `social_crew.py --clip_finder`

---

### Schema Definitions

#### `models/clip_finder_schema.py`

```python
from pydantic import BaseModel
from typing import List, Optional

class ClipCandidate(BaseModel):
    candidate_id: str        # Unique segment ID
    start_sec: float         # Start time in seconds
    end_sec: float           # End time in seconds
    segment_text: str        # Full transcript segment
    quick_score: float       # 0-1 keyword score
    llm_engagement_score: Optional[float]  # 0-10 LLM score (after Phase 2)
    llm_reason: Optional[str]                  # Why this clip is good
    suggested_caption: Optional[str]           # Auto-generated social caption
    
class ClipFinderRun(BaseModel):
    """
    Record of a Clip Finder run
    """
    run_id: str
    start_time: datetime
    end_time: Optional[datetime]
    status: str  # "pending", "processing", "complete", "failed"
    input_source: str  # "youtube_url" | "local_file"
    source_path: str  # URL or file path
    total_duration: float  # Video duration in seconds
    total_segments_analyzed: int
    segments: List[ClipCandidate]
    approved_clips: Optional[List[int]]  # Array of indices approved
    output_paths: Optional[List[str]]    # Paths to generated clip files
    
    class Config:
        json_schema_extra = {
            "example": {
                "run_id": "cf_20260430_123456",
                "start_time": "2026-04-30T12:34:56Z",
                "input_source": "youtube_url",
                "source_path": "https://youtube.com/watch?v=abc123",
                "total_duration": 3600.0,  # 1 hour
                "total_segments_analyzed": 87,
                "segments": [
                    {
                        "candidate_id": "1",
                        "start_sec": 45.0,
                        "end_sec": 78.0,
                        "segment_text": "Wait until you hear this one thing that...",
                        "quick_score": 0.89,
                        "llm_engagement_score": 8.7,
                        "llm_reason": "Strong hook with curiosity gap...",
                        "suggested_caption": "The secret nobody tells you about 💀"
                    },
                    ...
                ],
                "approved_clips": [0, 2, 4],  # Indices of approved segments
                "output_paths": ["/Users/alex/revenue_crew/outputs/clip_finder/..."]
            }
        }
```

---

## CLI Interface Design

### Usage Examples

```bash
# Clip from YouTube URL
python social_crew.py --mode clip_finder --url "https://youtube.com/watch?v=VIDEO_ID" \
  --max-clips 5 --output-dir ./outputs/clip_finder \
  --use-llm-score true  # enable LLM quality analysis (default: true)

# Clip from local file
python social_crew.py --mode clip_finder --file "/path/to/video.mp4" \
  --max-clips 8 --skip-llm-score true  # skip LLM for speed (only keyword scoring)

# Dry run (analyze but don't render)
python social_crew.py --mode clip_finder --url "VIDEO_URL" \
  --dry-run true --output-dir ./outputs/clip_finder --output-only-text

# Telegram integration (send results for approval)
python social_crew.py --mode clip_finder --url "VIDEO_URL" \
  --telegram true --chat-id 123456789
```

### Argument Parser Structure

```python
import argparse

parser = argparse.ArgumentParser(description="Revenue Crew - Auto Clip Finder")

subparsers = parser.add_subparsers(dest="mode")

clip_finder_parser = subparsers.add_parser(
    "clip_finder", 
    help="Analyze video and extract best segments"
)

clip_finder_parser.add_argument(
    "--url", 
    type=str, 
    help="YouTube video URL (required if not using --file)"
)

clip_finder_parser.add_argument(
    "--file", 
    type=str, 
    required=False, 
    help="Local video file path"
)

clip_finder_parser.add_argument(
    "--max-clips", 
    type=int, 
    default=5, 
    help="Maximum number of clips to extract"
)

clip_finder_parser.add_argument(
    "--use-llm-score", 
    action="store_true", 
    help="Enable LLM-based quality scoring (slower but more accurate)"
)

clip_finder_parser.add_argument(
    "--skip-llm-score", 
    action="store_true", 
    help="Skip LLM scoring for speed"
)

clip_finder_parser.add_argument(
    "--dry-run", 
    action="store_true", 
    help="Analyze but don't render clips"
)

clip_finder_parser.add_argument(
    "--output-dir", 
    type=str, 
    default="./outputs/clip_finder",
    help="Output directory for generated clips"
)

clip_finder_parser.add_argument(
    "--telegram", 
    action="store_true", 
    help="Send results to Telegram for approval"
)

# Parse and dispatch
args = parser.parse_args()

if args.mode == "clip_finder":
    handle_clip_finder(args)
elif args.url and args.file:
    parser.error("Cannot specify both --url and --file")
elif not args.url and not args.file:
    parser.error("One of --url or --file is required")
```

---

## Output Structure

```
outputs/
├── clip_finder/
│   ├── pending/
│   │   ├── 20260430_123456_yt_abc123_clip_01.mp4
│   │   ├── 20260430_123456_yt_abc123_clip_01_thumb.jpg
│   │   ├── ...
│   │   └── 20260430_123456_yt_abc123_segments.json  # Metadata file
│   ├── approved/
│   │   └── ... (after Telegram approval)
│   └── rejected/
│       └── ... (user rejects via Telegram)
└── cache/
    └── clip_finder_transcript_cache.json  # Store transcripts to avoid re-transcribing
```

**Metadata File Format (segments.json):**
```json
{
  "run_id": "cf_20260430_123456",
  "timestamp": "2026-04-30T12:34:56Z",
  "source_type": "youtube_url",
  "source_path": "https://youtube.com/watch?v=abc123",
  "total_duration_seconds": 3600,
  "segments": [
    {
      "index": 0,
      "start_sec": 45.0,
      "end_sec": 78.0,
      "text": "The one thing that changed my life...",
      "quick_score": 0.89,
      "llm_score": 8.7,
      "caption": "This one thing will save you hours...",
      "approved": true,
      "output_file": "cf_20260430_123456_yt_abc123_clip_01.mp4"
    }
  ]
}
```

---

## User Workflow Integration

### Manual Approval Flow (CLI/Telegram)

**Step 1: Run Clip Finder**
```bash
python social_crew.py --mode clip_finder --url "https://youtube.com/watch?v=abc123" --telegram
```

**Step 2: Receive Telegram Message**
```
🎬 Clip Finder Results

Video: "How I Built a $1M Business" (1:00:00)
Analyzed: 87 segments
Top 5 Clips Identified:

1️⃣ 0:45 - "Wait until you hear this..." (Score: 8.7/10)
   Caption: "The secret nobody tells you about 💀"
   
2️⃣ 2:30 - "Here's how to double your income" (Score: 9.2/10)
   Caption: "Double your income in 30 days 📈"
   
3️⃣ 5:12 - "The biggest mistake beginners make" (Score: 7.8/10)
   Caption: "Don't make this costly mistake! 💸"
   ...

✅ [Approve All] / ❌ [Reject All]
Or select individual clips via:
[1] [2] [3] [4] [5]

───
Auto-post: Pending approval
───
```

**Step 3: User Responds**
- Approves some clips → they move to `outputs/clip_finder/approved/`
- Rejects others → move to `outputs/rejected/`
- No response → timeout (7 days), auto-delete pending clips

---

## Processing Time Estimates

| Operation | Duration (YouTube URL) | Duration (Local File) |
|-----------|----------------------|--------------------|
| Download video metadata | ~5 seconds | N/A |
| Transcription (1 hour video) | ~45s (auto-gen) | ~5 min (Whisper) |
| Segment scoring (10 segments) | ~5 seconds | ~5 seconds |
| LLM analysis (5 segments) | ~5-10 seconds | ~5-10 seconds |
| Video clip rendering | ~2-5 minutes (5 clips) | ~2-5 minutes |
| **Total (1 hour video)** | **~6 minutes** | **~6-7 minutes** |
| **Total (30 minute video)** | **~3-4 minutes** | **~3-5 minutes** |

**Speedup for large videos:**
- Pre-transcript caching (one-time cost)
- Skip LLM scoring for speed (keyword scoring only)
- Parallel segment processing (FFmpeg can render 2-3 simultaneously)

---

## Edge Case Handling

| Scenario | Risk Level | Handling Strategy |
|----------|-----------|-------------------|
| Transcript unavailable on YouTube | Low | Download video, use local Whisper fallback |
| Video <15s duration | Low | Skip, log warning ("Video too short to clip") |
| Video already 9:16 vertical | Low | Crop horizontally (center) instead of 16:9 crop |
| No subtitles in source video | Medium | Whisper transcription handles missing subtitles |
| Burned-in subtitles present | Medium | Detect with FFmpeg metadata, skip adding own subtitles |
| Video quality <720p | Medium | Warn user, still process, note quality may not meet standard |
| Video URL deleted/privacy change | Medium | Retry 3 times, then fail with clear error message |
| Ollama/LLM service unavailable | Low | Fallback to keyword-only scoring (no LLM analysis) |
| FFmpeg encoding fails | Low | Retry with different codec options |

---

## Performance Optimization Strategies

### 1. Transcript Caching

```json
// outputs/cache/transcript_cache.json
{
  "yt_abc123": {
    "timestamp": "2026-04-30T12:34:56Z",
    "video_duration": 3600,
    "transcript": [...]
  }
}
```

**On-run check:**
```python
if video_id in transcript_cache:
    log("Using cached transcript for yt_abc123")
    transcript = transcript_cache[video_id]["transcript"]
else:
    transcript = download_transcript(video_id)
    transcript_cache[video_id] = {"timestamp": now, "transcript": transcript}
```

**Benefit**: Transcribing a video twice takes only ~5 seconds instead of ~45 seconds.

---

### 2. Parallel Clip Rendering

FFmpeg can render multiple clips in parallel (CPU/GPU dependent):

```python
from concurrent.futures import ThreadPoolExecutor

def render_clips_parallel(clips, max_workers=3):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(clip_render, clip) for clip in clips]
        results = [future.result() for future in futures]
    return results
```

**Benefit**: 10 clips rendered in ~3 minutes vs ~6 minutes sequential.

---

### 3. Keyword-Only Fast Path

```python
if args.skip_llm_score:
    log("Using keyword-only scoring (faster, no LLM)")
    segments = keyword_scoring(transcript, max_candidates=20)
    # Skip LLM analysis, output segments directly
else:
    segments = keyword_scoring(transcript, max_candidates=50)
    segments = llm_scoring(segments)  # Phase 2
    
    # Filter to top 10
    segments = segments[:10]
```

**Use Case**: User wants quick results, may accept lower accuracy.

---

## API Quota Impact

| Operation | Quota Cost | Frequency |
|-----------|-----------|----------|
| Video metadata via YouTube API | 1 | Once per run |
| Video download (yt-dlp) | 0 | — |
| Auto-transcript access | 0 (cached) | — |
| Whisper transcription (local) | 0 (local) | One-time per video |
| **Total per run** | **1 quota unit** | Safe for unlimited runs |

**Note**: YouTube transcript download via `yt-dlp` does NOT use API quota — only API-based transcript access does.

---

## Implementation Timeline

| Phase | Task | Estimated Hours | Dependencies |
|------|------|----------------|---------|
| **Phase 1** | CLI interface + argument parsing | 0.5h | None |
| **Phase 2** | YouTube URL processing (yt-dlp download) | 2.0h | Phase 1 |
| **Phase 3** | Segment scoring algorithm (keyword + LLM) | 2.5h | Phase 2 |
| **Phase 4** | FFmpeg clip rendering pipeline | 2.0h | Phase 3 |
| **Phase 5** | Telegram integration (approval workflow) | 1.5h | Phase 4 |
| **Phase 6** | Testing (YouTube URLs, local files, edge cases) | 2.0h | Phase 5 |
| **Total** | **MVP Feature 3** | **~8.5 hours** | — |

**Can be completed in one day with iterative testing.**

---

## Comparison: Feature 2 vs Feature 3

| Feature | Purpose | Input | Output | Use Case |
|---------|---------|-------|--------|----------|
| **Feature 1: Source Video Clipping** | Find segments from long content | YouTube URL | 3-10 clips | User has long video, wants best clips |
| **Feature 2: Curated Channel Polling** | Daily discovery of quality clips | Channel list | 3-5 clips/day | User trusts specific channels |
| **Feature 3: Clip Finder (New)** | Extract best segments from specific video | YouTube URL OR local file | 3-10 clips | User has specific video in mind, wants to skip manual selection |

**Feature 3 vs Feature 1: What's different?**
- Feature 1: Transcribe + segment scoring to find 3-5 best clips automatically
- Feature 3: User explicitly selects video to clip (e.g., new podcast episode just dropped), wants ALL good segments found from that one video

**Overlap?** Yes, but Feature 3 is more user-controlled (explicit video selection) vs Feature 1 automated discovery.

---

## Technical Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|-------|-----------|
| YouTube auto-transcripts low quality | Medium | Medium | Fallback to local Whisper or keyword-only mode |
| `yt-dlp` breaks with YouTube updates | Low | Medium | Pin specific `yt-dlp` version; monitor for updates |
| LLM scoring too slow | Medium | Low | Batch processing + parallel execution, fallback to keyword-only |
| User uploads corrupted video file | Low | High | FFmpeg error handling + clear error messages |
| File system disk space exhausted | Low | Low | Implement temp file cleanup post-processing |

---

## Next Steps for Feature 3 Implementation

1. **Start with Feature 3 MVP** (keyword-only scoring, YouTube URLs only)
2. **Add LLM quality scoring** (Phase 2 enhancement)
3. **Add local file upload support** (Phase 3 enhancement)
4. **Add Telegram approval flow** (Phase 5)
5. **Add transcript caching** (optimization)
6. **Add parallel clip rendering** (optimization)

**Recommendation**: Build incrementally, test each phase with real YouTube URLs before adding complexity.

---

## Appendix: Sample Test Scripts

### Test: YouTube URL Processing
```bash
#!/bin/bash
# test_clip_finder_youtube.sh

python social_crew.py \
  --mode clip_finder \
  --url "https://youtube.com/watch?v=dQw4w9WgXcQ" \
  --max-clips 5 \
  --use-llm-score \
  --output-dir ./outputs/clip_finder/test
```

### Test: Local File Processing
```bash
#!/bin/bash
# test_clip_finder_local.sh

python social_crew.py \
  --mode clip_finder \
  --file "/Users/alex/Downloads/test_podcast.mp4" \
  --max-clips 8 \
  --skip-llm-score \
  --output-dir ./outputs/clip_finder/test
```

---

## Document Metadata

- Created: April 30, 2026
- Author: revenue_crew research assistant
- Version: 1.0
- Status: Final draft for review
- Next: Phase 1 implementation (CLI + YouTube URL processing)
