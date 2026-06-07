<script setup lang="ts">
import { ref } from 'vue'
import { importSource, type Block } from '../api'
import { useDeckStore } from '../stores/deck'
import DeckSelector from './DeckSelector.vue'
import ImportResultCard from './ImportResultCard.vue'

const deckStore = useDeckStore()

const text    = ref('')
const title   = ref('')
const deckId  = ref<number | null>(deckStore.selectedDeckId)
const loading = ref(false)
const error   = ref('')
const result  = ref<{ title: string; blocks: Block[]; deckId: number | null; warning: string | null } | null>(null)

async function handleImport() {
  if (!text.value.trim() || text.value.trim().length < 10) {
    error.value = '文本太短（至少 10 个字符）'
    return
  }
  loading.value = true
  error.value   = ''
  result.value  = null
  try {
    const data = await importSource(text.value.trim(), title.value.trim() || undefined, deckId.value)
    result.value = { title: data.title, blocks: data.blocks, deckId: data.deck_id, warning: data.warning ?? null }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '导入失败'
  } finally {
    loading.value = false
  }
}

function reset() {
  text.value   = ''
  title.value  = ''
  result.value = null
  error.value  = ''
}
</script>

<template>
  <!-- Import form -->
  <div v-if="!result" class="card import-card mt-xl">
    <div class="form-group">
      <label class="form-label">选择 Deck</label>
      <DeckSelector v-model="deckId" allow-null show-strategy />
    </div>

    <div class="form-group mt-lg">
      <label class="form-label">标题（可选）</label>
      <input id="import-title" v-model="title" class="form-input" type="text" placeholder="留空则自动取文本前 20 字" />
    </div>

    <div class="form-group mt-lg">
      <label class="form-label">内容</label>
      <textarea
        id="import-text"
        v-model="text"
        class="form-textarea"
        placeholder="粘贴 Markdown 或文本内容…&#10;&#10;例：# 南山南&#10;It's just a matter of minutes.&#10;A man has his pride."
        style="min-height: 260px; font-family: monospace; font-size: 14px;"
      />
    </div>

    <p v-if="error" class="import-error">⚠️ {{ error }}</p>

    <div class="flex items-center justify-between mt-xl">
      <p class="text-faint text-sm">AI 会按 Deck 策略自动拆解文本</p>
      <button id="import-submit" class="btn btn-primary" :disabled="loading || text.trim().length < 10" @click="handleImport" style="min-width: 140px;">
        <span v-if="loading" class="spinner" style="width:16px; height:16px;"></span>
        <span v-else>🚀 AI 智能拆解</span>
      </button>
    </div>
  </div>

  <!-- Result -->
  <ImportResultCard
    v-else
    class="mt-xl"
    :title="result.title"
    :blocks="result.blocks"
    :deck-id="result.deckId"
    :warning="result.warning"
    @reset="reset"
  />
</template>

<style scoped>
.import-card {
  background-color: var(--color-primary-mid);
}
.import-error {
  color: #e57373;
  font-size: var(--text-caption);
  margin-top: var(--space-md);
}
</style>
