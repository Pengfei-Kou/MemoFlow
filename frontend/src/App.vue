<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { computed, onMounted, watch } from 'vue'
import { useDeckStore } from './stores/deck'
import { useStatsStore } from './stores/stats'
import { logout } from './api'
import MobileTabBar from './components/MobileTabBar.vue'

const route = useRoute()
const deckStore = useDeckStore()
const statsStore = useStatsStore()

// 登录页：无导航、不预载数据（未登录时预载只会撞 401）
const isLoginPage = computed(() => route.path === '/login')

onMounted(async () => {
  if (window.location.pathname === '/login') return
  await deckStore.loadDecks()
  statsStore.load()
})

// Re-load stats when the selected Deck changes
watch(() => deckStore.selectedDeckId, () => statsStore.load())

const selectedDeck = computed(() => deckStore.getDeckById(deckStore.selectedDeckId))

/** 卡库 = 卡片库/牌组/导入 三页 + 文章详情 */
const hubActive = computed(() =>
  ['/library', '/decks', '/import'].includes(route.path) || route.path.startsWith('/sources/')
)

async function handleLogout() {
  try { await logout() } catch { /* cookie 已清即达目的 */ }
  window.location.href = '/login'
}
</script>

<template>
  <aside class="sidebar" v-if="!isLoginPage">
    <div class="sidebar-logo">
      <svg class="sidebar-logo-icon" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="var(--color-surface-violet)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M2 12l10-6 10 6-10 6Z" />
        <path d="M2 17l10 6 10-6" />
        <path d="M2 7l10 6 10-6" />
      </svg>
      <span class="sidebar-logo-text">MemoFlow</span>
    </div>

    <!-- Deck 选择器 -->
    <div class="sidebar-deck-selector">
      <label class="sidebar-deck-label">复习范围</label>
      <select
        id="sidebar-deck-select"
        class="sidebar-deck-select"
        :value="deckStore.selectedDeckId ?? ''"
        @change="(e) => deckStore.selectDeck((e.target as HTMLSelectElement).value === '' ? null : Number((e.target as HTMLSelectElement).value))"
      >
        <option value="">全部 Deck</option>
        <option
          v-for="deck in deckStore.decks"
          :key="deck.id"
          :value="deck.id"
        >{{ deck.path }}</option>
      </select>
      <p v-if="selectedDeck" class="sidebar-deck-hint">{{ selectedDeck.path }}</p>
    </div>

    <nav class="sidebar-nav">
      <RouterLink
        to="/"
        class="sidebar-nav-item"
        :class="{ active: route.path === '/' }"
      >
        <!-- Review icon -->
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <rect x="3" y="8" width="14" height="12" rx="2"/>
          <path d="M7 4h12a2 2 0 0 1 2 2v10"/>
          <path d="M7 14h6"/>
        </svg>
        <span>复习</span>
      </RouterLink>

      <RouterLink
        to="/library"
        class="sidebar-nav-item"
        :class="{ active: hubActive }"
      >
        <!-- 卡库 icon -->
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
        </svg>
        <span>卡库</span>
      </RouterLink>

      <RouterLink
        to="/stats"
        class="sidebar-nav-item"
        :class="{ active: route.path === '/stats' }"
      >
        <!-- Stats icon -->
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <line x1="18" y1="20" x2="18" y2="10"/>
          <line x1="12" y1="20" x2="12" y2="4"/>
          <line x1="6" y1="20" x2="6" y2="14"/>
        </svg>
        <span>统计</span>
      </RouterLink>

      <RouterLink
        to="/settings"
        class="sidebar-nav-item"
        :class="{ active: route.path === '/settings' }"
      >
        <!-- Settings icon -->
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>
          <line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>
          <line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>
          <line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/>
          <line x1="17" y1="16" x2="23" y2="16"/>
        </svg>
        <span>设置</span>
      </RouterLink>
    </nav>

    <div class="sidebar-footer" v-if="statsStore.stats">
      <div class="sidebar-stats-mini">
        <div>总卡片 <strong style="color: var(--color-surface-violet)">{{ statsStore.stats.total }}</strong></div>
        <div>今日到期 <strong style="color: var(--color-surface-violet)">{{ statsStore.stats.due_today }}</strong></div>
      </div>
      <button class="sidebar-logout" @click="handleLogout">退出登录</button>
    </div>
  </aside>

  <main class="main-content" :class="{ 'full-bleed': isLoginPage }">
    <Transition name="fade" mode="out-in">
      <RouterView :key="route.path" />
    </Transition>
  </main>

  <MobileTabBar v-if="!isLoginPage" />
</template>

<style scoped>
.sidebar-deck-selector {
  padding: var(--space-md) var(--space-xl);
  border-bottom: 1px solid var(--color-hairline-dark);
  margin-bottom: var(--space-sm);
}

.sidebar-deck-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--color-on-dark-mute);
  display: block;
  margin-bottom: var(--space-xs);
}

.sidebar-deck-select {
  width: 100%;
  background-color: var(--color-primary-deep);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-sm);
  color: var(--color-on-primary);
  font-family: var(--font-sans);
  font-size: var(--text-caption);
  padding: 4px 8px;
  cursor: pointer;
  outline: none;
  transition: border-color var(--transition);
}

.sidebar-deck-select:focus,
.sidebar-deck-select:hover {
  border-color: var(--color-surface-violet);
}

.sidebar-deck-hint {
  font-size: 10px;
  color: var(--color-surface-violet);
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-logout {
  margin-top: var(--space-md);
  background: transparent;
  border: none;
  color: var(--color-on-dark-faint);
  font-size: var(--text-micro);
  cursor: pointer;
  padding: 0;
  text-align: left;
  transition: color 0.2s ease;
}
.sidebar-logout:hover {
  color: #e57373;
}

.main-content.full-bleed {
  margin-left: 0;
}
</style>
