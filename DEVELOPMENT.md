# MemoFlow V2 开发文档

## 1. 项目概述

MemoFlow V2 是基于 V1（Streamlit 原型）的架构升级版本，采用 **前后端分离** 架构：
- **后端**：FastAPI REST API
- **前端**：Vue3 SPA（后续开发）
- **数据库**：SQLite（开发）→ PostgreSQL（生产）

### V1 → V2 的核心变化

| 维度 | V1 | V2 |
|---|---|---|
| 架构 | Streamlit 单体 | FastAPI + Vue3 前后端分离 |
| 前端 | Streamlit (Python) | Vue3 + Vite (TypeScript) |
| API | 无 | RESTful API，支持多客户端 |
| 数据模型 | Source 未存原文 | Source 存储原文，Block 支持暂停 |
| 用户系统 | 无 | JWT 认证（Phase 2） |
| 部署 | 手动 | Docker Compose |

---

## 2. 技术栈

### 后端
- **Python** 3.11+
- **FastAPI** — Web 框架
- **SQLModel** — ORM（Pydantic + SQLAlchemy）
- **Uvicorn** — ASGI 服务器
- **Google GenAI SDK** — Gemini LLM 接口
- **Pydantic Settings** — 配置管理
- **python-dotenv** — 环境变量

### 前端（Phase 2）
- **Vue 3** + Composition API
- **Vite** — 构建工具
- **Pinia** — 状态管理
- **TailwindCSS** — 样式

---

## 3. 项目结构

```
MemoFlowV2/
├── DEVELOPMENT.md          # 本文档
├── backend/
│   ├── .env                # 环境变量（不提交到 Git）
│   ├── requirements.txt    # Python 依赖
│   ├── run.py              # 快速启动脚本
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py         # FastAPI 应用入口，注册路由/中间件
│   │   ├── config.py       # 配置管理（从 .env 读取）
│   │   ├── database.py     # 数据库引擎与会话管理
│   │   ├── models.py       # SQLModel 数据表定义
│   │   ├── schemas.py      # Pydantic 请求/响应模型
│   │   ├── crud.py         # 数据库 CRUD 操作
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── sources.py  # /api/sources — 来源管理
│   │   │   ├── blocks.py   # /api/blocks  — 卡片管理
│   │   │   ├── review.py   # /api/review  — 复习流程
│   │   │   └── stats.py    # /api/stats   — 数据统计
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── llm.py      # LLM ETL（Gemini 文本拆解）
│   │       └── scheduler.py # SM-2 间隔重复算法
├── frontend/               # Phase 2
└── docker-compose.yml      # Phase 3
```

---

## 4. API 接口文档

### 4.1 来源管理 `/api/sources`

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/sources/import` | 导入文本，触发 LLM 拆解，返回生成的卡片 |
| `GET` | `/api/sources` | 获取所有来源列表 |
| `GET` | `/api/sources/{id}` | 获取单个来源详情（含卡片列表） |
| `DELETE` | `/api/sources/{id}` | 删除来源及其所有卡片 |

### 4.2 卡片管理 `/api/blocks`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/blocks` | 获取卡片列表（支持分页、搜索、按来源筛选） |
| `GET` | `/api/blocks/{id}` | 获取单张卡片详情 |
| `PUT` | `/api/blocks/{id}` | 编辑卡片（修改 content/quiz/暂停状态） |
| `DELETE` | `/api/blocks/{id}` | 删除单张卡片 |

### 4.3 复习流程 `/api/review`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/review/next` | 获取下一张待复习的卡片（优先到期 > 新卡） |
| `POST` | `/api/review/{block_id}` | 提交复习打分（1=忘, 3=难, 4=良, 5=易） |

### 4.4 统计数据 `/api/stats`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/stats` | 获取全局统计（总数、已掌握、学习中、新卡、今日到期） |

---

## 5. 数据模型

### Source（来源表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int, PK | 主键 |
| title | str | 标题 |
| content_hash | str, Unique | 原文哈希（去重） |
| original_text | str | **[V2新增]** 保存原文，支持重新拆解和 RAG |
| source_type | str | 来源类型：text / url / file |
| url | str, nullable | 如果从 URL 导入，保存原始链接 |
| created_at | datetime | 创建时间 |

### Block（复习卡片表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int, PK | 主键 |
| source_id | int, FK | 关联 Source |
| sequence_number | int | 序列号（上下文排序） |
| content | str | 英文原文（Answer） |
| quiz | str | 中文提示（Question） |
| reps | int | 连续成功次数（SM-2） |
| interval | int | 当前间隔天数（SM-2） |
| ease_factor | float | 简易度系数（SM-2，默认 2.5） |
| last_review | datetime, nullable | 上次复习时间 |
| next_review | datetime, nullable | 下次复习时间（核心索引） |
| is_suspended | bool | **[V2新增]** 暂停复习（不删除） |
| embedding | JSON, nullable | RAG 预留向量字段 |

---

## 6. SM-2 调度算法

复刻 Anki 核心逻辑，评分标准：

| 评分 | 含义 | 行为 |
|------|------|------|
| 1 | 忘记 (Again) | interval=1, reps=0 |
| 3 | 困难 (Hard) | EF 下调，interval 按倍率增长 |
| 4 | 良好 (Good) | EF 保持，interval 按倍率增长 |
| 5 | 简单 (Easy) | EF 上调，interval 按倍率增长 |

**"已掌握"定义**：`interval >= 21`（间隔达到 3 周以上）

---

## 7. 开发路线图

### Phase 1：后端 API（当前阶段）✅
- [x] FastAPI 项目结构搭建
- [x] 数据模型定义（修复 V1 问题）
- [x] SM-2 算法移植
- [x] LLM ETL 服务移植
- [x] REST API 端点实现
- [x] CORS 配置（为前端准备）

### Phase 2：前端 SPA
- [ ] Vue3 + Vite 项目初始化
- [ ] 复习页面（翻牌动画、键盘快捷键）
- [ ] 导入页面（文本/URL）
- [ ] 卡片库管理页面
- [ ] Dashboard 统计面板

### Phase 3：部署与增强
- [ ] Docker Compose 打包
- [ ] 用户认证系统 (JWT)
- [ ] URL 内容抓取
- [ ] RAG 知识库问答

---

## 8. 快速启动

```bash
# 1. 进入后端目录
cd backend

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
# 编辑 .env 文件，填入你的 GEMINI_API_KEY

# 5. 启动开发服务器
python run.py

# API 文档自动生成于：
# http://localhost:8000/docs (Swagger UI)
# http://localhost:8000/redoc (ReDoc)
```

---

## 9. V1 遗留问题修复清单

| 问题 | 修复方式 |
|------|---------|
| Source 未保存原文 | models.py 新增 `original_text` 字段 |
| `datetime.utcnow()` 已弃用 | 改用 `datetime.now(timezone.utc)` |
| crud.py 重复 import | 清理导入 |
| mastered 阈值太低 (interval>1) | 改为 `interval >= 21` |
| 无法编辑/删除卡片 | 新增 PUT/DELETE 端点 |
| 数据库路径为相对路径 | 通过 config.py 统一管理 |
