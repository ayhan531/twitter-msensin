#!/usr/bin/env bash
echo "Starting X BIST Bot Web Dashboard on port ${PORT:-8000}..."
uvicorn web.app:app --host 0.0.0.0 --port "${PORT:-8000}"
