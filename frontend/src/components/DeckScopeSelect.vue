<script setup lang="ts">
/**
 * 全局"复习范围"选择器（绑定 deckStore）。
 * 窄屏下侧边栏收成图标栏放不下 select，由各页面顶部挂载本组件补位；
 * 桌面端由 .mobile-only 隐藏，避免与侧边栏选择器重复。
 */
import { useDeckStore } from '../stores/deck'

const deckStore = useDeckStore()

function onChange(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  deckStore.selectDeck(v === '' ? null : Number(v))
}
</script>

<template>
  <select
    class="deck-scope-select mobile-only"
    :value="deckStore.selectedDeckId ?? ''"
    @change="onChange"
    aria-label="复习范围"
  >
    <option value="">🗂️ 全部 Deck</option>
    <option v-for="deck in deckStore.decks" :key="deck.id" :value="deck.id">
      🗂️ {{ deck.path }}
    </option>
  </select>
</template>

<style scoped>
.deck-scope-select {
  background-color: var(--color-primary-deep);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-sm);
  color: var(--color-on-primary);
  font-family: var(--font-sans);
  font-size: var(--text-caption);
  padding: 8px 10px;
  max-width: 60vw;
  outline: none;
}
</style>
