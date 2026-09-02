#!/bin/sh
# Copies the raw Claude Code session transcripts for this project into
# transcript/ untouched (JSON Lines, one event per line, dead ends included).
# Run this after the run seals, then commit. Safe to re-run.
set -eu
SRC="$HOME/.claude/projects/-Users-Yash-Developer-characterquilt-challenge-1"
DST="$(cd "$(dirname "$0")/.." && pwd)/transcript"
mkdir -p "$DST"
for f in "$SRC"/*.jsonl; do
  cp "$f" "$DST/"
  printf '%s  %s lines\n' "$(basename "$f")" "$(wc -l < "$f" | tr -d ' ')"
done
echo "copied to $DST"
