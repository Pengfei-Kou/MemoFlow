<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchNextCard, submitReview, submitBatchReview, type Block } from '../api'
import { useDeckStore } from '../stores/deck'
import { useStatsStore } from '../stores/stats'
import ReviewCard from '../components/ReviewCard.vue'

const deckStore = useDeckStore()
const statsStore = useStatsStore()

// ─── State ────────────────────────────────────────────────
const card        = ref<Block | null>(null)
const remaining   = ref(0)
const isNew       = ref(false)
const flipped     = ref(false)
const loading     = ref(false)
const submitting  = ref(false)
const error       = ref('')
const done        = ref(false)
const lastResult  = ref<string>('')
const sourceTitle = ref<string | null>(null)
const deckName    = ref<string | null>(null)

// Passage review state
const reviewMode     = ref<'card' | 'passage'>('card')
const batchCards     = ref<Block[]>([])
const batchIndex     = ref(0)
const batchQualities = ref<number[]>([])

// ─── Ratings constant ─────────────────────────────────────
const ratings = [
  { quality: 1, label: '忘了', shortcut: '1' },
  { quality: 3, label: '难', shortcut: '2' },
  { quality: 4, label: '良', shortcut: '3' },
  { quality: 5, label: '简单', shortcut: '4' },
] as const

// ─── Load next card ───────────────────────────────────────
async function loadNext() {
  loading.value = true
  error.value   = ''
  flipped.value = false
  lastResult.value = ''
  submitting.value = false
  try {
    const data = await fetchNextCard(deckStore.selectedDeckId)
    if (!data.block && (!data.batch || data.batch.length === 0)) {
      done.value = true
      card.value = null
      batchCards.value = []
    } else {
      remaining.value = data.remaining
      isNew.value   = data.is_new
      sourceTitle.value = data.source_title ?? null
      deckName.value    = data.deck_name ?? null
      done.value    = false
      
      if (data.review_mode === 'passage' && data.batch && data.batch.length > 0) {
        reviewMode.value = 'passage'
        batchCards.value = data.batch
        batchIndex.value = 0
        batchQualities.value = []
        card.value = batchCards.value[0]
      } else {
        reviewMode.value = 'card'
        batchCards.value = []
        card.value = data.block
      }
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '连接失败，请确认后端已启动'
  } finally {
    loading.value = false
  }
}

// ─── Rating ───────────────────────────────────────────────
function calculatePassageQuality(qualities: number[]): number {
  let score = 0
  for (const q of qualities) {
    if (q === 5) score += 100
    else if (q === 4) score += 80
    else if (q === 3) score += 0
    else if (q === 1) score -= 100
  }
  const avg = qualities.length > 0 ? score / qualities.length : 0
  if (avg >= 85) return 5
  if (avg >= 50) return 4
  if (avg >= 15) return 3
  return 1
}

async function rate(quality: number, label: string) {
  if (!card.value || submitting.value) return
  
  if (reviewMode.value === 'passage' && batchCards.value.length > 0) {
    batchQualities.value.push(quality)
    batchIndex.value++
    
    if (batchIndex.value < batchCards.value.length) {
      card.value = batchCards.value[batchIndex.value]
      flipped.value = false
    } else {
      submitting.value = true
      const overall = calculatePassageQuality(batchQualities.value)
      try {
        const blockIds = batchCards.value.map(b => b.id)
        const res = await submitBatchReview(blockIds, overall)
        lastResult.value = `✓ 整段 ${res.message}`
        statsStore.invalidate()
        setTimeout(() => loadNext(), 1200)
      } catch (e: unknown) {
        error.value = e instanceof Error ? e.message : '批量提交失败'
        submitting.value = false
      }
    }
  } else {
    submitting.value = true
    try {
      const res = await submitReview(card.value.id, quality)
      lastResult.value = `✓ ${label} — 下次复习：${new Date(res.next_review).toLocaleDateString('zh-CN')}`
      statsStore.invalidate()
      setTimeout(() => loadNext(), 900)
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '提交失败'
      submitting.value = false
    }
  }
}

function undo() {
  if (reviewMode.value !== 'passage' || batchIndex.value === 0 || submitting.value) return
  batchQualities.value.pop()
  batchIndex.value--
  card.value = batchCards.value[batchIndex.value]
  flipped.value = true
}

// ─── Keyboard shortcuts ───────────────────────────────────
function onKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
  if (e.key === 'Backspace') {
    e.preventDefault()
    undo()
    return
  }
  if (e.key === ' ' || e.key === 'Enter') {
    e.preventDefault()
    if (!flipped.value && card.value) {
      flipped.value = true
    } else if (flipped.value && card.value) {
      const r = ratings.find(r => r.shortcut === '3')
      if (r) rate(r.quality, r.label)
    }
    return
  }
  if (flipped.value && card.value) {
    const r = ratings.find(r => r.shortcut === e.key)
    if (r) rate(r.quality, r.label)
  }
}

