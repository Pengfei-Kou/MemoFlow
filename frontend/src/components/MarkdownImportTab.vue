<script setup lang="ts">
import { ref } from 'vue'
import AppIcon from './AppIcon.vue'
import { importMarkdownFile, type MarkdownImportResponse } from '../api'
import { useDeckStore } from '../stores/deck'
import DeckSelector from './DeckSelector.vue'

const deckStore = useDeckStore()

const mdFile       = ref<File | null>(null)
const mdDeckId     = ref<number | null>(deckStore.selectedDeckId)
const mdLoading    = ref(false)
const mdError      = ref('')
const mdResult     = ref<MarkdownImportResponse | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  mdFile.value = input.files?.[0] ?? null
  mdError.value = ''
}

function onFileDrop(e: DragEvent) {
  e.preventDefault()
  const file = e.dataTransfer?.files[0]
  if (file && file.name.endsWith('.md')) {
    mdFile.value = file
    mdError.value = ''
  } else {
    mdError.value = '请拖入 .md 文件'
  }
}

async function handleMarkdownImport() {
  if (!mdFile.value) { mdError.value = '请先选择 Markdown 文件'; return }
  if (!mdDeckId.value) { mdError.value = '请选择目标 Deck'; return }
  mdLoading.value = true
  mdError.value   = ''
  mdResult.value  = null
  try {
    mdResult.value = await importMarkdownFile(mdFile.value, mdDeckId.value)
  } catch (e: unknown) {
    mdError.value = e instanceof Error ? e.message : '导入失败'
  } finally {
    mdLoading.value = false
  }
}

function resetMarkdown() {
  mdFile.value   = null
  mdResult.value = null
  mdError.value  = ''
  if (fileInputRef.value) fileInputRef.value.value = ''
}
</script>

<template>
  <div v-if="!mdResult" class="card import-card mt-xl">

    <!-- Deck 选择 -->
    <div class="form-group">
      <label class="form-label">目标 Deck *</label>
      <DeckSelector v-model="mdDeckId" null-label="— 请选择 Deck —" />
      <p class="text-xs text-faint mt-xs">
        每个 H1 标题（# Video N）会创建为一个独立的 Source
      </p>
    </div>

    <!-- 文件上传区域 -->
    <div class="form-group mt-xl">
      <label class="form-label">Markdown 文件</label>
      <div
        class="drop-zone"
        :class="{ 'drop-zone-active': !!mdFile }"
        @dragover.prevent
        @drop="onFileDrop"
        @click="fileInputRef?.click()"
      >
        <input
          ref="fileInputRef"
          type="file"
          accept=".md,text/markdown"
          style="display:none"
          @change="onFileChange"
        />
        <div v-if="!mdFile" class="drop-zone-hint">
          <AppIcon name="doc" :size="36" />
          <p class="mt-lg text-mute">拖拽 .md 文件到此处，或点击选择</p>
          <p class="text-xs text-faint mt-sm">支持「郝炟英语口语」格式（中文句 + 英文翻译）</p>
        </div>
        <div v-else class="drop-zone-file">
          <AppIcon name="doc" :size="28" />
          <div>
            <p class="file-name">{{ mdFile.name }}</p>
            <p class="text-faint text-xs">{{ (mdFile.size / 1024).toFixed(1) }} KB · 点击重新选择</p>
          </div>
        </div>
      </div>
    </div>

    <p v-if="mdError" class="import-error">⚠️ {{ mdError }}</p>

    <!-- 格式说明 -->
    <div class="md-format-hint mt-lg">
      <p class="text-xs text-faint" style="font-weight: 540; margin-bottom: 6px;">支持的文件格式</p>
      <pre class="format-example">
# 1 Video 1
## 1.1 Content
中文句子
English translation.
- 中文例句：English example.

