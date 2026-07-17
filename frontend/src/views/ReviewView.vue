<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import {
  fetchNextCard, submitReview, submitBatchReview, fetchTodaySummary, undoReview,
  type Block, type TodaySummary, type ReviewNextResponse,
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

// 文章切换提示：本次会话内跨 Source 时给个轻提醒
const prevSourceId    = ref<number | null>(null)
const articleSwitched = ref(false)

// 评分按钮上的预测间隔（仅单卡模式，随 /review/next 返回）
const predictedIntervals = ref<Record<string, string> | null>(null)

// 预取的下一张卡：评分后立即切换，消除切卡等待
const nextData = ref<ReviewNextResponse | null>(null)
let loadGen = 0 // 换 Deck / 撤销等强制重载时递增，作废在途预取

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
    card.value = { ...card.value, quiz: updated.quiz, content: updated.content, notes: updated.notes }
  }
  const idx = batchCards.value.findIndex(b => b.id === updated.id)
  if (idx >= 0) batchCards.value[idx] = { ...batchCards.value[idx], quiz: updated.quiz, content: updated.content, notes: updated.notes }
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
function applyData(data: ReviewNextResponse) {
  flipped.value = false
  submitting.value = false

  if (!data.block && (!data.batch || data.batch.length === 0)) {
    done.value = true
    card.value = null
    batchCards.value = []
    articleSwitched.value = false
    return
  }

  remaining.value = data.remaining
  isNew.value   = data.is_new
  sourceTitle.value = data.source_title ?? null
  deckName.value    = data.deck_name ?? null
  predictedIntervals.value = data.predicted_intervals ?? null
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

  const sid = card.value?.source_id ?? null
  articleSwitched.value = prevSourceId.value !== null && sid !== null && sid !== prevSourceId.value
  if (sid !== null) prevSourceId.value = sid
}

/** 后台预取下一张（排除当前卡）；只在单卡模式下有意义 */
function prefetch() {
  if (done.value || reviewMode.value === 'passage' || !card.value) return
  const gen = loadGen
  fetchNextCard(deckStore.selectedDeckId, card.value.id)
    .then((d) => { if (gen === loadGen) nextData.value = d })
    .catch(() => { /* 预取失败无妨，评分时退回同步路径 */ })
}

