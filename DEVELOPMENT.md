# MemoFlow V3 开发文档

## 1. 项目概述

MemoFlow V3 是一个**间隔重复记忆系统**，基于 SM-2 算法帮助用户高效记忆外语句子。支持三种导入方式（文本粘贴 / URL 抓取 / Markdown 上传），通过 LLM 智能拆解文本，并以 Deck 树形结构组织学习内容。

### 架构

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Pinia |
| 后端 | FastAPI + SQLModel + Uvicorn |
| 数据库 | SQLite（通过 Alembic 管理迁移） |
| AI | OpenAI 兼容接口（LiteLLM / Gemini） |

---

## 2. 项目结构

```
MemoFlowV3/
├── start.sh                    # 一键启动脚本
├── Makefile                    # make dev / make test / make stop
│
├── backend/
│   ├── .env                    # 环境变量（LLM Key、数据库路径）
│   ├── requirements.txt
│   ├── run.py                  # Uvicorn 启动入口
│   ├── alembic.ini             # Alembic 迁移配置
│   ├── alembic/
│   │   ├── env.py              # 迁移环境（SQLModel metadata + batch mode）
│   │   └── versions/           # 迁移脚本
│   ├── app/
│   │   ├── main.py             # FastAPI 入口，注册路由/中间件/生命周期
│   │   ├── config.py           # pydantic-settings 配置管理
│   │   ├── database.py         # 引擎与会话管理
│   │   ├── models.py           # SQLModel 表定义（Deck / Source / Block）
│   │   ├── schemas.py          # Pydantic 请求/响应模型
│   │   ├── crud.py             # 数据库 CRUD（不含 commit，由调用方控制）
│   │   ├── routers/
│   │   │   ├── sources.py      # /api/sources — 导入管理（薄代理）
│   │   │   ├── blocks.py       # /api/blocks  — 卡片 CRUD
│   │   │   ├── review.py       # /api/review  — 复习流程（薄代理）
│   │   │   ├── stats.py        # /api/stats   — 统计数据
│   │   │   └── decks.py        # /api/decks   — Deck 管理
│   │   └── services/
│   │       ├── review_service.py  # 复习业务逻辑（配额/分流/评分）
│   │       ├── import_service.py  # 导入业务逻辑（LLM拆解/MD解析）
│   │       ├── llm.py             # LLM 调用（tenacity 3次重试）
│   │       ├── md_parser.py       # 郝炟口语 Markdown 规则解析
│   │       ├── scheduler.py       # SM-2 间隔重复算法
│   │       ├── url_fetcher.py     # URL 正文抓取（含 SSRF 防护）
│   │       └── parsers.py         # Parser 配置与 prompt 生成
│   └── tests/
│       ├── conftest.py         # pytest fixtures（内存 SQLite + StaticPool）
│       ├── test_scheduler.py   # SM-2 算法单元测试（13 个）
│       ├── test_md_parser.py   # Markdown 解析器测试（16 个）
│       └── test_api.py         # API 集成测试（16 个）
│
└── frontend/
    └── src/
        ├── main.ts             # Vue 应用入口
        ├── App.vue             # 根组件（侧边栏 + 路由视图）
        ├── api/index.ts        # API 客户端（统一 fetch 封装）
        ├── router/index.ts     # Vue Router 路由配置
        ├── stores/
        │   ├── deck.ts         # Pinia — Deck 列表与选中状态
        │   └── stats.ts        # Pinia — 全局统计数据（跨页共享）
        ├── components/
        │   ├── DeckSelector.vue      # Deck 下拉选择器（v-model）
        │   ├── ImportResultCard.vue   # 导入结果展示（问答列表）
        │   ├── TextImportTab.vue      # 文本粘贴导入 Tab
        │   ├── UrlImportTab.vue       # URL 抓取导入 Tab
        │   ├── MarkdownImportTab.vue  # Markdown 上传导入 Tab
        │   └── ReviewCard.vue         # 复习卡片（问/答/笔记/评分）
        └── views/
            ├── ReviewView.vue    # 复习页面（键盘快捷键 + passage 模式）
            ├── ImportView.vue    # 导入页面（Tab 容器）
            ├── StatsView.vue     # 统计页面（热力图 + 进度条）
            ├── LibraryView.vue   # 卡片库管理
            └── DecksView.vue     # Deck 管理
```

