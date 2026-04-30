#!/bin/bash

# Run pipeline in dry-run mode for testing

set -e

cd /Users/alexglaze/revenue_crew

# Activate virtual environment
source venv/bin/activate

# Create a test .env with dry-run enabled
cat > .env.test << 'EOF'
LLM_MODEL=ollama/qwen3.5:35b-a3b
LLM_BASE_URL=http://localhost:11434
WORKSPACE_DIR=/Users/alexglaze/revenue_crew
OUTPUT_DIR=/Users/alexglaze/revenue_crew/outputs
STATE_DB_PATH=/Users/alexglaze/revenue_crew/pipeline_state.db
TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat_id
DAILY_CLIP_LIMIT=3
MAX_CANDIDATES=5
DRY_RUN=true
EOF

echo "Running pipeline in DRY_RUN mode..."
LLM_MODEL=ollama/qwen3.5:35b-a3b \
LLM_BASE_URL=http://localhost:11434 \
WORKSPACE_DIR=/Users/alexglaze/revenue_crew \
OUTPUT_DIR=/Users/alexglaze/revenue_crew/outputs \
STATE_DB_PATH=/Users/alexglaze/revenue_crew/pipeline_state.db \
TELEGRAM_BOT_TOKEN=test_token \
TELEGRAM_CHAT_ID=test_chat_id \
DAILY_CLIP_LIMIT=3 \
MAX_CANDIDATES=5 \
DRY_RUN=true \
python social_crew.py 2>&1

echo ""
echo "✓ Dry-run test completed"
