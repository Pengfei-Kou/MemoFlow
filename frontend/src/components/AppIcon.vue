<script setup lang="ts">
/**
 * 统一线条图标（与底部导航/侧栏同一套视觉语言）：
 * stroke=currentColor、1.8 线宽，替代散落各处风格不一的 emoji。
 */
withDefaults(defineProps<{ name: keyof typeof PATHS; size?: number }>(), { size: 14 })

const PATHS = {
  /** 书本：来源/卡片语境（与导航"卡库"同形） */
  book: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
  /** 文件夹：牌组/范围语境 */
  folder: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
  /** 文档：文章语境 */
  doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
  /** 喇叭：朗读 */
  speaker: '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>',
  /** 铅笔：编辑 */
  pencil: '<path d="M17 3a2.83 2.83 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
  /** 左箭头：返回/上一句 */
  'arrow-left': '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
  /** 循环：重学 */
  refresh: '<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>',
} as const
</script>

<template>
  <svg
    class="app-icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    v-html="PATHS[name]"
  />
</template>

<style scoped>
.app-icon {
  flex-shrink: 0;
  vertical-align: -2px;
}
</style>