---

## 3. 数据模型

### Deck（学习集）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int, PK | 主键 |
| name | str | 显示名（如 "Grammar"） |
| path | str, Unique | 完整路径（如 "English/Grammar"） |
| parent_id | int, FK, nullable | 父节点 ID（树形结构） |
| parser_config | JSON | AI 拆解配置（strategy / source_lang / target_lang） |
| card_order | str | 卡片顺序策略 |
| created_at | datetime | 创建时间 |

### Source（来源）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int, PK | 主键 |
| title | str | 标题 |
| content_hash | str, Unique | SHA-256 去重哈希 |
| original_text | str | 原文 |
| source_type | str | 类型：text / url / file |
| url | str, nullable | 原始 URL |
| deck_id | int, FK, nullable | 所属 Deck |
| created_at | datetime | 创建时间 |

### Block（复习卡片）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int, PK | 主键 |
| source_id | int, FK | 关联 Source |
| sequence_number | int | 序列号 |
| content | str | 英文原文（Answer） |
| quiz | str | 中文提示（Question） |
| notes | JSON, nullable | 附属知识点 `[{zh, en}]` |
| reps | int | 连续成功次数 |
| interval | int | 当前间隔天数 |
| ease_factor | float | SM-2 简易度系数（默认 2.5） |
| last_review | datetime, nullable | 上次复习时间（UTC） |
| next_review | datetime, nullable | 下次复习时间（UTC） |
| first_reviewed_at | datetime, nullable | 首次学习时间 |
| is_suspended | bool | 是否暂停复习 |

---

## 4. API 接口

### 来源管理 `/api/sources`
| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/sources/import` | 导入文本 → LLM 拆解 → 存库 |
| `POST` | `/api/sources/import-markdown` | 上传 MD 文件 → 规则解析 → 批量存库 |
| `POST` | `/api/sources/fetch-url` | 抓取 URL 正文（预览，不存库） |
| `GET` | `/api/sources` | 获取来源列表 |
| `GET` | `/api/sources/{id}` | 获取来源详情（含卡片） |
| `DELETE` | `/api/sources/{id}` | 删除来源及其卡片 |

### 复习流程 `/api/review`
| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/review/next?deck_id=N` | 获取下一张待复习卡片（card / passage 模式） |
| `POST` | `/api/review/{block_id}` | 提交单卡评分（`Literal[1,3,4,5]`） |
| `POST` | `/api/review/batch` | 提交 passage 级批量评分 |

### 卡片管理 `/api/blocks`
| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/blocks` | 获取卡片列表 |
| `PUT` | `/api/blocks/{id}` | 编辑卡片 |
| `DELETE` | `/api/blocks/{id}` | 删除卡片 |

### Deck 管理 `/api/decks`
| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/decks` | 获取所有 Deck |
| `POST` | `/api/decks` | 创建 Deck（含 parent_path 校验） |
| `PUT` | `/api/decks/{id}` | 修改 Deck |
| `DELETE` | `/api/decks/{id}` | 删除 Deck（级联） |

### 统计 `/api/stats`
| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/stats?deck_id=N` | 全局/按 Deck 统计 |
| `GET` | `/api/stats/history?days=90` | 复习热力图数据 |

---

## 5. 架构设计原则

### 后端分层

```
Router (薄代理)  →  Service (业务逻辑)  →  CRUD (数据操作)
   ↓                    ↓                     ↓
 参数校验            配额/分流/编排         session.add / flush
 HTTP 状态映射       LLM 调用              不含 commit
 response_model      事务 commit
```

- **Router** 只做参数校验 + 调用 Service + 返回 HTTP 响应
- **Service** 封装业务逻辑，控制事务边界（commit）
- **CRUD** 只做 `session.add() / flush()`，不含 `commit()`

### 前端分层

```
View (页面容器)  →  Component (可复用组件)  →  Store (全局状态)
     ↓                    ↓                       ↓
   路由匹配            DeckSelector             useDeckStore
   Tab 切换            ReviewCard               useStatsStore
   页面布局            ImportResultCard          跨页面共享