## 1.2 Quiz
（跳过不导入）</pre>
    </div>

    <div class="flex items-center justify-between mt-xl">
      <p class="text-faint text-sm">直接规则解析，不消耗 AI 配额</p>
      <button
        id="md-import-submit"
        class="btn btn-primary"
        :disabled="mdLoading || !mdFile || !mdDeckId"
        @click="handleMarkdownImport"
        style="min-width: 160px;"
      >
        <span v-if="mdLoading" class="spinner" style="width:16px; height:16px;"></span>
        <span v-else>⚡ 解析并导入</span>
      </button>
    </div>
  </div>

  <!-- MD import result -->
  <div v-else class="import-result mt-xl">
    <div class="import-result-header flex items-center justify-between">
      <div>
        <h2 class="import-result-title">✅ 导入完成！</h2>
        <p class="text-mute mt-lg">
          <strong class="text-violet">{{ mdResult.file_name }}</strong>
          → Deck「{{ mdResult.deck_name }}」
        </p>
        <div class="md-result-stats mt-lg">
          <div class="md-stat">
            <span class="md-stat-num text-violet">{{ mdResult.total_sources }}</span>
            <span class="md-stat-label">个 Source</span>
          </div>
          <div class="md-stat">
            <span class="md-stat-num text-violet">{{ mdResult.total_cards }}</span>
            <span class="md-stat-label">张卡片</span>
          </div>
        </div>
      </div>
      <button class="btn btn-ghost" @click="resetMarkdown">继续导入</button>
    </div>

    <div class="divider"></div>

    <div class="md-sources-list">
      <div v-for="src in mdResult.sources" :key="src.source_id" class="md-source-item">
        <span class="md-source-title">{{ src.title }}</span>
        <span class="badge">{{ src.card_count }} 张</span>
      </div>
    </div>
  </div>
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

/* Drop zone */
.drop-zone {
  border: 2px dashed var(--color-hairline-dark);
  border-radius: var(--radius-lg);
  padding: var(--space-xxl);
  text-align: center;
  cursor: pointer;
  transition: border-color var(--transition), background-color var(--transition);
}
.drop-zone:hover,
.drop-zone-active {
  border-color: var(--color-surface-violet);
  background-color: rgba(139, 92, 246, 0.05);
}
.drop-zone-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
}
.drop-zone-file {
  display: flex;
  align-items: center;
  gap: var(--space-lg);
  justify-content: center;
}
.file-name {
  font-weight: 540;
  color: var(--color-on-primary);
  font-size: var(--text-body-md);
}

/* Format hint */
.md-format-hint {
  background-color: var(--color-primary-deep);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-md);
  padding: var(--space-lg);
}
.format-example {
  font-family: monospace;
  font-size: 12px;
  color: var(--color-on-dark-mute);
  margin: 0;
  line-height: 1.6;
  white-space: pre-wrap;
}

/* Result */
.import-result-title {
  font-size: var(--text-display-lg);
  font-weight: 540;
  letter-spacing: -0.63px;
}
.md-result-stats {
  display: flex;
  gap: var(--space-xl);
}
.md-stat {
  display: flex;
  align-items: baseline;
  gap: var(--space-xs);
}
.md-stat-num {
  font-size: var(--text-display-md);
  font-weight: 640;
}
.md-stat-label {
  font-size: var(--text-caption);
  color: var(--color-on-dark-mute);
}

/* Sources list */
.md-sources-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  max-height: 55vh;
  overflow-y: auto;
  padding-right: var(--space-xs);
}
.md-source-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--color-primary-deep);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-md);
  padding: var(--space-md) var(--space-lg);
  transition: background-color var(--transition);
}
.md-source-item:hover {
  background-color: var(--color-primary-mid);
}
.md-source-title {
  font-size: var(--text-body-md);
  color: var(--color-on-primary);
  font-weight: 460;
}

.mt-xs { margin-top: var(--space-xs); }
.mt-sm { margin-top: var(--space-sm); }
</style>
