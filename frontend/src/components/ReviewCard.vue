<script setup lang="ts">
import type { Block } from '../api'

defineProps<{
  card: Block
  flipped: boolean
  submitting: boolean
  lastResult: string
  /** Passage mode: show undo button */
  showUndo: boolean
  /** Last passage rating label */
  lastRatingLabel: string
}>()

const emit = defineEmits<{
  flip: []
  rate: [quality: number, label: string]
  undo: []
}>()

const ratings = [
  { quality: 1, label: '忘了', shortcut: '1' },
  { quality: 3, label: '难', shortcut: '2' },
  { quality: 4, label: '良', shortcut: '3' },
  { quality: 5, label: '简单', shortcut: '4' },
] as const
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
        <p class="review-answer">{{ card.content }}</p>

        <!-- Notes Section -->
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

        <!-- Feedback -->
        <Transition name="fade">
          <p v-if="lastResult" class="review-result text-violet text-sm">{{ lastResult }}</p>
        </Transition>

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
        <div v-else class="flex items-center gap-md mt-xl" style="justify-content: center;">
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

.review-answer {
  font-size: var(--text-display-md);
  font-weight: 540;
  line-height: 1.6;
  color: #ffffff;
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
