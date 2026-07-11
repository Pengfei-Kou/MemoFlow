# MemoFlow

基于 LLM 的智能间隔重复记忆系统 — 把长文本（口语课讲义、视频脚本、技术文档）自动拆解成"原子化"问答卡片，用 FSRS 算法科学调度每天该复习什么。主力用途：背英语口语句子。

**LLM-powered spaced repetition system**: paste any text, let an LLM split it into atomic flashcards (with hallucination guards), then review on an FSRS schedule. Vue 3 + FastAPI + SQLite, self-hosted, PWA-ready.

## 特性

- **智能拆解**：粘贴文本 / 抓取 URL / 上传 Markdown → LLM 拆成中文提示 + 英文原句卡片；代码级硬校验确保原句忠实于原文（防幻觉）
- **FSRS-6 调度**：Anki 同款新一代间隔重复算法（可回退 SM-2）；追加式复习日志（ReviewLog）为未来参数个性化留好数据
- **Deck 树形组织**：每个 Deck 可配置独立的拆解策略（句子/词汇/问答/填空/自定义 Prompt）与出卡顺序
- **Passage 模式**：整篇课文逐句过、整体评分，适合成段口语材料
- **移动端优先**：PWA 加主屏、底部 Tab 导航、拇指热区评分栏、TTS 朗读（支持翻面自动读）
- **本地时区逻辑日**：凌晨 4 点滚动（熬夜复习不算第二天），存储一律 UTC
- **单文件数据**：SQLite + Alembic 迁移，备份就是一个文件

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Pinia |
| 后端 | FastAPI + SQLModel + Uvicorn |
| 数据库 | SQLite（Alembic 迁移） |
| 调度 | py-fsrs（FSRS-6） |
| LLM | 任意 OpenAI 兼容接口（LiteLLM / OpenAI / Gemini） |

## 快速开始

```bash
# 后端
cd backend
cp .env.example .env        # 填入你的 LLM 端点与 Key
uv venv .venv && VIRTUAL_ENV=$PWD/.venv uv pip install -r requirements.txt
.venv/bin/python run.py     # http://localhost:8000（API 文档 /docs）

# 前端（另开终端）
cd frontend
npm install && npm run dev  # http://localhost:5173
```

### 生产部署（Docker）

```bash
docker build -t memoflow .
docker run -d -p 8000:8000 \
  -v ./data:/data \
  -e DATABASE_URL=sqlite:////data/memoflow.db \
  -e LLM_BASE_URL=... -e LLM_API_KEY=... -e MODEL_NAME=... \
  -e AUTH_USERNAME=... -e AUTH_PASSWORD=... \
  memoflow
```

多阶段构建自带前端产物（FastAPI 直接托管，SPA 路由回退），启动时自动执行 Alembic 迁移。公网部署务必设置 `AUTH_USERNAME/AUTH_PASSWORD`（登录页 + 90 天会话 cookie，Basic Auth 并行可用于脚本）。

## 文档

- [DEVELOPMENT.md](DEVELOPMENT.md) — 架构、数据模型、API 全览
- [MemoFlow_V3_Summary.md](MemoFlow_V3_Summary.md) — 底层实现与关键约定
- [implementation_plan.md](implementation_plan.md) — 设计决策记录

## 测试

```bash
cd backend && .venv/bin/python -m pytest tests/ -q   # 72 tests
cd frontend && npm run build                          # vue-tsc 类型检查
```
