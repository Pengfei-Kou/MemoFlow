/**
 * Pinia store：管理当前选中的 Deck
 * 供复习页、统计页、导入页共享"当前复习 Deck"状态
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchDecks, type Deck } from '../api'

export const useDeckStore = defineStore('deck', () => {
  const decks = ref<Deck[]>([])
  const selectedDeckId = ref<number | null>(null)
  const loading = ref(false)

  async function loadDecks() {
    loading.value = true
    try {
      decks.value = await fetchDecks()
    } catch {
      // Silent fail — app still works without deck filter
    } finally {
      loading.value = false
    }
  }

  function selectDeck(id: number | null) {
    selectedDeckId.value = id
  }

  function getDeckById(id: number | null): Deck | null {
    if (id == null) return null
    return decks.value.find(d => d.id === id) ?? null
  }

  return { decks, selectedDeckId, loading, loadDecks, selectDeck, getDeckById }
})
