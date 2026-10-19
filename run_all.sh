#!/usr/bin/env bash
# Runs the whole experiment with one command:
#   ingest -> teacher scan -> lessons -> student before / placebo / after -> report
#
#   ./run_all.sh                 models from .env (TEACHER_MODEL, STUDENT_MODEL, ...)
#   ./run_all.sh --free          free preset: everything on Groq with open models
#                                (teacher gpt-oss-120b, student gpt-oss-20b); needs GROQ_API_KEY
#   ./run_all.sh --app my.apk    a different app (.apk or decompiled folder); combine with --free
#
# Output: runs/<time>/report.md (also copied to docs/results.md) and runs/<time>/run.log
# Survives logout:  nohup ./run_all.sh --free > /dev/null 2>&1 &
set -euo pipefail
cd "$(dirname "$0")"
[ -f .venv/bin/activate ] && source .venv/bin/activate

APP_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --free)
      export TEACHER_MODEL=openai/gpt-oss-120b TEACHER_BASE_URL=https://api.groq.com/openai/v1
      export TEACHER_API_KEY_ENV=GROQ_API_KEY TEACHER_MAX_CHUNK_CHARS=12000 TEACHER_MAX_TOKENS=8192
      export STUDENT_MODEL=openai/gpt-oss-20b STUDENT_BASE_URL=https://api.groq.com/openai/v1
      export STUDENT_API_KEY_ENV=GROQ_API_KEY
      shift ;;
    --app) APP_ARGS=(--app "$2"); shift 2 ;;
    *) echo "unknown option: $1"; exit 1 ;;
  esac
done

LOG=runs/run_all.log
mkdir -p runs
{
  echo "=== $(date)  ingest"
  python3 -u main.py ingest ${APP_ARGS[@]+"${APP_ARGS[@]}"}
  echo "=== $(date)  teacher -> lessons -> students"
  python3 -u main.py loop ${APP_ARGS[@]+"${APP_ARGS[@]}"}
  echo "=== $(date)  done"
} 2>&1 | tee "$LOG"

OUT=$(grep -o 'All outputs saved in [^ ]*' "$LOG" | tail -1 | sed 's/All outputs saved in //; s:/$::')
cp "$LOG" "$OUT/run.log"
echo
echo "Report:  $OUT/report.md"
if [ ${#APP_ARGS[@]} -eq 0 ]; then
  cp "$OUT/report.md" docs/results.md
  echo "Copied:  docs/results.md"
fi
