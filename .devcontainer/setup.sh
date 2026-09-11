#!/bin/bash
# This script runs automatically the first time the Codespace is created.
# It requires no input from you — just wait for it to finish.
set -e

echo "=========================================="
echo " GO OS — setting up your environment"
echo " This takes a few minutes the first time."
echo "=========================================="

# Create the local environment file from the example, if it doesn't exist yet.
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

# Build and start Postgres, Redis, the API, the worker, and the web dashboard.
echo "Building and starting all services (Postgres, Redis, API, worker, web)..."
docker compose up -d --build

echo "=========================================="
echo " Done. Once the ports panel shows 3000 as"
echo " forwarded, click 'Open in Browser' there"
echo " (or use the popup notification) to see"
echo " the GO OS dashboard."
echo "=========================================="
