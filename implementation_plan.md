# MemoFlow V3 设计方案及核心逻辑修复

> **状态**: 设计已确认，核心逻辑修复待执行
> **前置条件**: 已从 V2 复制代码至 V3，准备在 V3 目录下实施修复及升级

---

## 零、核心逻辑问题修复（优先执行）

在进行 V3 的 Deck 结构改造前，必须先修复 V2 遗留的严重影响 SM-2 算法调度和用户体验的核心 Bug。

### 1. 修复：日期比较导致的“漏掉今日复习”Bug
- **问题**：`crud.py` 中的 `Block.next_review <= str(today)` 比较由于 SQLite 字符串字典序规则，会漏掉当天 `00:00:00` 的卡片。
- **修复方案**：
  - 将对比条件改为比较 `next_review < str(tomorrow)`。
  - 涉及函数：`get_due_blocks`, `count_due_blocks`, `get_stats`。

### 2. 修复：每日学习/复习上限被架空
- **问题**：后端未统计今日已学/已复习数量，导致 `/api/review/next` 会无视 `config.new_cards_per_session` 和 `config.review_cards_per_session`，无限出卡。
- **修复方案**：
  - 在 `get_due_blocks` 和 `get_new_blocks` 被调用时，计算当天已经复习和学习的数量。
  - 新卡片逻辑：查询当天 `last_review` 是今天且第一次学习的卡片数量，判断是否超过 `new_cards_per_session`。若超过，不再出新卡。
  - 复习逻辑：查询当天复习且非第一次学习的卡片数量，判断是否超过 `review_cards_per_session`。若超过，不再出复习卡。

### 3. 修复：前端“查看答案”后一直转圈的 Bug
- **问题**：用户在 `/` (ReviewView) 页面对卡片进行打分后，`rate()` 函数设置了 `submitting.value = true`，但在 `loadNext()` 完成后，没有将其重置为 `false`。导致下一张卡片翻开时，直接显示了“提交中...”的转圈动画，卡死了复习流程。
- **修复方案**：在 `frontend/src/views/ReviewView.vue` 的 `loadNext` 函数中增加 `submitting.value = false`，确保每次进入新卡片时，提交状态都被正确重置。

---

## 一、核心目标

在现有两层结构（Source → Block）之上，增加 **Deck（学科仓库）** 层，
形成任意深度的三层以上树形结构，并为每个 Deck 配置独立的 AI 拆解规则和卡片顺序策略。

```
Deck: "English"
  └── Deck: "English/Grammar"
        └── Source: "Chapter 1 - Tenses"
              └── Block: "I gotta hold myself accountable." / "如何表达..."
Deck: "French"
  └── Source: "Leçon 1"
        └── Block: ...
```

---

## 二、数据库 Schema（新增 / 修改）

### 新增表：`Deck`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int, PK | 主键 |
| `name` | str | 当前节点显示名（如 `"Grammar"`）|
| `path` | str, Unique Index | 完整路径（如 `"English/Grammar"`）|
| `parent_id` | int, FK → Deck.id, nullable | 父节点（用于 UI 树形展示）|
| `parser_config` | JSON | AI 拆解规则（见下方结构）|
| `card_order` | str | 卡片顺序策略（见下方枚举）|
| `created_at` | datetime | 创建时间 |

**`parser_config` JSON 结构：**
```json
{
  "strategy": "sentence_en_zh",
  "source_lang": "English",
  "target_lang": "Chinese",
  "custom_prompt": null
}
```

**`strategy` 枚举值：**

| 值 | 说明 |
|----|------|
| `sentence_en_zh` | 提取英文原句 + 生成中文提示（当前默认行为）|
| `vocabulary` | 提取单词 + 词性 + 例句 |
| `qa_pairs` | 从文档提取问答对 |
| `cloze` | 生成填空题 |
| `custom` | 完全使用 `custom_prompt` 字段（模板中用 `{text}` 占位）|

**`card_order` 枚举值：**

| 值 | 说明 |
|----|------|
| `sequential_then_random` | **默认**：新卡按 Source 创建顺序，复习卡随机打乱 |
| `always_sequential` | 所有阶段按 sequence_number 顺序（适合数学推导等强依赖场景）|
| `always_random` | 完全随机（适合词汇卡片等无顺序依赖场景）|

---

### 修改表：`Source`

新增字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `deck_id` | int, FK → Deck.id, **NOT NULL** | 所属 Deck |

**迁移策略**：V2 现有数据直接清空（用户确认），V3 起导入时强制指定 Deck，未指定则自动放入系统默认 Deck `"Default"`。

---

### `Block` 表：不变

`sequence_number` 字段已存在，直接用于顺序控制。

---

## 三、API 设计（新增 / 修改）

