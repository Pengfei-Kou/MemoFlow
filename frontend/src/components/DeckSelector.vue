<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useDeckStore } from '../stores/deck'

const deckStore = useDeckStore()

const modelValue = defineModel<number | null>({ default: null })

defineProps<{
  /** 是否显示 "自动分配到 Default Deck" 选项 */
  allowNull?: boolean
  /** 为空时的 placeholder 文字 */
  nullLabel?: string
  /** 是否显示 parser 策略信息 */
  showStrategy?: boolean
}>()
</script>

<template>
  <div class="deck-selector">
    <div class="flex gap-md items-center">
      <select v-model="modelValue" class="form-input" style="flex:1">
        <option :value="null">{{ nullLabel ?? (allowNull ? '— 自动分配到 Default Deck —' : '— 请选择 Deck —') }}</option>
        <option v-for="deck in deckStore.decks" :key="deck.id" :value="deck.id">{{ deck.path }}</option>
      </select>
      <RouterLink to="/decks" class="btn btn-ghost" style="white-space:nowrap; font-size: var(--text-caption)">
        + 新建 Deck
      </RouterLink>
    </div>
    <p v-if="showStrategy && modelValue && deckStore.getDeckById(modelValue)" class="text-xs text-faint mt-xs">
      策略：{{ deckStore.getDeckById(modelValue)?.parser_config?.strategy ?? '—' }}
      &nbsp;·&nbsp;
      顺序：{{ deckStore.getDeckById(modelValue)?.card_order ?? '—' }}
    </p>
  </div>
</template>
