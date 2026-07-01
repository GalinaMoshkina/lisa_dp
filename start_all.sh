#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$ROOT_DIR/runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PID_DIR="$RUNTIME_DIR/pids"
PYTHON_BIN="${PYTHON_BIN:-python3}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-8080}"

mkdir -p "$LOG_DIR" "$PID_DIR"

start_service() {
  local name="$1"
  local workdir="$2"
  shift 2
  local pid_file="$PID_DIR/$name.pid"
  local log_file="$LOG_DIR/$name.log"

  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file")"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
      echo "$name уже запущен: PID $old_pid"
      return
    fi
  fi

  echo "Запускаю $name..."
  (
    cd "$workdir"
    nohup "$@" >> "$log_file" 2>&1 &
    echo $! > "$pid_file"
  )

  sleep 0.4
  local new_pid
  new_pid="$(cat "$pid_file")"
  if kill -0 "$new_pid" 2>/dev/null; then
    echo "$name запущен: PID $new_pid, лог: $log_file"
  else
    echo "$name не запустился. Проверьте лог: $log_file"
  fi
}

start_service "hash_api" "$ROOT_DIR/.." "$PYTHON_BIN" "work/hash_service_api/app.py"
start_service "web_site" "$ROOT_DIR/web_w" "$PYTHON_BIN" "-m" "http.server" "$WEB_PORT" "--bind" "$WEB_HOST"
start_service "tgbot" "$ROOT_DIR/tgbot" "$PYTHON_BIN" "bot.py"
start_service "discussion_bot" "$ROOT_DIR/discussion_bot" "$PYTHON_BIN" "bot.py"

echo
echo "Готово."
echo "Сайт: http://$WEB_HOST:$WEB_PORT"
echo "Логи: $LOG_DIR"
echo "Остановить все: $ROOT_DIR/stop_all.sh"
