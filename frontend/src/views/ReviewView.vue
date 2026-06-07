<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchNextCard, submitReview, submitBatchReview, type Block } from '../api'
import { useDeckStore } from '../stores/deck'

const deckStore = useDeckStore()

// ─── State ────────────────────────────────────────────────
const card        = ref<Block | null>(null)
const remaining   = ref(0)
const isNew       = ref(false)
const flipped     = ref(false)
const loading     = ref(false)
const submitting  = ref(false)
const error       = ref('')
const done        = ref(false)          // no more cards today
const lastResult  = ref<string>('')     // feedback after rating
const sourceTitle = ref<string | null>(null)
const deckName    = ref<string | null>(null)

// Passage review state
const reviewMode     = ref<'card' | 'passage'>('card')
const batchCards     = ref<Block[]>([])
const batchIndex     = ref(0)
const batchQualities = ref<number[]>([])

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
const ratings = [
  { quality: 1, label: '忘了', shortcut: '1' },
  { quality: 3, label: '难', shortcut: '2' },
  { quality: 4, label: '良', shortcut: '3' },
  { quality: 5, label: '简单', shortcut: '4' },
] as const

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
      // Continue passage
      card.value = batchCards.value[batchIndex.value]
      flipped.value = false
      // Removed the '上一句' feedback as requested
    } else {
      // Finish passage
      submitting.value = true
      const overall = calculatePassageQuality(batchQualities.value)
      try {
        const blockIds = batchCards.value.map(b => b.id)
        const res = await submitBatchReview(blockIds, overall)
        lastResult.value = `✓ 整段 ${res.message}`
        setTimeout(() => loadNext(), 1200)
      } catch (e: unknown) {
        error.value = e instanceof Error ? e.message : '批量提交失败'
        submitting.value = false
      }
    }
  } else {
    // Normal single card mode
    submitting.value = true
    try {
      const res = await submitReview(card.value.id, quality)
      lastResult.value = `✓ ${label} — 下次复习：${new Date(res.next_review).toLocaleDateString('zh-CN')}`
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
      const r = ratings.find(r => r.shortcut === '3') // 默认"良好"
      if (r) rate(r.quality, r.label)
    }
    return
  }
  if (flipped.value && card.value) {
    const r = ratings.find(r => r.shortcut === e.key)
    if (r) rate(r.quality, r.label)
  }
}

// ─── Progress ─────────────────────────────────────────────
const progressLabel = computed(() => {
  if (!card.value) return ''
  let label = `${isNew.value ? '新内容' : '复习'} · 剩余 ${remaining.value} 组`
  if (reviewMode.value === 'passage' && batchCards.value.length > 0) {
    label += ` (${batchIndex.value + 1}/${batchCards.value.length})`
  }
  return label
})

// ─── Source/Deck label ────────────────────────────────────
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

      <!-- Single Expandable Card -->
      <div class="card review-card mt-xl" style="min-height: 340px; position: relative;">
        <!-- Undo Button -->
        <div v-if="reviewMode === 'passage' && batchIndex > 0" class="review-undo-container flex items-center">
          <button class="btn btn-ghost text-xs review-undo-btn" @click="undo" title="快捷键: Backspace">
            ⬅️ 上一句
          </button>
          <span class="text-faint text-xs ml-sm">
            (上一句: {{ ratings.find(r => r.quality === batchQualities[batchQualities.length - 1])?.label || '未知' }})
          </span>
        </div>

        <p class="review-card-label text-xs text-faint">问题</p>
        <p class="review-question dim">{{ card.quiz }}</p>

        <!-- Front actions: Only show when NOT flipped -->
        <div v-if="!flipped" class="review-card-actions" style="margin-top: auto;">
          <button
            class="btn btn-pill"
            @click="flipped = true"
            style="font-size: var(--text-body-md)"
          >
            查看答案
            <span class="text-xs" style="opacity: 0.6">Space</span>
          </button>
        </div>

        <!-- Back part: answer + rating -->
        <Transition name="card-reveal">
          <div v-if="flipped" class="review-card-back-section">
            <div class="divider" style="margin: var(--space-xl) 0;"></div>

            <p class="review-card-label text-xs text-faint">答案</p>
            <p class="review-answer">{{ card.content }}</p>

            <!-- Notes Section (Sub-cards) -->
            <div v-if="card.notes && card.notes.length > 0" class="review-notes-section">
              <div class="divider" style="margin: var(--space-md) 0; opacity: 0.5;"></div>
              <p class="review-card-label text-xs text-faint" style="margin-bottom: var(--space-sm);">附属知识点 <span style="text-transform: none; opacity: 0.5; margin-left: 4px;">(悬浮查看翻译)</span></p>
              <ul class="review-notes-list">
                <li v-for="(note, idx) in card.notes" :key="idx" class="review-note-item">
                  <span class="note-zh">{{ note.zh }}</span>
                  <span class="note-en-mask">{{ note.en }}</span>
                </li>
              </ul>
            </div>

            <!-- Feedback after submitting -->
            <Transition name="fade">
              <p v-if="lastResult" class="review-result text-violet text-sm">{{ lastResult }}</p>
            </Transition>

            <!-- Rating buttons -->
            <div class="review-ratings" v-if="!submitting">
              <button
                v-for="r in ratings"
                :key="r.quality"
                class="btn review-rating-btn"
                @click="rate(r.quality, r.label)"
              >
                <span class="rating-label">{{ r.label }}</span>
                <span class="rating-shortcut">[{{ r.shortcut }}]</span>
              </button>
            </div>
            <div v-else class="flex items-center gap-md mt-xl" style="justify-content: center;">
              <div class="spinner"></div>
              <span class="text-mute text-sm">提交中...</span>
            </div>
          </div>
        </Transition>
      </div>

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

