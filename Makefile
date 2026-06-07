########################################
# MemoFlow 开发环境快捷命令
# 用法：make dev
########################################

.PHONY: dev backend frontend install help

## 同时启动前后端开发服务器（需要两个终端，或使用 make dev）
dev:
	@echo "🚀 启动 MemoFlow 开发环境..."
	@echo "   后端: http://localhost:8000  (API Docs: http://localhost:8000/docs)"
	@echo "   前端: http://localhost:5173"
	@(cd backend && uv run python run.py &) && cd frontend && npm run dev

## 仅启动后端
backend:
	@echo "🔧 启动后端..."
	cd backend && uv run python run.py

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

## 显示帮助
help:
	@echo "可用命令："
	@echo "  make dev       - 同时启动前后端"
	@echo "  make backend   - 仅启动后端"
	@echo "  make frontend  - 仅启动前端"
	@echo "  make install   - 安装所有依赖"
