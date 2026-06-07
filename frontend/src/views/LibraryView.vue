<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { fetchBlocks, deleteBlock, type Block } from '../api'

import { useDeckStore } from '../stores/deck'

const deckStore = useDeckStore()
const blocks  = ref<Block[]>([])
const loading = ref(false)
const error   = ref('')
const search  = ref('')
const deleting = ref<number | null>(null)

async function load() {
  loading.value = true
  error.value   = ''
  try {
    blocks.value = await fetchBlocks({ deck_id: deckStore.selectedDeckId, limit: 5000 })
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

// Re-load when the selected Deck changes
import { watch } from 'vue'
watch(() => deckStore.selectedDeckId, load)

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  if (!q) return blocks.value
  return blocks.value.filter(b =>
    b.content.toLowerCase().includes(q) || b.quiz.toLowerCase().includes(q)
  )
})

async function handleDelete(id: number) {
  if (!confirm('确认删除这张卡片？')) return
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

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="flex items-center justify-between">
      <h1 class="page-title" style="margin-bottom: 0">卡片库</h1>
      <span class="badge">{{ filtered.length }} 张</span>
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
      <p class="text-mute">{{ search ? '没有匹配的卡片' : '还没有卡片，去导入内容吧' }}</p>
    </div>

    <!-- List -->
    <div v-else class="library-list mt-xl">
      <div
        v-for="block in filtered"
        :key="block.id"
        class="library-item"
      >
        <div class="library-item-content">
          <p class="library-item-q">{{ block.quiz }}</p>
          <p class="library-item-a">{{ block.content }}</p>
        </div>
        <div class="library-item-meta">
          <span class="badge" :class="intervalClass(block.interval)">
            {{ intervalLabel(block.interval) }}
          </span>
          <button
            class="btn btn-danger"
            :disabled="deleting === block.id"
            @click="handleDelete(block.id)"
          >
            {{ deleting === block.id ? '…' : '删除' }}
          </button>
        </div>
      </div>
    </div>

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

/* Badge variants */
.badge-new      { color: var(--color-surface-violet); border-color: var(--color-surface-violet); }
.badge-mastered { color: #4db6b6; border-color: rgba(77,182,182,0.4); }
.badge-learning { color: var(--color-on-dark-mute); }
</style>
