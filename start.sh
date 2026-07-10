#!/usr/bin/env bash
# ────────────────────────────────────────────
# MemoFlow V3 — 一键启动脚本
# 用法：./start.sh
# 按 Ctrl+C 同时停止前后端
# ────────────────────────────────────────────

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 MemoFlow V3 启动中..."
echo "   后端: http://localhost:8000  (API Docs: http://localhost:8000/docs)"
echo "   前端: http://localhost:5173"
echo "   按 Ctrl+C 停止"
echo ""

# trap: 收到 SIGINT/SIGTERM 时杀掉整个进程组
trap 'echo ""; echo "🛑 正在停止..."; kill 0; wait 2>/dev/null; echo "✅ 已停止"' EXIT

# 启动后端
(cd "$DIR/backend" && .venv/bin/python run.py) &

# 等后端启动一秒再启前端，避免日志交叉
sleep 1

# 启动前端
(cd "$DIR/frontend" && npm run dev) &

# 等待所有子进程
wait
