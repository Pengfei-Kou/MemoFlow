/**
 * Pinia store：管理统计数据
 * 提供全局共享的 stats 数据，避免 App.vue 和 StatsView 重复 fetch
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { fetchStats, fetchTodaySummary, type Stats, type TodaySummary } from '../api'
import { useDeckStore } from './deck'

export const useStatsStore = defineStore('stats', () => {
  const stats = ref<Stats | null>(null)
  const today = ref<TodaySummary | null>(null)
  const loading = ref(false)
  const error = ref('')

  /** 今日剩余任务量（全局，不随 Deck 筛选变），底部导航角标用 */
  const todayRemaining = computed(() => today.value?.remaining ?? 0)

  async function load() {
    const deckStore = useDeckStore()
    loading.value = true
    error.value = ''
    try {
      stats.value = await fetchStats(deckStore.selectedDeckId)
      today.value = await fetchTodaySummary(null)
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

  return { stats, today, todayRemaining, loading, error, load, invalidate }
})
