/**
 * Pinia store：管理统计数据
 * 提供全局共享的 stats 数据，避免 App.vue 和 StatsView 重复 fetch
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchStats, type Stats } from '../api'
import { useDeckStore } from './deck'

export const useStatsStore = defineStore('stats', () => {
  const stats = ref<Stats | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function load() {
    const deckStore = useDeckStore()
    loading.value = true
    error.value = ''
    try {
      stats.value = await fetchStats(deckStore.selectedDeckId)
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  /** 由 ReviewView 等在提交复习后调用，触发数据刷新 */
  function invalidate() {
    load()
  }

  return { stats, loading, error, load, invalidate }
})
