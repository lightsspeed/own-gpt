#!/usr/bin/env sh
# Pull the Ollama models used by OwnGPT into the persistent volume.
# Idempotent: models already present are no-ops (no re-download).
# Run from the repo root after `docker compose up -d`:
#   ./scripts/pull_ollama_models.sh
set -e

docker compose exec -T ollama ollama pull qwen3:8b
docker compose exec -T ollama ollama pull nomic-embed-text

echo "Ollama models ready:"
docker compose exec -T ollama ollama list