async function loadNext() {
  const gen = ++loadGen
  nextData.value = null
  loading.value = true
  error.value   = ''
  flipped.value = false
  submitting.value = false
  try {
    const [data, summary] = await Promise.all([
      fetchNextCard(deckStore.selectedDeckId),
      fetchTodaySummary(deckStore.selectedDeckId).catch(() => null),
    ])
    if (gen !== loadGen) return
    today.value = summary
    applyData(data)
    prefetch()
  } catch (e: unknown) {
    if (gen !== loadGen) return
    error.value = e instanceof Error ? e.message : '连接失败，请确认后端已启动'
  } finally {
    if (gen === loadGen) loading.value = false
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
    const ratedId = card.value.id
    const next = nextData.value

    if (next && (next.block || (next.batch && next.batch.length > 0))) {
      // 乐观切卡：立即显示预取好的下一张，评分在后台提交（成功后再预取下下张）
      nextData.value = null
      applyData(next)
      submitReview(ratedId, quality)
        .then((res) => {
          statsStore.invalidate()
          showToast(`✓ ${label} — ${res.message.split('→ ')[1] ?? res.message}`, ratedId)
          fetchTodaySummary(deckStore.selectedDeckId).then((s) => { today.value = s }).catch(() => {})
          prefetch()
        })
        .catch(() => {
          // 提交失败该卡仍留在队列里，之后会重新出现，不打断当前复习
          showToast('⚠️ 评分提交失败，这张卡稍后会重新出现')
        })
      return
    }

    // 预取未就绪，或预取显示队列见底（🎉 完成页必须由权威查询判定，
    // 因为 FSRS 学习步可能让刚评的卡几分钟后就再次到期）：走同步路径
    submitting.value = true
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
        <p class="review-done-emoji">🎉</p>
        <h2 class="review-done-title">今天全部完成！</h2>
        <p v-if="today && today.reviewed > 0" class="review-done-summary">
          今日复习 <strong>{{ today.reviewed }}</strong> 次<template v-if="retentionLabel !== null">
            · 记住率 <strong>{{ retentionLabel }}%</strong></template>
        </p>
        <p v-if="today && today.streak > 1" class="review-done-streak">
          🔥 连续学习 <strong>{{ today.streak }}</strong> 天
        </p>
        <p class="text-mute review-done-tomorrow">
          <template v-if="today && today.due_tomorrow > 0">
            明天到期 <strong>{{ today.due_tomorrow }}</strong> 张 — 明天见 👋
          </template>
          <template v-else>明天暂无到期卡片，好好休息 🌙</template>
        </p>
      </div>
    </div>

    <!-- Active card -->
    <div v-else-if="card" class="review-active">

      <!-- 信息区：第一行 = 卡片身份，第二行 = 范围 + 进度 -->
      <div class="review-meta">
        <div class="review-meta-main">
          <span class="badge badge-truncate" :title="cardLabel">📖 {{ cardLabel }}</span>
          <span v-if="isNew" class="badge badge-new">新卡片</span>
          <button
            class="review-autospeak-btn"
            :class="{ on: autoSpeak }"
            @click="toggleAutoSpeak"
            :title="autoSpeak ? '翻面自动朗读：开' : '翻面自动朗读：关'"
          >🔊 {{ autoSpeak ? '自动' : '手动' }}</button>
        </div>
        <div class="review-meta-sub">
          <span class="review-deck-scope text-xs desktop-only">🗂️ {{ currentDeckLabel }}</span>
          <span class="text-faint text-xs review-progress-label">{{ progressLabel }}</span>
        </div>
      </div>

      <!-- 文章切换提示 -->
      <div v-if="articleSwitched" class="article-switch-banner mt-lg">
        📄 上一篇已读完 · 开始新文章<template v-if="sourceTitle">《{{ sourceTitle }}》</template>
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
        :predicted-intervals="reviewMode === 'card' ? predictedIntervals : null"
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

.review-done-emoji {
  font-size: 56px;
  margin-bottom: var(--space-md);
  animation: done-pop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes done-pop {
  0% { transform: scale(0.3); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}

.review-done-streak {
  margin-top: var(--space-md);
  font-size: var(--text-body-lg);
}
.review-done-streak strong {
  color: var(--color-surface-violet);
  font-weight: 640;
}

.review-done-tomorrow {
  margin-top: var(--space-lg);
}
.review-done-tomorrow strong {
  color: var(--color-on-primary);
  font-weight: 540;
}

.review-active {
  flex: 1;
  max-width: 680px;
  margin: 0 auto;
  width: 100%;
}

.article-switch-banner {
  text-align: center;
  font-size: var(--text-caption);
  color: var(--color-surface-violet);
  border: 1px dashed var(--color-surface-violet);
  border-radius: var(--radius-sm);
  padding: 6px 12px;
  opacity: 0.85;
}

.review-meta {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  margin-bottom: var(--space-lg);
  opacity: 0.5;
  transition: opacity 0.3s ease;
}
.review-meta:hover {
  opacity: 1;
}

.review-meta-main {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  min-width: 0;
}

/* 来源标签可以很长：允许收缩并省略号截断（覆盖 .badge 的 inline-flex / 不收缩） */
.badge-truncate {
  display: block;
  flex-shrink: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.badge-new {
  color: var(--color-surface-violet);
  border-color: var(--color-surface-violet);
}

.review-meta-sub {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}
.review-progress-label {
  margin-left: auto;
}

.review-autospeak-btn {
  margin-left: auto;
  flex-shrink: 0;
  white-space: nowrap;
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

/* 窄屏：toast 移到底部操作栏上方居中（顶部会撞状态栏/刘海，且离拇指太远） */
@media (max-width: 768px) {
  .review-toast {
    top: auto;
    bottom: calc(var(--mobile-nav-h) + env(safe-area-inset-bottom) + 88px);
    left: var(--space-lg);
    right: var(--space-lg);
    width: fit-content;
    margin: 0 auto;
  }
  .toast-enter-from,
  .toast-leave-to {
    transform: translateY(8px); /* 从底部方向淡入淡出 */
  }
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
