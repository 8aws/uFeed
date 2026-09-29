#!/usr/bin/env bash
# Export the translation models (opus-mt, 8-bit OpenVINO IR) into the AI
# models volume. Needed once per box (and after adding a pair to AI_MT_PAIRS).
# The exporter requires transformers<=4.57, older than the AI image's, so it
# runs in a throwaway container from the same image with that version pinned;
# the running service is untouched and only loads the exported files.
#
# Usage (on the box, in the uFeed directory): ./scripts/export_mt.sh
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose run --rm --no-deps -T --entrypoint sh ai -c '
  pip install -q "transformers==4.57.6" sentencepiece sacremoses 2>/dev/null
  HF_HOME=/tmp/hf python -m app.mt_export'
