<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import {
  fetchNextCard, submitReview, submitBatchReview, fetchTodaySummary, undoReview,
  type Block, type TodaySummary,
} from '../api'
import { useDeckStore } from '../stores/deck'
import { useStatsStore } from '../stores/stats'
import ReviewCard from '../components/ReviewCard.vue'
import DeckScopeSelect from '../components/DeckScopeSelect.vue'
import EditCardModal from '../components/EditCardModal.vue'

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
const sourceTitle = ref<string | null>(null)
const deckName    = ref<string | null>(null)
const today       = ref<TodaySummary | null>(null)

// Passage review state
const reviewMode     = ref<'card' | 'passage'>('card')
const batchCards     = ref<Block[]>([])
const batchIndex     = ref(0)
const batchQualities = ref<number[]>([])

// 翻面自动朗读（记 localStorage）
const autoSpeak = ref(localStorage.getItem('memoflow-autospeak') === '1')
function toggleAutoSpeak() {
  autoSpeak.value = !autoSpeak.value
  localStorage.setItem('memoflow-autospeak', autoSpeak.value ? '1' : '0')
}

// 轻量 toast：不阻塞切卡的评分反馈；单卡评分后附带"撤销"按钮
const toast = ref('')
const undoableBlockId = ref<number | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null
function showToast(msg: string, undoBlockId: number | null = null) {
  toast.value = msg
  undoableBlockId.value = undoBlockId
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value = ''
    undoableBlockId.value = null
  }, undoBlockId ? 5000 : 2200)
}

async function handleUndo() {
  const id = undoableBlockId.value
  if (!id) return
  undoableBlockId.value = null
  toast.value = ''
  try {
    await undoReview(id)
    statsStore.invalidate()
    showToast('↩︎ 已撤销，重新作答')
    loadNext()
  } catch (e: unknown) {
    showToast(e instanceof Error ? e.message : '撤销失败')
  }
}

