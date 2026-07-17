<script setup lang="ts">
/**
 * 文章列表（卡库·文章标签）：按牌组分组展示全部文章，
 * 带学习进度条；支持 ?deck_id= 过滤（从牌组页点行进入）。
 * 三层结构的中间层浏览入口：牌组 → 文章 → 句子。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchSources, type SourceListItem } from '../api'
import { useDeckStore } from '../stores/deck'
import HubTabs from '../components/HubTabs.vue'

const route = useRoute()
const router = useRouter()
const deckStore = useDeckStore()

const sources = ref<SourceListItem[]>([])
const loading = ref(true)
const error = ref('')

const filterDeckId = computed(() => {
  const q = route.query.deck_id
  return q ? Number(q) : null
})

const filterDeck = computed(() =>
  filterDeckId.value != null ? deckStore.getDeckById(filterDeckId.value) : null
)

/** deck 过滤：含子树（按 path 前缀） */
const filtered = computed(() => {
  const deck = filterDeck.value
  if (!deck) return sources.value
  const ids = new Set(
    deckStore.decks
      .filter(d => d.path === deck.path || d.path.startsWith(deck.path + '/'))
      .map(d => d.id)
  )
  return sources.value.filter(s => s.deck_id != null && ids.has(s.deck_id))
})

/** 按牌组路径分组，分区标题即层级说明 */
const groups = computed(() => {
  const map = new Map<string, SourceListItem[]>()
  for (const s of filtered.value) {
    const path = (s.deck_id ? deckStore.getDeckById(s.deck_id)?.path : null) ?? '未分组'
    if (!map.has(path)) map.set(path, [])
    map.get(path)!.push(s)
  }
  return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]))
})

function progress(s: SourceListItem): number {
  return s.block_count > 0 ? Math.round((s.learned_count / s.block_count) * 100) : 0
}

onMounted(async () => {
  if (deckStore.decks.length === 0) await deckStore.loadDecks()
  try {
    sources.value = await fetchSources()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page-container">
    <div class="hub-header">
      <HubTabs />
    </div>

    <!-- deck 过滤 chip -->
    <div v-if="filterDeck" class="articles-filter mt-lg">
      <span class="badge">🗂️ {{ filterDeck.path }}</span>
      <button class="articles-filter-clear" title="清除过滤" @click="router.replace('/articles')">✕</button>
    </div>

    <div v-if="loading" class="flex items-center gap-md mt-xl">
      <div class="spinner"></div><span class="text-mute">加载中...</span>
    </div>
    <p v-else-if="error" class="text-sm mt-xl" style="color:#e57373">⚠️ {{ error }}</p>
    <p v-else-if="filtered.length === 0" class="text-mute text-sm mt-xl">
      还没有文章 — 去「导入」标签添加内容吧 🚀
    </p>

    <template v-else>
      <section v-for="[path, list] in groups" :key="path" class="articles-group mt-xl">
        <h2 class="articles-group-title text-xs text-faint">🗂️ {{ path }}</h2>
        <div
          v-for="s in list"
          :key="s.id"
          class="article-item"
          @click="router.push(`/sources/${s.id}`)"
        >
          <div class="article-item-body">
            <p class="article-title">{{ s.title }}</p>
            <div class="article-progress-row">
              <span class="article-progress-track">
                <span class="article-progress-fill" :style="{ width: progress(s) + '%' }"></span>
              </span>
              <span class="text-xs text-faint article-count">{{ s.learned_count }}/{{ s.block_count }}</span>
            </div>
          </div>
          <span class="text-faint article-chevron">›</span>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.articles-filter {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.articles-filter-clear {
  background: transparent;
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-full);
  color: var(--color-on-dark-mute);
  cursor: pointer;
  width: 24px;
  height: 24px;
  line-height: 1;
}

.articles-group-title {
  text-transform: none;
  letter-spacing: 0.04em;
  margin-bottom: var(--space-sm);
}

.article-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md) var(--space-lg);
  margin-bottom: var(--space-sm);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-md);
  background-color: var(--color-primary-mid);
  cursor: pointer;
  transition: border-color 0.2s ease;
}
.article-item:hover {
  border-color: var(--color-surface-violet);
}

.article-item-body {
  flex: 1;
  min-width: 0;
}

.article-title {
  font-weight: 540;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.article-progress-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-top: var(--space-xs);
}

.article-progress-track {
  flex: 1;
  height: 4px;
  border-radius: var(--radius-full);
  background-color: var(--color-primary-deep);
  overflow: hidden;
}

.article-progress-fill {
  display: block;
  height: 100%;
  border-radius: var(--radius-full);
  background-color: var(--color-surface-violet);
}

.article-count {
  flex-shrink: 0;
}

.article-chevron {
  font-size: var(--text-body-lg);
  flex-shrink: 0;
}
</style>
