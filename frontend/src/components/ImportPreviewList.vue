<script setup lang="ts">
/**
 * LLM 拆解结果预览确认：入库前勾选/编辑/剔除卡片。
 * 把人的判断放在入库前，而不是事后删卡。
 */
import { ref, computed, watch } from 'vue'
import type { CardCandidate } from '../api'

const props = defineProps<{
  cards: CardCandidate[]
  title: string
  submitting: boolean
}>()

const emit = defineEmits<{
  confirm: [cards: CardCandidate[]]
  cancel: []
}>()

interface EditableCard extends CardCandidate {
  checked: boolean
}

const items = ref<EditableCard[]>([])

watch(
  () => props.cards,
  (cards) => {
    items.value = cards.map(c => ({ ...c, checked: true }))
  },
  { immediate: true }
)

const selectedCount = computed(() => items.value.filter(i => i.checked).length)

function confirm() {
  const selected = items.value
    .filter(i => i.checked)
    .map(({ content, quiz }) => ({ content: content.trim(), quiz: quiz.trim() }))
    .filter(c => c.content && c.quiz)
  if (selected.length > 0) emit('confirm', selected)
}
</script>

<template>
  <div class="card preview-card mt-xl">
    <div class="flex items-center justify-between">
      <h3 class="preview-title">拆解预览 <span class="text-faint text-xs">{{ title }}</span></h3>
      <span class="badge">已选 {{ selectedCount }}/{{ items.length }} 张</span>
    </div>
    <p class="text-faint text-sm" style="margin-top: var(--space-xs)">
      入库前最后一道关：取消勾选剔除废卡，直接点击文字可修改
    </p>

    <ul class="preview-list mt-lg">
      <li v-for="(item, idx) in items" :key="idx" class="preview-item" :class="{ unchecked: !item.checked }">
        <input v-model="item.checked" type="checkbox" class="preview-check" />
        <div class="preview-fields">
          <input v-model="item.quiz" class="preview-input preview-quiz" placeholder="提示（问题）" />
          <input v-model="item.content" class="preview-input preview-content" placeholder="原句（答案）" />
        </div>
      </li>
    </ul>

    <div class="flex items-center justify-between mt-xl">
      <button class="btn btn-ghost" :disabled="submitting" @click="emit('cancel')">← 返回修改</button>
      <button class="btn btn-primary" :disabled="submitting || selectedCount === 0" @click="confirm" style="min-width: 140px">
        <span v-if="submitting" class="spinner" style="width:16px;height:16px"></span>
        <span v-else>✓ 确认入库 {{ selectedCount }} 张</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.preview-card {
  background-color: var(--color-primary-mid);
}

.preview-title {
  font-size: var(--text-body-lg);
  font-weight: 540;
}

.preview-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  max-height: 55vh;
  overflow-y: auto;
}

.preview-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
  padding: var(--space-md);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-sm);
  background-color: var(--color-primary-deep);
  transition: opacity 0.2s ease;
}

.preview-item.unchecked {
  opacity: 0.35;
}

.preview-check {
  margin-top: 8px;
  accent-color: var(--color-surface-violet);
  flex-shrink: 0;
}

.preview-fields {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  min-width: 0;
}

.preview-input {
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-xs);
  color: var(--color-on-primary);
  font-family: var(--font-sans);
  padding: 2px 6px;
  width: 100%;
  transition: border-color 0.2s ease;
}
.preview-input:hover {
  border-color: var(--color-hairline-dark);
}
.preview-input:focus {
  border-color: var(--color-surface-violet);
  outline: none;
  background-color: rgba(0, 0, 0, 0.2);
}

.preview-quiz {
  font-size: var(--text-caption);
  color: var(--color-on-dark-mute);
}

.preview-content {
  font-size: var(--text-body-md);
}
</style>
