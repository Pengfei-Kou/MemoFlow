<script setup lang="ts">
import type { Block } from '../api'
import { useDeckStore } from '../stores/deck'

const deckStore = useDeckStore()

defineProps<{
  title: string
  blocks: Block[]
  deckId: number | null
  warning: string | null
}>()

const emit = defineEmits<{
  reset: []
}>()

function getDeckPath(id: number | null): string {
  if (id == null) return '—'
  return deckStore.getDeckById(id)?.path ?? String(id)
}
</script>

<template>
  <div class="import-result">
    <div class="import-result-header flex items-center justify-between">
      <div>
        <h2 class="import-result-title">✅ 拆解完成</h2>
        <p class="text-mute mt-lg">
          《{{ title }}》— 共提取 <strong class="text-violet">{{ blocks.length }}</strong> 张卡片，已导入
          <strong class="text-violet">{{ getDeckPath(deckId) }}</strong>
        </p>
        <p v-if="warning" class="text-xs mt-sm" style="color:#ffb74d">⚠️ {{ warning }}</p>
      </div>
      <button class="btn btn-ghost" @click="emit('reset')">继续导入</button>
    </div>
    <div class="divider"></div>
    <div class="import-blocks">
      <div v-for="block in blocks" :key="block.id" class="import-block-item">
        <div class="import-block-q">
          <span class="text-xs text-faint" style="text-transform:uppercase; letter-spacing: 0.08em;">问</span>
          {{ block.quiz }}
        </div>
        <div class="import-block-a">
          <span class="text-xs text-faint" style="text-transform:uppercase; letter-spacing: 0.08em;">答</span>
          {{ block.content }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.import-result-title {
  font-size: var(--text-display-lg);
  font-weight: 540;
  letter-spacing: -0.63px;
}

.import-blocks {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  max-height: 60vh;
  overflow-y: auto;
  padding-right: var(--space-xs);
}

.import-block-item {
  background-color: var(--color-primary-deep);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-md);
  padding: var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.import-block-q {
  font-size: var(--text-body-md);
  color: var(--color-on-primary);
  display: flex;
  gap: var(--space-sm);
  align-items: baseline;
}

.import-block-a {
  font-size: var(--text-caption);
  color: var(--color-on-dark-mute);
  display: flex;
  gap: var(--space-sm);
  align-items: baseline;
}

.mt-sm { margin-top: var(--space-sm); }
</style>
