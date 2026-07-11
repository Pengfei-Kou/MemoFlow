# MemoFlow V3 核心技术与架构文档

本文档记录 MemoFlow V3 的底层技术实现细节与架构约定，作为后续开发的技术参考。

高层概览和 API 文档请参阅 [DEVELOPMENT.md](./DEVELOPMENT.md)。

---

## 一、数据流与架构设计

### 1. 三层后端架构

```
Router (HTTP 薄代理)  →  Service (业务编排)  →  CRUD (数据操作)
```

**关键约定：**
- **CRUD** 函数只做 `session.add() / flush()`，**不含 `commit()`**
- **Service** 层控制事务边界，负责业务逻辑编排和统一 `commit()`
- **Router** 只做参数校验、异常→HTTP 状态映射、response_model 约束

**异常映射规则：**
- `ValueError` → `404`（资源不存在）
- `RuntimeError` → `422`（业务逻辑错误，如 LLM 拆解失败）

### 2. 数据库模型要点

**`Block.notes` — JSON 嵌套子笔记：**
- 数据类型：`list[dict]`，Schema 为 `Array<{ zh: string, en: string }>`
- 由 `md_parser.py` 解析 `- 中文：英文` bullet 格式时生成
- 当前不参与独立 SM-2 调度（作为附属信息展示）

**`Deck.parser_config` — AI 拆解配置：**
- JSON 结构：`{ strategy, source_lang, target_lang, custom_prompt }`
- 影响 LLM prompt 生成（`parsers.py`）

**时区（2026-07-11 修订）：**
- 存储：所有 `datetime` 字段使用 `datetime.now(timezone.utc)` 存入（naive UTC 落库），杜绝 `date.today()` 混用
- 判定："今天"（到期/配额/热力图）= 本地逻辑日 —— `services/timeutils.py` 的 `local_day_bounds()/logical_date()`（America/Toronto + 凌晨 4 点滚动，config 可调），不再用 UTC 日界

**调度（2026-07-11 修订）：**
- 默认 FSRS-6（`services/fsrs_scheduler.py`，py-fsrs），`scheduler_algorithm=sm2` 回退
- `enable_fuzzing=False`：passage 模式依赖同篇卡片到期日聚拢，别打开
- 旧 SM-2 卡片首次复习时接种（stability≈interval，difficulty←ease_factor 线性映射）
- 每次评分追加一条 `ReviewLog`（含迁移回填的 quality=NULL 行）；热力图从日志聚合

### 3. Alembic 迁移

- `render_as_batch=True` — SQLite 不支持原生 ALTER TABLE，通过 batch mode 模拟
- `env.py` 从 `app.config.settings.database_url` 注入连接字符串
- `env.py` 导入 `app.models` 确保 `SQLModel.metadata` 包含所有表定义

---

## 二、Markdown 解析管线 (`md_parser.py`)

### 解析策略
基于**块的上下文关联解析**（非行级正则）：

1. **数据清洗** (`_clean_markdown_symbols`)：剥离 `**`、`$$` 等冗余符号
2. **节点归属算法**：
   - 中英文对 → 创建新 `Block` 实体
   - `- 中文：英文` bullet → 追加到最近一个 Block 的 `notes` 数组
   - `## Quiz` 下的内容 → 跳过
3. **语言检测**：通过 Unicode 范围判断中英文，过滤纯数字/符号行

### 重要约束
- 数据库 `original_text` 存的是拼接后的 `quiz / content` 字符串，**不是原始 Markdown**
- 批量重新导入**必须读取原始 `.md` 文件**，不能从 `original_text` 逆向解析

---

## 三、前端架构

### 1. 状态管理

| Store | 职责 | 消费者 |
|-------|------|--------|
| `useDeckStore` | Deck 列表 + 选中 ID | App.vue 侧边栏、所有页面 |
| `useStatsStore` | 全局统计数据 | App.vue 侧边栏、StatsView |

- `useStatsStore.invalidate()` — 由 ReviewView 每次提交评分后调用，触发侧边栏数据刷新
- `App.vue` 的 `watch(selectedDeckId)` 自动重新加载 stats

### 2. 组件设计

| 组件 | 职责 | 可复用性 |
|------|------|----------|
| `DeckSelector` | Deck 下拉选择 + 新建链接（v-model 双向绑定） | 全局 |
| `ImportResultCard` | 导入结果展示（问答卡片列表） | Text/URL Tab |
| `ReviewCard` | 复习卡片（问/答/笔记/评分按钮） | ReviewView |
| `TextImportTab` | 文本粘贴 + LLM 拆解 | ImportView |
| `UrlImportTab` | URL 抓取 + LLM 拆解 | ImportView |
| `MarkdownImportTab` | 拖放上传 + 规则解析 | ImportView |

### 3. 子卡片"胶囊遮罩"实现

```
<span class="note-zh">中文</span>
<span class="note-en-mask">English</span>
```

- 默认：英文文字透明 + 半透明背景 → 看起来像被遮住
- `:hover` / `:active`：背景透明 + 文字可见 → 刮开效果
- `margin-left: -4px` 抵消 `padding-left: 4px`，实现左边界对齐
- HTML 模板中 `<span>{{ note.en }}</span>` 必须写在同一行，避免 Vue 渲染空格

### 4. 设计 Token（`style.css`）

- Typography：`var(--text-display-md)` 为问答大字号上限
- 色彩层级：`--color-primary-deep`（底层）→ `--color-primary-mid`（卡片）→ `--color-surface-violet`（交互亮点）
- 极简原则：线框风格，通过 `hover` + `opacity` 提供反馈

---

## 四、测试基础设施

### 关键技术点

**SQLite 内存数据库测试：**
- 问题：SQLite `://` 每个连接创建独立数据库，lifespan 建表后 TestClient 看不到
- 方案：`StaticPool`（`sqlalchemy.pool`），强制所有连接共用同一个内存数据库
- 实现：在 `conftest.py` 中 patch `app.database.engine`，**必须在 `TestClient(app)` 初始化之前**

### 测试组织

```
tests/
├── conftest.py          # session / client / seed_data fixtures
├── test_scheduler.py    # SM-2 纯函数测试（13 个）
├── test_md_parser.py    # 解析器输入/输出对照（16 个）
└── test_api.py          # API 集成测试（16 个）
```

---

## 五、数据无损回填机制 (`fix_blocks.py`)

适用场景：Markdown 解析器升级导致卡片 ID 变化，需保留用户的 SM-2 进度。

**步骤：**
1. 以 `f"{quiz}|||{content}"` 为 Key，将旧 Block 的 SM-2 参数保存到内存 Map
2. 重新解析原始 Markdown 生成带 `notes` 的新 Block
3. 通过 Key 匹配，迁移 `reps / interval / ease_factor` 等进度字段

> 若将来再发生解析器变更导致 ID 错乱，均可采用此"特征签名匹配"模式抢救用户进度。
