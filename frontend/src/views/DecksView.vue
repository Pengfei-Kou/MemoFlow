<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchDecks, createDeck, updateDeck, deleteDeck, fetchSources, type Deck, type SourceListItem } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import HubTabs from '../components/HubTabs.vue'
import { useDeckStore } from '../stores/deck'

const router = useRouter()
const deckStore = useDeckStore()
const decks = ref<Deck[]>([])
const sources = ref<SourceListItem[]>([])
const loading = ref(false)
const error = ref('')

/** 该 Deck（含子树）的文章数与卡片数——牌组行的层级线索 */
function deckCounts(deck: Deck): { articles: number; cards: number } {
  const ids = new Set(
    decks.value
      .filter(d => d.path === deck.path || d.path.startsWith(deck.path + '/'))
      .map(d => d.id)
  )
  const list = sources.value.filter(s => s.deck_id != null && ids.has(s.deck_id))
  return { articles: list.length, cards: list.reduce((a, s) => a + s.block_count, 0) }
}

// ── 创建 Deck 表单 ────────────────────────────────────────
const showCreateForm = ref(false)
const createName = ref('')
const createParentPath = ref('')
const createStrategy = ref('sentence_en_zh')
const createSourceLang = ref('English')
const createTargetLang = ref('Chinese')
const createCustomPrompt = ref('')
const createCardOrder = ref('sequential_then_random')
const creating = ref(false)
const createError = ref('')

// ── 编辑 Deck ────────────────────────────────────────────
const editingDeck = ref<Deck | null>(null)
const editName = ref('')
const editStrategy = ref('sentence_en_zh')
const editSourceLang = ref('English')
const editTargetLang = ref('Chinese')
const editCustomPrompt = ref('')
const editCardOrder = ref('sequential_then_random')
const saving = ref(false)

const STRATEGIES = [
  { value: 'sentence_en_zh', label: '英文句 → 中文提示（默认）' },
  { value: 'vocabulary',     label: '词汇卡片（词性 + 例句）' },
  { value: 'qa_pairs',       label: '问答对提取' },
  { value: 'cloze',          label: '填空题' },
  { value: 'custom',         label: '自定义 Prompt' },
]

const CARD_ORDERS = [
  { value: 'sequential_then_random', label: '新卡顺序 + 复习按遗忘风险（默认）' },
  { value: 'always_sequential',      label: '全程按顺序（适合数学推导）' },
  { value: 'always_random',          label: '完全随机（适合词汇卡片）' },
]

// ── 树形渲染 ─────────────────────────────────────────────
interface TreeNode {
  deck: Deck
  children: TreeNode[]
  depth: number
}

const tree = computed<TreeNode[]>(() => {
  const roots: TreeNode[] = []
  const map = new Map<number, TreeNode>()

  for (const d of decks.value) {
    map.set(d.id, { deck: d, children: [], depth: 0 })
  }

  for (const node of map.values()) {
    if (node.deck.parent_id != null) {
      const parent = map.get(node.deck.parent_id)
      if (parent) {
        node.depth = parent.depth + 1
        parent.children.push(node)
      } else {
        roots.push(node)
      }
    } else {
      roots.push(node)
    }
  }

  return roots
})

function flattenTree(nodes: TreeNode[]): TreeNode[] {
  const result: TreeNode[] = []
  function walk(ns: TreeNode[]) {
    for (const n of ns) {
      result.push(n)
      walk(n.children)
    }
  }
  walk(nodes)
  return result
}

const flatTree = computed(() => flattenTree(tree.value))