```

### 测试策略
- SM-2 算法：纯函数单元测试
- MD 解析器：输入/输出对照测试
- API 集成：TestClient + 内存 SQLite（StaticPool）

---

## 6. 快速启动

```bash
# 一键启动（推荐）
./start.sh
# 或
make dev

# 分别启动
make backend    # 后端 http://localhost:8000
make frontend   # 前端 http://localhost:5173

# 运行测试
make test

# 停止残留进程
make stop

# 安装依赖
make install
```

### 数据库迁移

```bash
cd backend

# 修改 models.py 后，自动生成迁移
.venv/bin/alembic revision --autogenerate -m "描述"

# 应用迁移
.venv/bin/alembic upgrade head

# 回滚
.venv/bin/alembic downgrade -1
```

---

## 7. 已完成的重构工作

### Bug 修复（P0）
- ✅ 统一时区：所有日期计算使用 `datetime.now(timezone.utc)`
- ✅ 修复 datetime vs date 字符串比较（`count_today_reviewed`）
- ✅ 批量 commit 优化（700 次 → 1 次 fsync）
- ✅ `timedelta` import 统一到文件顶部
- ✅ 删除空类 `MarkdownImportResponse`，加 response_model
- ✅ `fetch_url_preview` body:dict → Pydantic Model
- ✅ 版本注释 V2 → V3

### 架构改进
- ✅ Service 层：`review_service.py` + `import_service.py`
- ✅ CRUD 解耦 commit（移到 Service/Router 层）
- ✅ LLM 重试（tenacity 3 次指数退避）
- ✅ 评分维度对齐：`Literal[1,3,4,5]`（前端/后端/算法三方统一）
- ✅ content_hash MD5 → SHA-256
- ✅ `create_deck` parent_path 存在性校验
- ✅ 移除 `Block.embedding` YAGNI 字段

### 基础设施
- ✅ Alembic 数据库迁移集成（render_as_batch for SQLite）
- ✅ 45 个测试（SM-2: 13 + MD 解析: 16 + API 集成: 16）
- ✅ SSRF 防护（url_fetcher 内网地址拦截）
- ✅ 一键启动（start.sh + Makefile）

### 前端组件化
- ✅ ImportView 724 → 88 行（拆为 5 个子组件）
- ✅ ReviewView 574 → 274 行（拆出 ReviewCard）
- ✅ `useStatsStore` 统一 stats 数据（侧边栏实时更新）
- ✅ `request()` Content-Type 自动检测 FormData

---

## 8. 未来方向

### 🔧 近期可做（产品增强）

| 方向 | 说明 | 复杂度 |
|------|------|--------|
| **认证系统** | 当前 API 完全公开，`HOST=0.0.0.0` 监听所有网卡。本地使用无碍，若部署到公网需加 JWT 或 Basic Auth | 中 |
| **SM-2 → FSRS** | FSRS（Free Spaced Repetition Scheduler）在记忆效率上显著优于 SM-2，Anki 已默认使用 FSRS-5 | 中 |
| **子笔记独立复习** | 当前 `notes` 是 JSON blob，无法参与 SM-2 调度。如需独立复习需拆为 `Note` 表 + 独立 SM-2 字段 | 高 |
| **移动端适配** | 打分按钮、键盘快捷键未针对触屏优化；侧边栏在窄屏下已可收起 | 中 |

### 🎯 长期演进

| 方向 | 说明 |
|------|------|
| **多设备同步** | SQLite → PostgreSQL + 用户系统 |
| **离线 PWA** | Service Worker 缓存，地铁/无网络环境下复习 |
| **Docker 部署** | docker-compose 一键部署前后端 + 数据库 |
| **富文本支持** | 引入 AST 解析器（如 remark），支持高亮、加粗等格式 |

---

## 9. 开发约定

### 后端
- 所有时间使用 UTC：`datetime.now(timezone.utc)`
- CRUD 函数不含 `commit()`，由 Service/Router 控制事务
- Schema 变更必须通过 Alembic 迁移
- 新增 API 路由需在 `test_api.py` 中添加对应测试

### 前端
- 遵循 `src/style.css` 设计 Token（颜色/间距/字号）
- 可复用组件放 `components/`，页面级放 `views/`
- 跨页面状态放 Pinia Store，页面内状态用 `ref()`
- API 调用统一通过 `api/index.ts` 的 `request()` 函数