// 卡片快速编辑（复习页翻面后 ✏️）
const editingBlock = ref<Block | null>(null)
function onCardSaved(updated: Block) {
  if (card.value && card.value.id === updated.id) {
    card.value = { ...card.value, quiz: updated.quiz, content: updated.content }
  }
  const idx = batchCards.value.findIndex(b => b.id === updated.id)
  if (idx >= 0) batchCards.value[idx] = { ...batchCards.value[idx], quiz: updated.quiz, content: updated.content }
  editingBlock.value = null
}

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
  submitting.value = false
  try {
    const [data, summary] = await Promise.all([
      fetchNextCard(deckStore.selectedDeckId),
      fetchTodaySummary(deckStore.selectedDeckId).catch(() => null),
    ])
    today.value = summary
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

// 切换复习范围时重载队列
watch(() => deckStore.selectedDeckId, () => loadNext())

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
        statsStore.invalidate()
        showToast(`✓ 整段 ${res.message}`)
        loadNext()
      } catch (e: unknown) {
        error.value = e instanceof Error ? e.message : '批量提交失败'
        submitting.value = false
      }
    }
  } else {
    submitting.value = true
    const ratedId = card.value.id
    try {
      const res = await submitReview(ratedId, quality)
      statsStore.invalidate()
      showToast(`✓ ${label} — ${res.message.split('→ ')[1] ?? res.message}`, ratedId)
      loadNext()
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
  if (editingBlock.value) return // 编辑弹窗打开时不响应复习快捷键
  if (e.key === 'Backspace') {
    e.preventDefault()
    if (reviewMode.value === 'passage') undo()
    else handleUndo() // 单卡模式：撤销刚提交的评分（toast 存续期内）
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

// 今日进度：已复习 / (已复习 + 队列剩余 + 当前这张)
const progressRatio = computed(() => {
  if (!today.value) return null
  const doneCount = today.value.reviewed
  const total = doneCount + remaining.value + (card.value ? 1 : 0)
  if (total === 0) return null
  return Math.min(1, doneCount / total)
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

const retentionLabel = computed(() => {
  if (!today.value || today.value.retention == null) return null
  return Math.round(today.value.retention * 100)
})

onMounted(() => {
  loadNext()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<template>
  <div class="page-container review-page">

    <!-- 今日进度条 -->
    <div v-if="progressRatio !== null && !done" class="review-progress-track">
      <div class="review-progress-fill" :style="{ width: `${progressRatio * 100}%` }"></div>
    </div>

    <!-- 评分反馈 toast（单卡评分附撤销） -->
    <Transition name="toast">
      <div v-if="toast" class="review-toast" :class="{ actionable: undoableBlockId }">
        <span>{{ toast }}</span>
        <button v-if="undoableBlockId" class="toast-undo-btn" @click="handleUndo">撤销</button>
      </div>
    </Transition>

    <!-- 窄屏：复习范围选择（桌面端由侧边栏承担） -->
    <div class="review-scope-row mobile-only">
      <DeckScopeSelect />
    </div>

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
        <p v-if="today && today.reviewed > 0" class="review-done-summary">
          今日复习 <strong>{{ today.reviewed }}</strong> 次<template v-if="retentionLabel !== null">
            · 记住率 <strong>{{ retentionLabel }}%</strong></template>
        </p>
        <p v-if="today && today.streak > 1" class="review-done-summary">
          🔥 连续学习 <strong>{{ today.streak }}</strong> 天
        </p>
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
          <button
            class="review-autospeak-btn"
            :class="{ on: autoSpeak }"
            @click="toggleAutoSpeak"
            :title="autoSpeak ? '翻面自动朗读：开' : '翻面自动朗读：关'"
          >🔊 {{ autoSpeak ? '自动' : '手动' }}</button>
          <span class="review-deck-scope text-xs desktop-only">🗂️ {{ currentDeckLabel }}</span>
          <span class="text-faint text-xs">{{ progressLabel }}</span>
        </div>
      </div>

      <!-- Card component -->
      <ReviewCard
        class="mt-xl"
        :card="card"
        :flipped="flipped"
        :submitting="submitting"
        :show-undo="reviewMode === 'passage' && batchIndex > 0"
        :last-rating-label="lastRatingLabel"
        :auto-speak="autoSpeak"
        @flip="flipped = true"
        @rate="rate"
        @undo="undo"
        @edit="editingBlock = card"
      />

      <!-- Keyboard hint -->
      <p class="text-faint text-xs review-keyboard-hint" style="text-align: center; margin-top: var(--space-xl)">
        <kbd>Space</kbd> 翻牌 / 默认(良) · <kbd>1</kbd><kbd>2</kbd><kbd>3</kbd><kbd>4</kbd> 打分 · <kbd>⌫</kbd> 撤销
      </p>
    </div>

    <EditCardModal
      :block="editingBlock"
      @saved="onCardSaved"
      @cancel="editingBlock = null"
    />

  </div>
</template>

<style scoped>
.review-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding-top: var(--space-huge);
}

/* ─── 今日进度条 ─────────────────────────────────────────── */
.review-progress-track {
  position: fixed;
  top: 0;
  left: var(--sidebar-width);
  right: 0;
  height: 3px;
  background-color: var(--color-primary-mid);
  z-index: 95;
}
.review-progress-fill {
  height: 100%;
  background-color: var(--color-surface-violet);
  transition: width 0.4s ease;
}

/* ─── Toast ──────────────────────────────────────────────── */
.review-toast {
  position: fixed;
  top: calc(var(--space-lg) + env(safe-area-inset-top));
  right: var(--space-xl);
  display: flex;
  align-items: center;
  gap: var(--space-md);
  background-color: var(--color-primary-deep);
  border: 1px solid var(--color-surface-violet);
  color: var(--color-surface-violet);
  border-radius: var(--radius-sm);
  padding: 8px 16px;
  font-size: var(--text-caption);
  z-index: 150;
  pointer-events: none;
  max-width: 80vw;
}
.review-toast.actionable {
  pointer-events: auto;
}
.toast-undo-btn {
  background: transparent;
  border: 1px solid var(--color-surface-violet);
  border-radius: var(--radius-sm);
  color: var(--color-surface-violet);
  font-size: var(--text-micro);
  padding: 2px 10px;
  cursor: pointer;
  flex-shrink: 0;
}
.toast-undo-btn:hover {
  background-color: rgba(201, 180, 250, 0.12);
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.review-scope-row {
  margin-bottom: var(--space-lg);
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

.review-done-summary {
  margin-top: var(--space-lg);
  color: var(--color-on-dark-mute);
}
.review-done-summary strong {
  color: var(--color-surface-violet);
  font-weight: 540;
}

.review-active {
  flex: 1;
  max-width: 680px;
  margin: 0 auto;
  width: 100%;
}

.review-meta {
  margin-bottom: var(--space-lg);
  opacity: 0.5;
  transition: opacity 0.3s ease;
}
.review-meta:hover {
  opacity: 1;
}

.review-autospeak-btn {
  background: transparent;
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-sm);
  color: var(--color-on-dark-mute);
  font-size: var(--text-micro);
  padding: 2px 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.review-autospeak-btn.on {
  color: var(--color-surface-violet);
  border-color: var(--color-surface-violet);
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

/* 触屏：meta 常显、键盘提示无意义 */
@media (hover: none) {
  .review-meta {
    opacity: 1;
  }
  .review-keyboard-hint {
    display: none;
  }
}
</style>
