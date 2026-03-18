#!/usr/bin/env bash
set -e

API="${API_URL:-http://localhost:8000}"
echo "Using API: $API"

echo "Building and starting containers..."
docker compose build
docker compose up -d

echo "Waiting for backend to be ready..."
for i in {1..30}; do
  if curl -sf "$API/health" > /dev/null 2>&1; then
    echo "Backend is ready."
    break
  fi
  if [ $i -eq 30 ]; then
    echo "Backend did not become ready in time."
    exit 1
  fi
  sleep 1
done

echo "Seeding data..."
docker compose exec -T backend uv run python scripts/seed.py

echo "Running analysis..."
curl -sf -X POST "$API/workspaces/1/analyze" | head -c 200
echo ""

echo "Generating recommendations..."
curl -sf -X POST "$API/workspaces/1/recommendations/generate" | head -c 200
echo ""

echo ""
echo "Demo ready! Open http://localhost:3000"
echo "Backend: $API"
