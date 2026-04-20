#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_PATH="$ROOT_DIR/gateway/openclaw.local.json5"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Missing config: $CONFIG_PATH" >&2
  echo "Copy gateway/openclaw.local.example.json5 to gateway/openclaw.local.json5 first." >&2
  exit 1
fi

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi

if ! command -v openclaw >/dev/null 2>&1; then
  echo "Official OpenClaw CLI is not installed or not on PATH." >&2
  echo "Install it first: npm install -g openclaw@latest" >&2
  exit 1
fi

OPENCLAW_CONFIG_PATH="$CONFIG_PATH" openclaw gateway "$@"
