#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8765}"
HOST="${HOST:-127.0.0.1}"
PID_FILE="$ROOT_DIR/.ui.pid"

find_pid() {
  lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true
}

status() {
  local pid
  pid="$(find_pid)"
  if [[ -n "$pid" ]]; then
    echo "UI is running on http://$HOST:$PORT (PID: $pid)"
  else
    echo "UI is not running on port $PORT"
  fi
}

start() {
  local pid
  pid="$(find_pid)"
  if [[ -n "$pid" ]]; then
    echo "UI is already running on http://$HOST:$PORT (PID: $pid)"
    return 0
  fi

  (
    cd "$ROOT_DIR"
    nohup env PYTHONPATH=src python3 -m job_hunter_agent serve-ui --host "$HOST" --port "$PORT" >/tmp/job-search-agent-ui.log 2>&1 &
    echo $! >"$PID_FILE"
  )

  sleep 1
  pid="$(find_pid)"
  if [[ -n "$pid" ]]; then
    echo "Started UI on http://$HOST:$PORT (PID: $pid)"
    echo "Log: /tmp/job-search-agent-ui.log"
  else
    echo "UI did not start successfully. Check /tmp/job-search-agent-ui.log" >&2
    exit 1
  fi
}

stop() {
  local pid
  pid="$(find_pid)"
  if [[ -z "$pid" ]]; then
    echo "UI is not running on port $PORT"
    rm -f "$PID_FILE"
    return 0
  fi
  kill "$pid"
  rm -f "$PID_FILE"
  echo "Stopped UI on port $PORT (PID: $pid)"
}

restart() {
  stop || true
  start
}

case "${1:-}" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  restart)
    restart
    ;;
  status)
    status
    ;;
  *)
    echo "Usage: scripts/ui.sh {start|stop|restart|status}" >&2
    exit 1
    ;;
esac
