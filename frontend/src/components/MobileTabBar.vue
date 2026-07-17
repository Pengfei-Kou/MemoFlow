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

/** 卡库 = 卡片库/牌组/导入 三页 + 文章详情 */
const hubActive = computed(() =>
  ['/library', '/decks', '/import', '/articles'].includes(route.path) || route.path.startsWith('/sources/')
)

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

    <RouterLink to="/library" class="tab-item" :class="{ active: hubActive }">
      <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
      </svg>
      <span>卡库</span>
    </RouterLink>

    <RouterLink to="/stats" class="tab-item" :class="{ active: route.path === '/stats' }">
      <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <line x1="18" y1="20" x2="18" y2="10"/>
        <line x1="12" y1="20" x2="12" y2="4"/>
        <line x1="6" y1="20" x2="6" y2="14"/>
      </svg>
      <span>统计</span>
    </RouterLink>

    <RouterLink to="/settings" class="tab-item" :class="{ active: route.path === '/settings' }">
      <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/>
        <line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/>
        <line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/>
        <line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/>
        <line x1="17" y1="16" x2="23" y2="16"/>
      </svg>
      <span>设置</span>
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
