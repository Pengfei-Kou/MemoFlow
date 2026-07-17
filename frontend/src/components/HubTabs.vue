<script setup lang="ts">
/**
 * 卡库页顶部标签导航：卡片库 / 牌组 / 导入 三页共用，
 * 替代各页原来的 h1 标题（激活标签即页面身份）。
 */
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()

const tabs = [
  { to: '/library', label: '卡片库' },
  { to: '/decks', label: '牌组' },
  { to: '/import', label: '导入' },
]
</script>

<template>
  <nav class="hub-tabs">
    <RouterLink
      v-for="t in tabs"
      :key="t.to"
      :to="t.to"
      class="hub-tab"
      :class="{ active: route.path === t.to }"
    >{{ t.label }}</RouterLink>
  </nav>
</template>

<style scoped>
.hub-tabs {
  display: inline-flex;
  gap: var(--space-xs);
  padding: 3px;
  background-color: var(--color-primary-mid);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-full);
}

.hub-tab {
  padding: 6px 16px;
  border-radius: var(--radius-full);
  color: var(--color-on-dark-mute);
  text-decoration: none;
  font-size: var(--text-caption);
  font-weight: 540;
  white-space: nowrap;
  transition: color 0.15s ease, background-color 0.15s ease;
}

.hub-tab.active {
  background-color: var(--color-surface-violet);
  color: var(--color-primary);
}
</style>
