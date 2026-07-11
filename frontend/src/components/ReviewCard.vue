<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Block } from '../api'

const props = defineProps<{
  card: Block
  flipped: boolean
  submitting: boolean
  /** Passage mode: show undo button */
  showUndo: boolean
  /** Last passage rating label */
  lastRatingLabel: string
  /** 翻面时自动朗读答案句 */
  autoSpeak?: boolean
}>()

const emit = defineEmits<{
  flip: []
  rate: [quality: number, label: string]
  undo: []
  edit: []
}>()

const ratings = [
  { quality: 1, label: '忘了', shortcut: '1' },
  { quality: 3, label: '难', shortcut: '2' },
  { quality: 4, label: '良', shortcut: '3' },
  { quality: 5, label: '简单', shortcut: '4' },
] as const

/** 浏览器原生 TTS 朗读英文句子（iOS Safari 需要用户手势触发，点击即满足） */
function speak(text: string) {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  const utter = new SpeechSynthesisUtterance(text)
  utter.lang = 'en-US'
  const voice = window.speechSynthesis
    .getVoices()
    .find((v) => v.lang.startsWith('en-US'))
  if (voice) utter.voice = voice
  utter.rate = 0.95
  window.speechSynthesis.speak(utter)
}

// 翻面自动朗读（开关在复习页 meta 行）
watch(
  () => props.flipped,
  (flipped) => {
    if (flipped && props.autoSpeak) speak(props.card.content)
  }
)

// 附属知识点"胶囊遮罩"：触屏没有 hover，改为点按切换
const isTouch = window.matchMedia('(hover: none)').matches
const revealedNotes = ref<Set<number>>(new Set())

watch(
  () => props.card.id,
  () => revealedNotes.value = new Set()
)

function toggleNote(idx: number) {
  const next = new Set(revealedNotes.value)
  if (next.has(idx)) next.delete(idx)
  else next.add(idx)
  revealedNotes.value = next
}
</script>

<template>
  <div class="card review-card" style="min-height: 340px; position: relative;">
    <!-- Undo Button (passage mode) -->
    <div v-if="showUndo" class="review-undo-container flex items-center">
      <button class="btn btn-ghost text-xs review-undo-btn" @click="emit('undo')" title="快捷键: Backspace">
        ⬅️ 上一句
      </button>
      <span class="text-faint text-xs ml-sm">
        (上一句: {{ lastRatingLabel }})
      </span>
    </div>

    <p class="review-card-label text-xs text-faint">问题</p>
    <p class="review-question dim">{{ card.quiz }}</p>

    <!-- Front: show answer button -->
    <div v-if="!flipped" class="review-card-actions" style="margin-top: auto;">
      <button
        class="btn btn-pill"
        @click="emit('flip')"
        style="font-size: var(--text-body-md)"
      >
        查看答案
        <span class="text-xs" style="opacity: 0.6">Space</span>
      </button>
    </div>

    <!-- Back: answer + notes + rating -->
    <Transition name="card-reveal">
      <div v-if="flipped" class="review-card-back-section">
        <div class="divider" style="margin: var(--space-xl) 0;"></div>

        <p class="review-card-label text-xs text-faint">答案</p>
        <div class="review-answer-row">
          <p class="review-answer">{{ card.content }}</p>
          <button class="btn-speak" @click.stop="speak(card.content)" title="朗读句子">🔊</button>
          <button class="btn-speak" @click.stop="emit('edit')" title="编辑卡片">✏️</button>
        </div>

        <!-- Notes Section -->
        <div v-if="card.notes && card.notes.length > 0" class="review-notes-section">
          <div class="divider" style="margin: var(--space-md) 0; opacity: 0.5;"></div>
          <p class="review-card-label text-xs text-faint" style="margin-bottom: var(--space-sm);">附属知识点 <span style="text-transform: none; opacity: 0.5; margin-left: 4px;">{{ isTouch ? '(点按查看翻译)' : '(悬浮查看翻译)' }}</span></p>
          <ul class="review-notes-list">
            <li v-for="(note, idx) in card.notes" :key="idx" class="review-note-item">
              <span class="note-zh">{{ note.zh }}</span>
              <span class="note-en-row"><span class="note-en-mask" :class="{ revealed: revealedNotes.has(idx) }" @click="toggleNote(idx)">{{ note.en }}</span><button class="btn-speak btn-speak-sm" @click.stop="speak(note.en)" title="朗读">🔊</button></span>
            </li>
          </ul>
        </div>

        <!-- Rating buttons -->
        <div class="review-ratings" v-if="!submitting">
          <button
            v-for="r in ratings"
            :key="r.quality"
            class="btn review-rating-btn"
            @click="emit('rate', r.quality, r.label)"
          >
            <span class="rating-label">{{ r.label }}</span>
            <span class="rating-shortcut">[{{ r.shortcut }}]</span>
          </button>
        </div>
        <div v-else class="review-submitting flex items-center gap-md mt-xl" style="justify-content: center;">
          <div class="spinner"></div>
          <span class="text-mute text-sm">提交中...</span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.review-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  background-color: var(--color-primary-mid);
  border-color: var(--color-hairline-dark);
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
  font-size: var(--text-body-lg);
}

.review-answer-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-md);
}

.review-answer {
  font-size: var(--text-display-md);
  font-weight: 540;
  line-height: 1.6;
  color: #ffffff;
  letter-spacing: -0.135px;
}

.btn-speak {
  background: transparent;
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-sm);
  color: var(--color-on-surface);
  cursor: pointer;
  padding: 2px 8px;
  font-size: var(--text-body-md);
  opacity: 0.6;
  transition: all 0.2s ease;
  flex-shrink: 0;
}
.btn-speak:hover {
  opacity: 1;
  border-color: var(--color-surface-violet);
}
.btn-speak-sm {
  font-size: var(--text-xs);
  padding: 0 6px;
  margin-left: var(--space-sm);
  vertical-align: middle;
}
.note-en-row {
  display: inline-flex;
  align-items: center;
  margin-top: 4px;
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
.note-en-mask:active,
.note-en-mask.revealed {
  background-color: transparent;
  color: #ffffff;
}

.review-card-actions {
  display: flex;
  justify-content: center;
  padding-top: var(--space-lg);
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

/* ─── 移动端：操作区固定底栏，叠在底部 Tab 导航之上 ────── */
@media (max-width: 768px) {
  .review-card-actions,
  .review-ratings,
  .review-submitting {
    position: fixed;
    bottom: calc(var(--mobile-nav-h) + env(safe-area-inset-bottom));
    left: 0;
    right: 0;
    width: auto; /* 覆盖基础规则的 width:100%，否则叠加 left 偏移会横向溢出 */
    margin: 0;
    padding: var(--space-md) var(--space-lg);
    background-color: var(--color-primary-deep);
    border-top: 1px solid var(--color-hairline-dark);
    z-index: 90;
  }

  .review-ratings {
    gap: var(--space-sm);
  }

  .review-rating-btn {
    min-height: 48px;
    padding: 10px 4px;
    min-width: 0; /* 允许四键在窄屏均分收缩 */
  }

  .review-card-actions .btn-pill {
    width: 100%;
    min-height: 48px;
    justify-content: center;
  }

  /* 给固定底栏让位，避免卡片内容被盖住 */
  .review-card {
    margin-bottom: 84px;
  }
}

/* 触屏：键盘快捷键角标无意义 */
@media (hover: none) {
  .rating-shortcut {
    display: none;
  }
}
</style>