// ─── Computed ─────────────────────────────────────────────
const progressLabel = computed(() => {
  if (!card.value) return ''
  let label = `${isNew.value ? '新内容' : '复习'} · 剩余 ${remaining.value} 组`
  if (reviewMode.value === 'passage' && batchCards.value.length > 0) {
    label += ` (${batchIndex.value + 1}/${batchCards.value.length})`
  }
  return label
})

const cardLabel = computed(() => {
  if (!card.value) return ''
  const parts: string[] = []
  if (deckName.value) parts.push(deckName.value)
  if (sourceTitle.value) parts.push(sourceTitle.value)
  const prefix = parts.length > 0 ? parts.join(' / ') + ' · ' : ''
  return `${prefix}#${card.value.id}`
})

const currentDeckLabel = computed(() => {
  const deck = deckStore.getDeckById(deckStore.selectedDeckId)
  return deck ? deck.path : '全部 Deck'
})

const lastRatingLabel = computed(() => {
  if (batchQualities.value.length === 0) return ''
  const lastQ = batchQualities.value[batchQualities.value.length - 1]
  return ratings.find(r => r.quality === lastQ)?.label || '未知'
})

onMounted(() => {
  loadNext()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="page-container review-page">

    <!-- Loading state -->
    <div v-if="loading" class="review-center">
      <div class="spinner"></div>
      <p class="text-mute mt-lg">加载中...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="review-center">
      <div class="review-error-card card">
        <p class="text-violet" style="font-size: var(--text-display-md); margin-bottom: var(--space-md)">⚠️</p>
        <p style="margin-bottom: var(--space-xl)">{{ error }}</p>
        <button class="btn btn-ghost" @click="loadNext">重试</button>
      </div>
    </div>

    <!-- All done state -->
    <div v-else-if="done" class="review-center">
      <div class="review-done-card card">
        <p style="font-size: 48px; margin-bottom: var(--space-md)">🎉</p>
        <h2 class="review-done-title">今天全部完成！</h2>
        <p class="text-mute" style="margin-top: var(--space-md)">
          明天继续，间隔重复的魔法正在发生。
        </p>
      </div>
    </div>

    <!-- Active card -->
    <div v-else-if="card" class="review-active">

      <!-- Top row: meta + progress -->
      <div class="review-meta flex items-center justify-between">
        <div class="flex items-center gap-md">
          <span class="badge">📖 {{ cardLabel }}</span>
          <span v-if="isNew" class="badge" style="color: var(--color-surface-violet); border-color: var(--color-surface-violet)">新卡片</span>
        </div>
        <div class="flex items-center gap-md">
          <span class="review-deck-scope text-xs">🗂️ {{ currentDeckLabel }}</span>
          <span class="text-faint text-xs">{{ progressLabel }}</span>
        </div>
      </div>

      <!-- Card component -->
      <ReviewCard
        class="mt-xl"
        :card="card"
        :flipped="flipped"
        :submitting="submitting"
        :last-result="lastResult"
        :show-undo="reviewMode === 'passage' && batchIndex > 0"
        :last-rating-label="lastRatingLabel"
        @flip="flipped = true"
        @rate="rate"
        @undo="undo"
      />

      <!-- Keyboard hint -->
      <p class="text-faint text-xs review-keyboard-hint" style="text-align: center; margin-top: var(--space-xl)">
        <kbd>Space</kbd> 翻牌 / 默认(良) · 或按 <kbd>1</kbd><kbd>2</kbd><kbd>3</kbd><kbd>4</kbd> 打分
      </p>
    </div>

  </div>
</template>

<style scoped>
.review-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding-top: var(--space-huge);
}

.review-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-lg);
  min-height: 60vh;
}

.review-error-card,
.review-done-card {
  text-align: center;
  max-width: 400px;
}

.review-done-title {
  font-size: var(--text-display-lg);
  font-weight: 540;
  letter-spacing: -0.63px;
}

.review-active {
  flex: 1;
  max-width: 680px;
  margin: 0 auto;
  width: 100%;
}

.review-meta {
  margin-bottom: var(--space-lg);
  opacity: 0.3;
  transition: opacity 0.3s ease;
}
.review-meta:hover {
  opacity: 1;
}

.review-keyboard-hint {
  opacity: 0.2;
  transition: opacity 0.3s ease;
}
.review-keyboard-hint:hover {
  opacity: 1;
}

.review-deck-scope {
  color: var(--color-surface-violet);
  opacity: 0.8;
}

kbd {
  display: inline-block;
  padding: 1px 6px;
  font-family: var(--font-sans);
  font-size: 11px;
  background: var(--color-primary-mid);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-xs);
  margin: 0 2px;
}
</style>
