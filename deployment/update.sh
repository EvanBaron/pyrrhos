#!/bin/bash
set -e

PROJECT_DIR="/root/pyrrhos-bot"

echo "[$(date)] Triggering update..."

cd "$PROJECT_DIR"

git pull origin main

docker compose up -d --build

docker image prune -f

echo "[$(date)] Update complete."
