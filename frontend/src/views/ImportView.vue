<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDeckStore } from '../stores/deck'
import HubTabs from '../components/HubTabs.vue'
import TextImportTab from '../components/TextImportTab.vue'
import UrlImportTab from '../components/UrlImportTab.vue'
import MarkdownImportTab from '../components/MarkdownImportTab.vue'

const deckStore = useDeckStore()

type Tab = 'text' | 'url' | 'markdown'
const activeTab = ref<Tab>('text')

onMounted(async () => {
  if (deckStore.decks.length === 0) {
    await deckStore.loadDecks()
  }
})
</script>

<template>
  <div class="page-container">
    <div class="hub-header">
      <HubTabs />
    </div>

    <!-- Tab 切换 -->
    <div class="import-tabs">
      <button
        id="tab-text"
        class="tab-btn"
        :class="{ active: activeTab === 'text' }"
        @click="activeTab = 'text'"
      >
        📝 粘贴文本
      </button>
      <button
        id="tab-url"
        class="tab-btn"
        :class="{ active: activeTab === 'url' }"
        @click="activeTab = 'url'"
      >
        🌐 URL 导入
      </button>
      <button
        id="tab-markdown"
        class="tab-btn"
        :class="{ active: activeTab === 'markdown' }"
        @click="activeTab = 'markdown'"
      >
        📄 上传 Markdown
      </button>
    </div>

    <TextImportTab v-if="activeTab === 'text'" />
    <UrlImportTab v-else-if="activeTab === 'url'" />
    <MarkdownImportTab v-else />
  </div>
</template>

<style scoped>
.import-tabs {
  display: flex;
  gap: var(--space-sm);
  margin-top: var(--space-xl);
  border-bottom: 1px solid var(--color-hairline-dark);
  padding-bottom: 0;
}

.tab-btn {
  padding: var(--space-md) var(--space-xl);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--color-on-dark-mute);
  font-family: var(--font-sans);
  font-size: var(--text-body-md);
  font-weight: 460;
  cursor: pointer;
  transition: color var(--transition), border-color var(--transition);
  margin-bottom: -1px;
}

.tab-btn:hover {
  color: var(--color-on-primary);
}

.tab-btn.active {
  color: var(--color-surface-violet);
  border-bottom-color: var(--color-surface-violet);
  font-weight: 540;
}
</style>
