<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { fetchBlocks, deleteBlock, updateBlock, fetchLeeches, type Block } from '../api'
import { useDeckStore } from '../stores/deck'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import DeckScopeSelect from '../components/DeckScopeSelect.vue'
import EditCardModal from '../components/EditCardModal.vue'
import HubTabs from '../components/HubTabs.vue'

const deckStore = useDeckStore()
const blocks  = ref<Block[]>([])
const loading = ref(false)
const error   = ref('')
const search  = ref('')
const deleting = ref<number | null>(null)
const pendingDelete = ref<number | null>(null)

type StatusFilter = 'all' | 'new' | 'learning' | 'mastered' | 'suspended'
const statusFilter = ref<StatusFilter>('all')

const statusChips: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'new', label: '新' },
  { value: 'learning', label: '学习中' },
  { value: 'mastered', label: '已掌握' },
  { value: 'suspended', label: '已暂停' },
]

function blockStatus(b: Block): StatusFilter {
  if (b.is_suspended) return 'suspended'
  if (b.next_review == null) return 'new'
  if (b.interval >= 21) return 'mastered'
  return 'learning'
}

const leeches = ref<Record<string, number>>({})

async function load() {
  loading.value = true
  error.value   = ''
  try {
    const [blockList, leechMap] = await Promise.all([
      fetchBlocks({ deck_id: deckStore.selectedDeckId, limit: 5000 }),
      fetchLeeches().catch(() => ({})),
    ])
    blocks.value = blockList
    leeches.value = leechMap
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

// Re-load when the selected Deck changes
watch(() => deckStore.selectedDeckId, load)

const filtered = computed(() => {
  let list = blocks.value
  if (statusFilter.value !== 'all') {
    list = list.filter(b => blockStatus(b) === statusFilter.value)
  }
  const q = search.value.toLowerCase()
  if (!q) return list
  return list.filter(b =>
    b.content.toLowerCase().includes(q) || b.quiz.toLowerCase().includes(q)
  )
})

const statusCount = computed(() => {
  const counts: Record<StatusFilter, number> = {
    all: blocks.value.length, new: 0, learning: 0, mastered: 0, suspended: 0,
  }
  for (const b of blocks.value) counts[blockStatus(b)]++
  return counts
})

async function confirmDelete() {
  const id = pendingDelete.value
  pendingDelete.value = null
  if (id == null) return
  deleting.value = id
  try {
    await deleteBlock(id)
    blocks.value = blocks.value.filter(b => b.id !== id)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '删除失败'
  } finally {
    deleting.value = null
  }
}

function intervalLabel(interval: number): string {
  if (interval === 0) return '新'
  if (interval >= 21) return `${interval}d ✓`
  return `${interval}d`
}

function intervalClass(interval: number): string {
  if (interval === 0)  return 'badge-new'
  if (interval >= 21) return 'badge-mastered'
  return 'badge-learning'
}

/** FSRS 难度（1~10）→ 难卡标签，只在偏难时显示避免噪音 */
function difficultyTag(b: Block): string | null {
  if (b.difficulty == null) return null
  if (b.difficulty >= 8) return '硬骨头'
  if (b.difficulty >= 6.5) return '偏难'
  return null
}

// 编辑
const editingBlock = ref<Block | null>(null)
function onCardSaved(updated: Block) {
  const idx = blocks.value.findIndex(b => b.id === updated.id)
  if (idx >= 0) blocks.value[idx] = updated
  editingBlock.value = null
}

// 暂停/恢复
const toggling = ref<number | null>(null)
async function toggleSuspend(b: Block) {
  if (toggling.value) return
  toggling.value = b.id
  try {
    const updated = await updateBlock(b.id, { is_suspended: !b.is_suspended })
    const idx = blocks.value.findIndex(x => x.id === b.id)
    if (idx >= 0) blocks.value[idx] = updated
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '操作失败'
  } finally {
    toggling.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="flex items-center justify-between hub-header">
      <HubTabs />
      <div class="flex items-center gap-md">
        <DeckScopeSelect />
        <span class="badge">{{ filtered.length }} 张</span>
      </div>
    </div>

    <!-- Search -->
    <div class="mt-xl">
      <input
        id="library-search"
        v-model="search"
        class="form-input"
        type="text"
        placeholder="搜索卡片内容…"
      />
    </div>

    <!-- Status filter chips -->
    <div class="library-chips mt-lg">
      <button
        v-for="chip in statusChips"
        :key="chip.value"
        class="library-chip"
        :class="{ active: statusFilter === chip.value }"
        @click="statusFilter = chip.value"
      >
        {{ chip.label }} <span class="library-chip-count">{{ statusCount[chip.value] }}</span>
      </button>
    </div>

    <!-- Error -->
    <p v-if="error" class="text-sm mt-lg" style="color:#e57373">⚠️ {{ error }}</p>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center gap-md mt-xl">
      <div class="spinner"></div>
      <span class="text-mute text-sm">加载中...</span>
    </div>

    <!-- Empty -->
    <div v-else-if="filtered.length === 0 && !loading" class="library-empty">
      <p style="font-size: 40px">📭</p>
      <p class="text-mute">{{ search || statusFilter !== 'all' ? '没有匹配的卡片' : '还没有卡片，去导入内容吧' }}</p>
    </div>

    <!-- List -->
    <div v-else class="library-list mt-xl">
      <div
        v-for="block in filtered"
        :key="block.id"
        class="library-item"
        :class="{ suspended: block.is_suspended }"
      >
        <div class="library-item-content">
          <p class="library-item-q">{{ block.quiz }}</p>
          <p class="library-item-a">{{ block.content }}</p>
        </div>
        <div class="library-item-meta">
          <span class="badge" :class="intervalClass(block.interval)">
            {{ block.is_suspended ? '⏸ 已暂停' : intervalLabel(block.interval) }}
          </span>
          <span v-if="difficultyTag(block)" class="badge badge-hard">
            🔥 {{ difficultyTag(block) }}
          </span>
          <span v-if="leeches[block.id]" class="badge badge-leech" title="反复忘记，建议编辑改写或暂停">
            🧟 忘 {{ leeches[block.id] }} 次
          </span>
          <div class="library-item-actions">
            <button class="btn btn-ghost btn-item-action" @click="editingBlock = block">编辑</button>
            <button
              class="btn btn-ghost btn-item-action"
              :disabled="toggling === block.id"
              @click="toggleSuspend(block)"
            >{{ block.is_suspended ? '恢复' : '暂停' }}</button>
            <button
              class="btn btn-danger btn-item-action"
              :disabled="deleting === block.id"
              @click="pendingDelete = block.id"
            >
              {{ deleting === block.id ? '…' : '删除' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :message="pendingDelete != null ? '确认删除这张卡片？\n复习进度将一并删除，此操作不可撤销。' : null"
      @confirm="confirmDelete"
      @cancel="pendingDelete = null"
    />

    <EditCardModal
      :block="editingBlock"
      @saved="onCardSaved"
      @cancel="editingBlock = null"
    />

  </div>
</template>

<style scoped>
.library-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-lg);
  padding: var(--space-huge) 0;
  text-align: center;
}

.library-chips {
  display: flex;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.library-chip {
  background: transparent;
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-full);
  color: var(--color-on-dark-mute);
  font-size: var(--text-caption);
  padding: 4px 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.library-chip:hover {
  border-color: var(--color-surface-violet);
}
.library-chip.active {
  color: var(--color-surface-violet);
  border-color: var(--color-surface-violet);
  background-color: rgba(201, 180, 250, 0.08);
}
.library-chip-count {
  opacity: 0.6;
  margin-left: 2px;
}

.library-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.library-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-xl);
  background-color: var(--color-primary-deep);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-md);
  padding: var(--space-lg);
  transition: border-color var(--transition);
}

.library-item:hover {
  border-color: var(--color-hairline-dark);
  background-color: var(--color-primary-mid);
}

.library-item-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.library-item-q {
  font-size: var(--text-body-md);
  font-weight: 540;
  color: var(--color-on-primary);
  line-height: 1.4;
}

.library-item-a {
  font-size: var(--text-caption);
  color: var(--color-on-dark-mute);
  line-height: 1.5;
}

.library-item-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--space-sm);
  flex-shrink: 0;
}

.library-item.suspended .library-item-content {
  opacity: 0.45;
}

.library-item-actions {
  display: flex;
  gap: var(--space-xs);
}

.btn-item-action {
  font-size: var(--text-micro);
  padding: 4px 8px;
}

/* Badge variants */
.badge-new      { color: var(--color-surface-violet); border-color: var(--color-surface-violet); }
.badge-mastered { color: #4db6b6; border-color: rgba(77,182,182,0.4); }
.badge-learning { color: var(--color-on-dark-mute); }
.badge-hard     { color: #e5a373; border-color: rgba(229,163,115,0.4); }
.badge-leech    { color: #e57373; border-color: rgba(229,115,115,0.4); }
</style>
