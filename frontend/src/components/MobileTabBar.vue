<script setup lang="ts">
/**
 * 移动端底部 Tab 导航（≤768px 显示，桌面端由左侧边栏承担）。
 * 图标与侧边栏保持同一套 SVG；复习 Tab 带今日剩余角标。
 */
import { computed, onMounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useStatsStore } from '../stores/stats'

const route = useRoute()
const statsStore = useStatsStore()

const badge = computed(() => {
  const n = statsStore.todayRemaining
  return n > 99 ? '99+' : n > 0 ? String(n) : ''
})

onMounted(() => {
  if (!statsStore.today) statsStore.load()
})
</script>

<template>
  <nav class="mobile-tabbar">
    <RouterLink to="/" class="tab-item" :class="{ active: route.path === '/' }">
      <span class="tab-icon-wrap">
        <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <rect x="3" y="8" width="14" height="12" rx="2"/>
          <path d="M7 4h12a2 2 0 0 1 2 2v10"/>
          <path d="M7 14h6"/>
        </svg>
        <span v-if="badge" class="tab-badge">{{ badge }}</span>
      </span>
      <span>复习</span>
    </RouterLink>

    <RouterLink to="/import" class="tab-item" :class="{ active: route.path === '/import' }">
      <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="17 8 12 3 7 8"/>
        <line x1="12" y1="3" x2="12" y2="15"/>
      </svg>
      <span>导入</span>
    </RouterLink>

    <RouterLink to="/decks" class="tab-item" :class="{ active: route.path === '/decks' }">
      <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
      </svg>
      <span>牌组</span>
    </RouterLink>

    <RouterLink to="/library" class="tab-item" :class="{ active: route.path === '/library' }">
      <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
      </svg>
      <span>卡片库</span>
    </RouterLink>

    <RouterLink to="/stats" class="tab-item" :class="{ active: route.path === '/stats' }">
      <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <line x1="18" y1="20" x2="18" y2="10"/>
        <line x1="12" y1="20" x2="12" y2="4"/>
        <line x1="6" y1="20" x2="6" y2="14"/>
      </svg>
      <span>统计</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
.mobile-tabbar {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: calc(var(--mobile-nav-h) + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  background-color: var(--color-primary-deep);
  border-top: 1px solid var(--color-hairline-dark);
  z-index: 100;
}

@media (max-width: 768px) {
  .mobile-tabbar {
    display: flex;
  }
}

.tab-item {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  color: var(--color-on-dark-faint);
  text-decoration: none;
  font-size: 10px;
  letter-spacing: 0.02em;
  transition: color 0.2s ease;
  -webkit-tap-highlight-color: transparent;
}

.tab-item.active {
  color: var(--color-surface-violet);
}

/* 选中态指示条：图标上方 2px 短横线 */
.tab-item.active::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 24px;
  height: 2px;
  border-radius: 0 0 2px 2px;
  background-color: var(--color-surface-violet);
}

.tab-icon {
  width: 22px;
  height: 22px;
}

.tab-icon-wrap {
  position: relative;
  display: inline-flex;
}

/* 今日剩余角标 */
.tab-badge {
  position: absolute;
  top: -4px;
  right: -10px;
  min-width: 15px;
  height: 15px;
  padding: 0 4px;
  border-radius: var(--radius-full);
  background-color: var(--color-surface-violet);
  color: var(--color-primary-deep);
  font-size: 9px;
  font-weight: 640;
  line-height: 15px;
  text-align: center;
}
</style>
