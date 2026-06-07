<script setup lang="ts">
import { ref } from 'vue'
import { importSource, fetchUrlPreview, type Block, type UrlPreviewResponse } from '../api'
import { useDeckStore } from '../stores/deck'
import DeckSelector from './DeckSelector.vue'
import ImportResultCard from './ImportResultCard.vue'

const deckStore = useDeckStore()

const urlInput     = ref('')
const urlDeckId    = ref<number | null>(deckStore.selectedDeckId)
const urlLoading   = ref(false)
const urlImporting = ref(false)
const urlError     = ref('')
const urlPreview   = ref<UrlPreviewResponse | null>(null)
const urlResult    = ref<{ title: string; blocks: Block[]; deckId: number | null; warning: string | null } | null>(null)

async function handleUrlFetch() {
  const u = urlInput.value.trim()
  if (!u || !u.startsWith('http')) {
    urlError.value = '请输入有效的 http/https 链接'
    return
  }
  urlLoading.value = true
  urlError.value   = ''
  urlPreview.value = null
  urlResult.value  = null
  try {
    urlPreview.value = await fetchUrlPreview(u)
  } catch (e: unknown) {
    urlError.value = e instanceof Error ? e.message : '抓取失败'
  } finally {
    urlLoading.value = false
  }
}

async function handleUrlImport() {
  if (!urlPreview.value) return
  if (!urlDeckId.value) { urlError.value = '请选择 Deck'; return }
  urlImporting.value = true
  urlError.value = ''
  try {
    const data = await importSource(
      urlPreview.value.text,
      urlPreview.value.title || undefined,
      urlDeckId.value,
    )
    urlResult.value = { title: data.title, blocks: data.blocks, deckId: data.deck_id, warning: data.warning ?? null }
  } catch (e: unknown) {
    urlError.value = e instanceof Error ? e.message : '导入失败'
  } finally {
    urlImporting.value = false
  }
}

function resetUrl() {
  urlInput.value   = ''
  urlPreview.value = null
  urlResult.value  = null
  urlError.value   = ''
}
</script>

<template>
  <!-- URL import form -->
  <div v-if="!urlResult" class="card import-card mt-xl">

    <!-- URL input -->
    <div class="form-group">
      <label class="form-label">URL 链接</label>
      <div class="flex gap-md">
        <input
          id="url-input"
          v-model="urlInput"
          class="form-input"
          type="url"
          placeholder="https://example.com/article..."
          @keydown.enter="handleUrlFetch"
          style="flex: 1"
        />
        <button
          id="url-fetch-btn"
          class="btn btn-ghost"
          :disabled="urlLoading || !urlInput.trim()"
          @click="handleUrlFetch"
          style="white-space: nowrap; min-width: 100px"
        >
          <span v-if="urlLoading" class="spinner" style="width:16px;height:16px"></span>
          <span v-else>🔍 抓取</span>
        </button>
      </div>
    </div>

    <!-- Preview area -->
    <div v-if="urlPreview" class="url-preview mt-xl">
      <div class="flex items-center justify-between" style="margin-bottom: var(--space-md)">
        <div>
          <p class="url-preview-title">{{ urlPreview.title || '(no title)' }}</p>
          <p class="text-xs text-faint mt-xs">{{ urlPreview.char_count.toLocaleString() }} 字符 · {{ urlPreview.url }}</p>
        </div>
        <button class="btn btn-ghost" style="font-size: var(--text-caption)" @click="urlPreview = null">重新抓取</button>
      </div>
      <textarea
        class="form-textarea url-preview-text"
        :value="urlPreview.text"
        readonly
        style="min-height: 180px; font-size: 13px; opacity: 0.8"
      />

      <!-- Deck 选择 -->
      <div class="form-group mt-xl">
        <label class="form-label">选择 Deck</label>
        <DeckSelector v-model="urlDeckId" allow-null />
      </div>

      <p v-if="urlError" class="import-error">⚠️ {{ urlError }}</p>

      <div class="flex items-center justify-between mt-xl">
        <p class="text-faint text-sm">AI 会按 Deck 策略自动拆解文本</p>
        <button
          id="url-import-btn"
          class="btn btn-primary"
          :disabled="urlImporting || !urlPreview"
          @click="handleUrlImport"
          style="min-width: 140px"
        >
          <span v-if="urlImporting" class="spinner" style="width:16px;height:16px"></span>
          <span v-else>🚀 AI 智能拆解</span>
        </button>
      </div>
    </div>

    <p v-else-if="urlError" class="import-error mt-xl">⚠️ {{ urlError }}</p>

    <p v-else class="text-faint text-sm mt-xl">
      输入任意网页链接，自动抓取正文内容。
    </p>
  </div>

  <!-- Result -->
  <ImportResultCard
    v-else
    class="mt-xl"
    :title="urlResult.title"
    :blocks="urlResult.blocks"
    :deck-id="urlResult.deckId"
    :warning="urlResult.warning"
    @reset="resetUrl"
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
.url-preview {
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-md);
  padding: var(--space-lg);
  background-color: var(--color-primary-deep);
}
.url-preview-title {
  font-size: var(--text-body-md);
  font-weight: 540;
  color: var(--color-on-primary);
}
.url-preview-text {
  cursor: default;
  user-select: text;
  line-height: 1.7;
}
.mt-xs { margin-top: var(--space-xs); }
</style>
