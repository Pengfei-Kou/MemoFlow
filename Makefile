########################################
# MemoFlow 开发环境快捷命令
# 用法：make dev
########################################

.PHONY: dev backend frontend install test help stop

## 同时启动前后端开发服务器（Ctrl+C 同时停止两者）
dev:
	@echo "🚀 启动 MemoFlow 开发环境..."
	@echo "   后端: http://localhost:8000  (API Docs: http://localhost:8000/docs)"
	@echo "   前端: http://localhost:5173"
	@trap 'kill 0' EXIT; \
		(cd backend && .venv/bin/python run.py) & \
		(cd frontend && npm run dev) & \
		wait

## 仅启动后端
backend:
	@echo "🔧 启动后端..."
	cd backend && .venv/bin/python run.py

## 仅启动前端
frontend:
	@echo "🎨 启动前端..."
	cd frontend && npm run dev

## 安装依赖
install:
	@echo "📦 安装后端依赖..."
	cd backend && uv sync
	@echo "📦 安装前端依赖..."
	cd frontend && npm install

## 运行测试
test:
	@echo "🧪 运行后端测试..."
	cd backend && .venv/bin/python -m pytest tests/ -v

## 停止残留进程
stop:
	@echo "🛑 停止 MemoFlow 进程..."
	-@pkill -f "run.py" 2>/dev/null || true
	-@pkill -f "vite" 2>/dev/null || true
	@echo "✅ 已清理"

## 显示帮助
help:
	@echo "可用命令："
	@echo "  make dev       - 一键启动前后端（Ctrl+C 同时停止）"
	@echo "  make backend   - 仅启动后端"
	@echo "  make frontend  - 仅启动前端"
	@echo "  make install   - 安装所有依赖"
	@echo "  make test      - 运行后端测试"
	@echo "  make stop      - 停止所有残留进程"
