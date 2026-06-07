# MemoFlow V3 核心技术与架构文档

本文档总结了 MemoFlow V3 版本迭代中的底层架构演进与关键技术实现，旨在为后续版本的开发和维护提供技术参考与标准约定。

---

## 一、 数据流与架构设计

### 1. 数据库模型演进 (Schema Upgrades)
为了支持“主卡片-子笔记”的嵌套数据结构，V3 摒弃了早期将所有内容打平为独立卡片的做法，在 `Block` 模型中引入了 JSON 结构：
- **`notes` 字段**：在 `app/models.py` 的 `Block` 表中新增了 `notes: Optional[str]`（底层使用 JSON 序列化存储）。
- **数据结构约定**：`notes` 在业务层对应的数据类型为 `list[dict]`，标准的 Schema 定义为 `Array<{ zh: string, en: string }>`。
- **持久化约束**：为了保证向前兼容，如果 `notes` 为空，在数据库中可存为 `null` 或 `'[]'`。

### 2. Markdown 解析管线 (`md_parser.py`)
解析器从基于行的无状态正则匹配，升级为了**基于块的上下文关联解析**。
- **数据清洗 (`_clean_markdown_symbols`)**：在解析入口处统一剥离了 `**` 和 `$$` 等容易干扰前端渲染的冗余符号。
- **节点归属算法**：
  - 检测到常规中英文对时，创建一个新的 `Block` 实体（主卡片）。
  - 检测到 `- 中文：英文` 这种 bullet 格式时，**不再**直接 yield 为新卡片。
  - 解析器会向上追溯，通过栈尾指针 `cards[-1]` 找到当前上下文的最后一个主卡片，并将该句结构化后直接 `append` 到其 `notes` 数组中。
- **注意缺陷**：V3 初期的数据库中 `original_text` 字段记录的是被拼接过的 `quiz / content` 字符串，**破坏了原始的 Markdown 换行符与 `- ` 标识**。在后续开发中，若涉及批量重新导入，**必须读取原始 `.md` 文件**（如 `郝炟英语口语.md`），切勿使用数据库内的 `original_text` 逆向解析。

### 3. 数据无损回填机制 (`fix_blocks.py`)
在执行从平铺卡片到层叠卡片的数据重构时，我们建立了一套**通过特征签名匹配状态**的机制：
- 将旧的 `Block` 以 `f"{quiz}|||{content}"` 作为哈希 Key 保存在内存 Map 中。
- 重新解析原始 Markdown 生成新的带有 `notes` 嵌套层级的新 `Block`。
- 通过 Key 匹配，将旧表中的 `reps`、`interval`、`ease_factor` 等 SM-2 算法关键参数逐一赋值给新表。
- **后续复用**：若将来再发生 Markdown 结构变更导致 ID 错乱，均可采用此“特征签名匹配”模式来抢救用户的 SM-2 进度状态。

---

## 二、 前端架构与交互逻辑

### 1. Vue 组件状态管理 (`ReviewView.vue`)
复习视图在 V3 彻底转变为流式结构：
- **状态流转**：通过 `flipped` (boolean) 控制翻牌状态。通过 `history` 数组记录用户在本次 Session 中已经刷过的历史卡片。
- **UI 退场机制**：已刷过的历史卡片会被渲染在主卡片上方，并附加 `.dim` CSS 类以弱化视觉焦点。
- **响应式撤销 (Undo)**：
  - 核心逻辑：拦截最近一次 SM-2 API 请求的返回值。
  - 当触发 `undoReview` 时，调用撤销 API，若成功，则将状态机中的 `history.pop()`，重置 `flipped = false`，将焦点拉回上一张卡片。

### 2. 子卡片“胶囊遮罩”实现原理
为实现不打断心流的“悬浮刮刮乐”体验，利用 CSS 高阶定位和边距魔法：
- 结构：`<span class="note-zh">` + `<span class="note-en-mask">`。
- **去前导空格 (Leading Space Elimination)**：严格要求 HTML 模板中 `<span>{{ note.en }}</span>` 必须写在一行，避免 Vue 编译器将 DOM 换行符渲染为空格。
- **负边距像素对齐**：
  - 遮罩层拥有 `padding: 2px 8px 2px 4px` 的内部留白。
  - 为防止这 `4px` 导致文字不齐，使用了 `margin-left: -4px`。
  - 通过盒模型抵消，最终实现遮罩背景的左边界对齐上一行文字，同时内部文字又恰好完美垂直对齐。

### 3. Design System 与视觉规范
后续组件开发需严格遵循 `src/style.css` 现有的设计 Token：
- **Typography**：使用 `var(--text-display-md)` 作为重点问答的大字号规范。不要超过此级别，避免排版在流式结构中显得头重脚轻。
- **色彩与层级 (Colors)**：
  - `var(--color-primary-deep)`：最底层的背景。
  - `var(--color-primary-mid)`：卡片的容器色。
  - `var(--color-surface-violet)`：所有的主次交互亮点（遮罩、焦点按钮）统一使用此紫色。
- **极简原则**：V3 去除了多余的 Emoji 与复杂的色块提示。后续新增交互按钮时，务必沿用线框风格，借助 `hover` 与 `opacity` 变化提供反馈。

---

## 三、 下一步研发建议 (Next Steps)

1. **富文本支持**：目前 Markdown 解析严格依赖固定字符，后续可考虑引入标准 AST 树解析器（如 `remark`），使 `notes` 可以安全地承载高亮、加粗等 HTML 标签。
2. **SM-2 算法优化**：目前子笔记（notes）不参与独立计分。如果业务需求改变，未来可在 `notes` 中增加独属于每个子句的 `ease_factor` 等评分字段，并在前端做深度嵌套。
3. **撤销栈深度**：当前的撤销仅支持 1 步回退。未来可通过引入完整的 Vuex/Pinia 队列，配合后端维护一个 Review History Table，实现无限深度的撤销栈。