// ── Load ──────────────────────────────────────────────────
async function load() {
  loading.value = true
  error.value = ''
  try {
    decks.value = await fetchDecks()
    await deckStore.loadDecks()
    sources.value = await fetchSources()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

// ── Create ────────────────────────────────────────────────
async function handleCreate() {
  if (!createName.value.trim()) { createError.value = '请输入名称'; return }
  creating.value = true
  createError.value = ''
  try {
    await createDeck({
      name: createName.value.trim(),
      parent_path: createParentPath.value.trim() || null,
      parser_config: {
        strategy: createStrategy.value,
        source_lang: createSourceLang.value,
        target_lang: createTargetLang.value,
        custom_prompt: createCustomPrompt.value.trim() || null,
      },
      card_order: createCardOrder.value,
    })
    showCreateForm.value = false
    createName.value = ''
    createParentPath.value = ''
    createCustomPrompt.value = ''
    await load()
  } catch (e: unknown) {
    createError.value = e instanceof Error ? e.message : '创建失败'
  } finally {
    creating.value = false
  }
}

// ── Edit ──────────────────────────────────────────────────
function startEdit(deck: Deck) {
  editingDeck.value = deck
  editName.value = deck.name
  editStrategy.value = deck.parser_config?.strategy ?? 'sentence_en_zh'
  editSourceLang.value = deck.parser_config?.source_lang ?? 'English'
  editTargetLang.value = deck.parser_config?.target_lang ?? 'Chinese'
  editCustomPrompt.value = deck.parser_config?.custom_prompt ?? ''
  editCardOrder.value = deck.card_order
}

async function handleSave() {
  if (!editingDeck.value) return
  saving.value = true
  try {
    await updateDeck(editingDeck.value.id, {
      name: editName.value.trim(),
      parser_config: {
        strategy: editStrategy.value,
        source_lang: editSourceLang.value,
        target_lang: editTargetLang.value,
        custom_prompt: editCustomPrompt.value.trim() || null,
      },
      card_order: editCardOrder.value,
    })
    editingDeck.value = null
    await load()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}

// ── Delete ────────────────────────────────────────────────
const pendingDelete = ref<Deck | null>(null)

async function confirmDelete() {
  const deck = pendingDelete.value
  pendingDelete.value = null
  if (!deck) return
  try {
    await deleteDeck(deck.id)
    await load()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '删除失败'
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="flex items-center justify-between hub-header">
      <HubTabs />
      <button class="btn btn-primary" @click="showCreateForm = !showCreateForm">
        {{ showCreateForm ? '收起' : '+ 新建' }}
      </button>
    </div>

    <p v-if="error" class="text-sm mt-lg" style="color:#e57373">⚠️ {{ error }}</p>

    <!-- 创建表单 -->
    <div v-if="showCreateForm" class="card deck-form mt-xl">
      <h2 class="deck-form-title">新建 Deck</h2>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label">名称 *</label>
          <input id="create-deck-name" v-model="createName" class="form-input" placeholder="如：Grammar" />
        </div>
        <div class="form-group">
          <label class="form-label">父路径（可选）</label>
          <input id="create-deck-parent" v-model="createParentPath" class="form-input" placeholder="如：English" />
        </div>
      </div>

      <div class="form-row mt-lg">
        <div class="form-group">
          <label class="form-label">拆解策略</label>
          <select id="create-deck-strategy" v-model="createStrategy" class="form-input">
            <option v-for="s in STRATEGIES" :key="s.value" :value="s.value">{{ s.label }}</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">卡片顺序</label>
          <select id="create-deck-order" v-model="createCardOrder" class="form-input">
            <option v-for="o in CARD_ORDERS" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
        </div>
      </div>

      <div v-if="createStrategy !== 'custom'" class="form-row mt-lg">
        <div class="form-group">
          <label class="form-label">源语言</label>
          <input v-model="createSourceLang" class="form-input" placeholder="English" />
        </div>
        <div class="form-group">
          <label class="form-label">目标语言</label>
          <input v-model="createTargetLang" class="form-input" placeholder="Chinese" />
        </div>
      </div>

      <div v-if="createStrategy === 'custom'" class="form-group mt-lg">
        <label class="form-label">自定义 Prompt（用 {text} 占位原文）</label>
        <textarea v-model="createCustomPrompt" class="form-textarea" rows="4" placeholder="请将以下文本拆解为学习卡片：{text}" />
      </div>

      <p v-if="createError" class="text-sm mt-md" style="color:#e57373">⚠️ {{ createError }}</p>

      <div class="flex gap-md mt-xl justify-end">
        <button class="btn btn-ghost" @click="showCreateForm = false">取消</button>
        <button id="create-deck-submit" class="btn btn-primary" :disabled="creating" @click="handleCreate">
          <span v-if="creating" class="spinner" style="width:14px;height:14px;" />
          <span v-else>创建</span>
        </button>
      </div>
    </div>

    <!-- Deck 树形列表 -->
    <div v-if="loading" class="flex items-center gap-md mt-xl">
      <div class="spinner" />
      <span class="text-mute text-sm">加载中...</span>
    </div>

    <div v-else-if="flatTree.length === 0" class="mt-xl">
      <p class="text-mute text-sm">还没有 Deck — 点击右上角「新建 Deck」开始吧</p>
    </div>

    <div v-else class="deck-tree mt-xl">
      <div
        v-for="node in flatTree"
        :key="node.deck.id"
        class="deck-node"
        :style="{ paddingLeft: `calc(var(--space-xl) + ${node.depth * 28}px)` }"
      >
        <div class="deck-node-content deck-node-clickable" @click="router.push(`/articles?deck_id=${node.deck.id}`)">
          <div class="deck-node-info">
            <span class="deck-node-connector" v-if="node.depth > 0">└─</span>
            <span class="deck-node-icon">{{ node.depth === 0 ? '📚' : '📖' }}</span>
            <div>
              <p class="deck-node-name">{{ node.deck.name }}</p>
              <p class="deck-node-path text-faint text-xs">
                {{ node.deck.path }} · {{ deckCounts(node.deck).articles }} 篇 {{ deckCounts(node.deck).cards }} 张
              </p>
            </div>
          </div>

          <div class="deck-node-meta">
            <span class="badge deck-strategy-badge">{{ node.deck.parser_config?.strategy ?? '—' }}</span>
            <div class="flex gap-sm">
              <button class="btn btn-ghost btn-sm" @click.stop="startEdit(node.deck)">编辑</button>
              <button class="btn btn-ghost btn-sm deck-delete-btn" @click.stop="pendingDelete = node.deck">删除</button>
            </div>
            <span class="text-faint deck-node-chevron">›</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 编辑 Modal -->
    <div v-if="editingDeck" class="modal-overlay" @click.self="editingDeck = null">
      <div class="modal-box card">
        <h2 class="deck-form-title">编辑 Deck：{{ editingDeck.path }}</h2>

        <div class="form-group mt-lg">
          <label class="form-label">名称</label>
          <input id="edit-deck-name" v-model="editName" class="form-input" />
        </div>

        <div class="form-row mt-lg">
          <div class="form-group">
            <label class="form-label">拆解策略</label>
            <select id="edit-deck-strategy" v-model="editStrategy" class="form-input">
              <option v-for="s in STRATEGIES" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">卡片顺序</label>
            <select id="edit-deck-order" v-model="editCardOrder" class="form-input">
              <option v-for="o in CARD_ORDERS" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </div>
        </div>

        <div v-if="editStrategy !== 'custom'" class="form-row mt-lg">
          <div class="form-group">
            <label class="form-label">源语言</label>
            <input v-model="editSourceLang" class="form-input" />
          </div>
          <div class="form-group">
            <label class="form-label">目标语言</label>
            <input v-model="editTargetLang" class="form-input" />
          </div>
        </div>

        <div v-if="editStrategy === 'custom'" class="form-group mt-lg">
          <label class="form-label">自定义 Prompt</label>
          <textarea v-model="editCustomPrompt" class="form-textarea" rows="4" />
        </div>

        <div class="flex gap-md mt-xl justify-end">
          <button class="btn btn-ghost" @click="editingDeck = null">取消</button>
          <button id="edit-deck-save" class="btn btn-primary" :disabled="saving" @click="handleSave">
            <span v-if="saving" class="spinner" style="width:14px;height:14px;" />
            <span v-else>保存</span>
          </button>
        </div>
      </div>
    </div>
    <ConfirmDialog
      :message="pendingDelete ? `确认删除 Deck「${pendingDelete.path}」及其所有 Sources 和 Blocks？\n此操作不可撤销。` : null"
      @confirm="confirmDelete"
      @cancel="pendingDelete = null"
    />
  </div>
</template>

<style scoped>
.deck-form {
  background-color: var(--color-primary-mid);
}

.deck-form-title {
  font-size: var(--text-heading-lg);
  font-weight: 540;
  letter-spacing: -0.4px;
  margin-bottom: var(--space-lg);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-lg);
}

.deck-tree {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.deck-node {
  background-color: var(--color-primary-mid);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-md);
  transition: background-color var(--transition), border-color var(--transition);
}

.deck-node:hover {
  background-color: var(--color-primary-deep);
  border-color: var(--color-surface-violet);
}

.deck-node-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-xl);
  padding: var(--space-lg) var(--space-xl) var(--space-lg) 0;
}

.deck-node-info {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  min-width: 0;
}

.deck-node-connector {
  color: var(--color-on-dark-mute);
  font-family: monospace;
  font-size: 14px;
  flex-shrink: 0;
}

.deck-node-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.deck-node-info > div {
  min-width: 0;
}

.deck-node-clickable {
  cursor: pointer;
}
.deck-node-clickable:hover .deck-node-name {
  color: var(--color-surface-violet);
}

.deck-node-chevron {
  font-size: var(--text-body-lg);
}

.deck-node-name {
  font-size: var(--text-body-md);
  font-weight: 540;
  color: var(--color-on-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.deck-node-path {
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.deck-node-meta {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  flex-shrink: 0;
}

/* 窄屏：徽章+按钮放不下时换到第二行，绝不撑宽页面
   （曾把文档撑到 417px 导致手机整页被缩放） */
@media (max-width: 768px) {
  .deck-node-content {
    flex-wrap: wrap;
    gap: var(--space-sm) var(--space-md);
  }
  .deck-node-meta {
    margin-left: auto;
  }
}

.deck-strategy-badge {
  font-size: 11px;
  padding: 2px 8px;
}

.btn-sm {
  padding: var(--space-xs) var(--space-md);
  font-size: var(--text-caption);
}

.deck-delete-btn:hover {
  color: #e57373;
  border-color: #e57373;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal-box {
  width: min(600px, 92vw);
  background-color: var(--color-primary-mid);
  padding: var(--space-xxl);
  max-height: 90vh;
  overflow-y: auto;
}
</style>