### 新增：Deck 管理 `/api/decks`

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/decks` | 获取所有 Deck（树形结构）|
| `POST` | `/api/decks` | 创建 Deck |
| `GET` | `/api/decks/{id}` | 获取单个 Deck 详情（含子 Deck 列表）|
| `PUT` | `/api/decks/{id}` | 修改 Deck（名称、parser_config、card_order）|
| `DELETE` | `/api/decks/{id}` | 删除 Deck（级联删除 Sources 和 Blocks）|

**`POST /api/decks` 请求体：**
```json
{
  "name": "Grammar",
  "parent_path": "English",
  "parser_config": { "strategy": "sentence_en_zh", "source_lang": "English", "target_lang": "Chinese" },
  "card_order": "sequential_then_random"
}
```

后端根据 `parent_path + name` 自动计算 `path = "English/Grammar"`。

---

### 修改：`/api/sources/import`

请求体新增：
```json
{
  "deck_id": 3,       // 必填；如未传，后端分配到 Default Deck 并返回警告
  "text": "...",
  "title": "..."
}
```

---

### 修改：`/api/review/next`

新增 query 参数：
```
GET /api/review/next?deck_id=3&include_children=true
```

- `deck_id`：限定复习范围；不传则复习全部（兼容旧行为）
- `include_children`：是否包含子 Deck（默认 `true`）

后端根据 Deck 的 `card_order` 配置决定排序方式：
- `sequential_then_random`：新卡 `ORDER BY source_id, sequence_number`；复习卡 `ORDER BY RANDOM()`
- `always_sequential`：全部 `ORDER BY source_id, sequence_number`
- `always_random`：全部 `ORDER BY RANDOM()`

---

### 修改：`/api/stats`

新增 query 参数：
```
GET /api/stats?deck_id=3&include_children=true
```

返回该 Deck 范围内的统计数据。

---

## 四、Parser 插件系统

**不使用动态代码执行**，采用"预设 Strategy + 自定义 Prompt 模板"的两层设计：

```python
# backend/app/services/parsers.py

STRATEGIES = {
    "sentence_en_zh": {
        "prompt_template": """
你是一个严格的数据提取助手。请阅读以下{source_lang}文本，将其拆解为学习卡片。
规则：
1. 识别文本中的{source_lang}原句作为 "content"，必须严谨摘录原文，禁止修改。
2. 为每句原文生成{target_lang}提示问题作为 "quiz"。
3. 输出格式必须是 JSON 数组：[{{"content": "...", "quiz": "..."}}]
4. 忽略无意义的闲聊。只输出 JSON。

待处理文本：
{text}
        """
    },
    "vocabulary": { "prompt_template": "..." },
    "qa_pairs":   { "prompt_template": "..." },
    "cloze":      { "prompt_template": "..." },
    "custom":     { "prompt_template": "{custom_prompt}\n\n待处理文本：\n{text}" },
}

def build_prompt(parser_config: dict, raw_text: str) -> str:
    strategy = parser_config.get("strategy", "sentence_en_zh")
    template = STRATEGIES[strategy]["prompt_template"]
    return template.format(
        text=raw_text,
        source_lang=parser_config.get("source_lang", "English"),
        target_lang=parser_config.get("target_lang", "Chinese"),
        custom_prompt=parser_config.get("custom_prompt", ""),
    )
```

`llm.py` 里调用 `build_prompt(deck.parser_config, raw_text)` 替换当前硬编码的 prompt。

---

## 五、前端改动

### 新增页面：Deck 管理页 `/decks`

- 树形展示所有 Deck
- 创建 / 编辑 / 删除 Deck
- 编辑 `parser_config`（Strategy 下拉 + 自定义 Prompt 编辑框）
- 编辑 `card_order`（单选）

### 修改：侧边栏

在侧边栏顶部加入"当前复习 Deck"选择器（下拉或树形选择）。选中后，复习页和统计页都以该 Deck 为范围。

### 修改：导入页 `/import`

- 文本框上方加入"选择 Deck"必填下拉（含"新建 Deck"快捷入口）
- 如果已在某 Deck 下进入导入页，自动预填

### 修改：复习页 `/`

- 顶部显示当前复习的 Deck 名称
- 卡片来源标签从 `卡片 #ID` 改为 `Deck名 / Source标题 · #ID`

### 修改：统计页 `/stats`

- 数据指标按选中 Deck 范围过滤
- 来源列表改为"Deck 树 + Source 列表"双层展示

---

## 六、实现顺序（下次开始时按此执行）

```
1. 后端数据库：新增 Deck 模型，修改 Source 加 deck_id
   → 验证：uv run python run.py 无报错，数据库生成 deck 表

2. 后端 CRUD：为 Deck 编写 create/read/update/delete 函数
   → 验证：pytest 或手动调用函数

3. 后端 Parser 系统：parsers.py，重构 llm.py 调用 build_prompt()
   → 验证：sentence_en_zh strategy 与当前行为一致

4. 后端 API：
   a. /api/decks 路由（CRUD）
   b. 修改 /api/sources/import（加 deck_id）
   c. 修改 /api/review/next（加 deck_id + card_order 逻辑）
   d. 修改 /api/stats（加 deck_id 过滤）
   → 验证：Swagger UI (/docs) 手动测试所有端点

5. 前端：Deck 管理页 + 侧边栏 Deck 选择器
   → 验证：能创建 Deck，选中后复习页和统计页数据正确过滤

6. 前端：修改导入页（加 Deck 选择）
   → 验证：导入后卡片归入正确 Deck

7. 前端：修改复习页 + 统计页（显示 Deck 信息）
   → 验证：卡片标签显示正确，统计数据按 Deck 正确过滤
```

---

## 七、已确认的设计决策（勿改动）

- **路径命名**：`path` 存完整路径（`"English/Grammar"`），`name` 只存当前节点名（`"Grammar"`）
- **复习顺序**：Deck 级别配置，默认 `sequential_then_random`（新卡顺序 + 复习随机）
- **已有数据**：实现前清空，V3 起导入强制指定 Deck
- **自定义 Prompt**：使用模板变量 `{text}`、`{source_lang}`、`{target_lang}`，不执行动态代码
- **子 Deck 复习**：`include_children=true` 时递归查询所有子 Deck 的卡片（用 `path LIKE 'parent/%'`）
