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

## Run Daily Pipeline

```bash
python social_crew.py
```

Pipeline output:
- Rendered clip artifacts in `OUTPUT_DIR` (default `outputs/`)
- SQLite state in `pipeline_state.db` (unless overridden)
- Telegram messages for approval review

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
- State persistence transitions
- Telegram callback parsing