/* Override flip-card-inner for auto-height */
.flip-card-inner {
  min-height: 340px;
}

.review-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  background-color: var(--color-primary-mid);
  border-color: var(--color-hairline-dark);
}

.review-card-back {
  /* absolute positioning within flip container is off — we show both stacked */
  position: relative !important;
  transform: none !important;
  backface-visibility: visible !important;
  -webkit-backface-visibility: visible !important;
}

.review-undo-container {
  position: absolute;
  top: var(--space-md);
  right: var(--space-md);
}

.review-undo-btn {
  padding: 4px 8px;
  background-color: transparent;
  color: var(--color-on-surface);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-sm);
  opacity: 0.6;
}
.review-undo-btn:hover {
  opacity: 1;
  background-color: var(--color-primary-deep);
}

.review-card-label {
  font-weight: 540;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.review-question {
  font-size: var(--text-display-md);
  font-weight: 460;
  letter-spacing: -0.315px;
  line-height: 1.4;
  flex: 1;
  color: var(--color-on-primary);
}

.review-question.dim {
  opacity: 0.6;
  font-size: var(--text-body-lg); /* Slightly smaller to de-emphasize */
}

.review-question-sm {
  font-size: var(--text-body-lg);
  font-weight: 460;
  line-height: 1.4;
}

.review-answer {
  font-size: var(--text-display-md); /* Slightly reduced from lg */
  font-weight: 540;
  line-height: 1.6;
  color: #ffffff; /* Absolute white */
  letter-spacing: -0.135px;
}

/* ─── Notes ────────────────────────────────────────────── */
.review-notes-section {
  margin-top: var(--space-xl);
}
.review-notes-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}
.review-note-item {
  font-size: var(--text-body-md);
  line-height: 1.5;
  display: flex;
  flex-direction: column;
}
.note-zh {
  color: var(--color-on-primary);
  opacity: 0.6;
}
.note-en-mask {
  display: inline-block;
  background-color: rgba(255, 255, 255, 0.1);
  color: transparent;
  border-radius: var(--radius-sm);
  padding: 2px 8px 2px 4px;
  margin-left: -4px;
  cursor: pointer;
  transition: all 0.3s ease;
  width: fit-content;
  margin-top: 4px;
}
.note-en-mask:hover,
.note-en-mask:active {
  background-color: transparent;
  color: #ffffff;
}

.review-card-actions {
  display: flex;
  justify-content: center;
  padding-top: var(--space-lg);
}

.review-result {
  text-align: center;
  margin-top: var(--space-md);
}

.review-ratings {
  display: flex;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-md);
  margin-top: var(--space-xl);
}

.review-rating-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  padding: 10px 16px;
  background-color: transparent;
  border: 1px solid var(--color-hairline-dark);
  color: var(--color-on-surface);
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
}

.review-rating-btn:hover:not(:disabled) {
  background-color: rgba(255, 255, 255, 0.05);
  border-color: var(--color-surface-violet);
  color: var(--color-on-primary);
}

.rating-label {
  font-size: var(--text-body-md);
  font-weight: 500;
}

.rating-shortcut {
  font-size: var(--text-xs);
  opacity: 0.5;
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

/* Flip — simplified: just show back inline when flipped */
.flip-card { perspective: none; }
.flip-card-inner { transform-style: flat; }
.flip-card-inner.flipped { transform: none; }
.flip-card-front { position: relative; backface-visibility: visible; -webkit-backface-visibility: visible; }
.flip-card-back  { position: relative; transform: none; backface-visibility: visible; -webkit-backface-visibility: visible; }

/* 翻牌揭示动画 */
.card-reveal-enter-active {
  transition: opacity 0.28s ease, transform 0.28s ease;
}
.card-reveal-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.card-reveal-enter-to {
  opacity: 1;
  transform: translateY(0);
}
</style>
