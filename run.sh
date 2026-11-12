#!/usr/bin/env bash
# 一键启动:自动避开被占用端口,打印实际访问地址。
#   ./run.sh            # 从 8100 起找第一个空闲端口
#   ./run.sh 9000       # 指定起始端口
#   PORT=9000 ./run.sh  # 同上(环境变量)
#   ./run.sh --kill     # 若默认端口被占,杀掉占用进程后使用该端口
set -euo pipefail
cd "$(dirname "$0")"

KILL=0
START_PORT="${PORT:-8100}"
for arg in "$@"; do
  case "$arg" in
    --kill) KILL=1 ;;
    ''|*[!0-9]*) ;;         # 非数字参数忽略
    *) START_PORT="$arg" ;; # 数字参数作为起始端口
  esac
done

# 环境自检
if [ ! -x ".venv/bin/uvicorn" ]; then
  echo "✗ 未找到 .venv,请先安装依赖:"
  echo "    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
if [ ! -f ".env" ]; then
  echo "⚠ 未找到 .env(将只能用 Mock 模式)。真实调用请:cp .env.example .env 并填 key。"
fi

port_pid() { lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -1; }

PORT="$START_PORT"
PID="$(port_pid "$PORT" || true)"
if [ -n "$PID" ]; then
  if [ "$KILL" = "1" ]; then
    echo "端口 $PORT 被 PID $PID 占用,--kill 已生效,正在结束该进程…"
    kill "$PID" 2>/dev/null || true
    sleep 1
  else
    # 自动向后找第一个空闲端口
    while [ -n "$(port_pid "$PORT" || true)" ]; do
      echo "端口 $PORT 被占用(PID $(port_pid "$PORT")),尝试 $((PORT+1))…"
      PORT=$((PORT+1))
      if [ "$PORT" -gt "$((START_PORT+20))" ]; then
        echo "✗ $START_PORT~$PORT 均被占用,请手动指定:./run.sh <port>"; exit 1
      fi
    done
  fi
fi

echo "✓ 启动中 → http://127.0.0.1:$PORT"
exec .venv/bin/uvicorn main:app --reload --app-dir backend --port "$PORT"
