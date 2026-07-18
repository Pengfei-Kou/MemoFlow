<script setup lang="ts">
/**
 * 文章详情页：按原文顺序浏览一篇文章的全部卡片、掌握度概览、整篇重学。
 * 三层结构（仓库-文章-句子）中间层的 UI 落点。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { fetchSourceDetail, relearnSource, type Block, type SourceDetail } from '../api'
import { useDeckStore } from '../stores/deck'
import { useStatsStore } from '../stores/stats'
import EditCardModal from '../components/EditCardModal.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import AppIcon from '../components/AppIcon.vue'

const route = useRoute()
const router = useRouter()
const deckStore = useDeckStore()
const statsStore = useStatsStore()

const source = ref<SourceDetail | null>(null)
const loading = ref(true)
const error = ref('')
const editingBlock = ref<Block | null>(null)
const confirmMsg = ref<string | null>(null)
const relearning = ref(false)
const toast = ref('')

const blocks = computed(() =>
  [...(source.value?.blocks ?? [])].sort((a, b) => a.sequence_number - b.sequence_number)
)

const learned = computed(() => blocks.value.filter(b => b.next_review !== null).length)
const mastered = computed(() => blocks.value.filter(b => b.interval >= 21).length)

const deckPath = computed(() => {
  const id = source.value?.deck_id
  return id ? deckStore.getDeckById(id)?.path ?? null : null
})

function statusLabel(b: Block): { text: string; cls: string } {
  if (b.is_suspended) return { text: '已暂停', cls: 'st-suspended' }
  if (b.next_review === null) return { text: '新卡', cls: 'st-new' }
  const days = Math.ceil((new Date(b.next_review).getTime() - Date.now()) / 86400000)
  if (days <= 0) return { text: '待复习', cls: 'st-due' }
  if (b.interval >= 21) return { text: `已掌握 · ${days}天后`, cls: 'st-mastered' }
  return { text: `${days}天后`, cls: 'st-learning' }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    source.value = await fetchSourceDetail(Number(route.params.id))
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function onCardSaved(updated: Block) {
  if (!source.value) return
  const idx = source.value.blocks.findIndex(b => b.id === updated.id)
  if (idx >= 0) source.value.blocks[idx] = updated
  editingBlock.value = null
}

async function doRelearn() {
  confirmMsg.value = null
  relearning.value = true
  try {
    const res = await relearnSource(Number(route.params.id))
    toast.value = `✓ ${res.message}`
    statsStore.invalidate()
    await load()
    setTimeout(() => { toast.value = '' }, 3000)
  } catch (e: unknown) {
    toast.value = e instanceof Error ? `⚠️ ${e.message}` : '⚠️ 操作失败'
  } finally {
    relearning.value = false
  }
}

onMounted(() => {
  if (deckStore.decks.length === 0) deckStore.loadDecks()
  load()
})
</script>

<template>
  <div class="page-container">
    <button class="btn btn-ghost source-back" @click="router.back()">← 返回</button>

    <div v-if="loading" class="flex items-center gap-md mt-xl">
      <div class="spinner"></div><span class="text-mute">加载中...</span>
    </div>
    <p v-else-if="error" class="text-sm mt-xl" style="color:#e57373">⚠️ {{ error }}</p>

    <template v-else-if="source">
      <h1 class="source-title-lg">{{ source.title }}</h1>
      <p class="text-faint text-sm mt-sm">
        <template v-if="deckPath && source.deck_id">
          <RouterLink :to="`/articles?deck_id=${source.deck_id}`" class="crumb-link"><AppIcon name="folder" :size="12" /> {{ deckPath }}</RouterLink>
          <span> › 本文 · </span>
        </template>{{ new Date(source.created_at).toLocaleDateString('zh-CN') }}
      </p>

      <!-- 掌握度概览 -->
      <div class="source-stats mt-lg">
        <span class="badge">{{ blocks.length }} 句</span>
        <span class="badge">已学 {{ learned }}</span>
        <span class="badge">已掌握 {{ mastered }}</span>
        <span class="source-progress-track">
          <span class="source-progress-fill" :style="{ width: blocks.length ? (learned / blocks.length * 100) + '%' : '0%' }"></span>
        </span>
      </div>

      <div class="mt-lg flex items-center gap-md">
        <button
          class="btn btn-ghost text-sm"
          :disabled="relearning || learned === 0"
          @click="confirmMsg = `确定整篇重学《${source.title}》？将清空 ${blocks.length} 张卡的复习进度（历史记录保留）`"
        ><AppIcon name="refresh" :size="12" /> 重学这篇</button>
        <span v-if="toast" class="text-xs" style="color: var(--color-surface-violet)">{{ toast }}</span>
      </div>

      <!-- 按原文顺序的卡片列表 -->
      <div class="source-blocks mt-xl">
        <div v-for="b in blocks" :key="b.id" class="source-block-item">
          <span class="source-block-seq text-xs text-faint">#{{ b.sequence_number }}</span>
          <div class="source-block-body">
            <p class="source-block-zh text-sm">{{ b.quiz }}</p>
            <p class="source-block-en">{{ b.content }}</p>
          </div>
          <div class="source-block-side">
            <span class="source-block-status text-xs" :class="statusLabel(b).cls">{{ statusLabel(b).text }}</span>
            <button class="btn-speak" title="编辑" @click="editingBlock = b"><AppIcon name="pencil" :size="13" /></button>
          </div>
        </div>
      </div>
    </template>

    <EditCardModal :block="editingBlock" @saved="onCardSaved" @cancel="editingBlock = null" />
    <ConfirmDialog :message="confirmMsg" confirm-label="重学" @confirm="doRelearn" @cancel="confirmMsg = null" />
  </div>
</template>

<style scoped>
.source-back {
  padding-left: 0;
}

.crumb-link {
  color: inherit;
  text-decoration: none;
}
.crumb-link:hover {
  color: var(--color-surface-violet);
}

.source-title-lg {
  font-size: var(--text-display-md);
  font-weight: 560;
  margin-top: var(--space-md);
}

.source-stats {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.source-progress-track {
  flex: 1;
  min-width: 80px;
  height: 4px;
  border-radius: var(--radius-full);
  background-color: var(--color-primary-mid);
  overflow: hidden;
}

.source-progress-fill {
  display: block;
  height: 100%;
  border-radius: var(--radius-full);
  background-color: var(--color-surface-violet);
  transition: width 0.3s ease;
}

.source-blocks {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.source-block-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
  padding: var(--space-md) var(--space-lg);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-md);
  background-color: var(--color-primary-mid);
}

.source-block-seq {
  flex-shrink: 0;
  margin-top: 2px;
  min-width: 28px;
}

.source-block-body {
  flex: 1;
  min-width: 0;
}

.source-block-zh {
  color: var(--color-on-dark-mute);
}

.source-block-en {
  margin-top: var(--space-xs);
}

.source-block-side {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--space-xs);
}

.source-block-status {
  white-space: nowrap;
}
.st-new { color: var(--color-surface-violet); }
.st-due { color: #e5a973; }
.st-learning { color: var(--color-on-dark-mute); }
.st-mastered { color: #7dd4a0; }
.st-suspended { color: var(--color-on-dark-faint); text-decoration: line-through; }
</style>
