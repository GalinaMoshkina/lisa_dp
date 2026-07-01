#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$ROOT_DIR/runtime/pids"

stop_service() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"

  if [[ ! -f "$pid_file" ]]; then
    echo "$name не найден: PID-файла нет"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if [[ -z "$pid" ]]; then
    rm -f "$pid_file"
    echo "$name не найден: пустой PID-файл"
    return
  fi

  if kill -0 "$pid" 2>/dev/null; then
    echo "Останавливаю $name: PID $pid"
    kill "$pid"
  else
    echo "$name уже не запущен: PID $pid"
  fi

  rm -f "$pid_file"
}

stop_service "discussion_bot"
stop_service "tgbot"
stop_service "web_site"
stop_service "hash_api"

echo "Готово."
