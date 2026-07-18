<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { fetchReviewHistory, type ReviewHistoryDay } from '../api'
import { useDeckStore } from '../stores/deck'
import DeckScopeSelect from '../components/DeckScopeSelect.vue'
import AppIcon from '../components/AppIcon.vue'
import { useStatsStore } from '../stores/stats'

const deckStore = useDeckStore()
const statsStore = useStatsStore()
const history = ref<ReviewHistoryDay[]>([])
const loading = ref(false)
const error   = ref('')

// 热力图 tooltip
const tooltip = ref<{ text: string; x: number; y: number } | null>(null)

async function load() {
  loading.value = true
  error.value   = ''
  try {
    history.value = await fetchReviewHistory(90, deckStore.selectedDeckId)
    await statsStore.load()
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

// Re-load when the selected Deck changes
watch(() => deckStore.selectedDeckId, load)

const currentScopeLabel = computed(() => {
  const deck = deckStore.getDeckById(deckStore.selectedDeckId)
  return deck ? deck.path : '全部 Deck'
})

// ── 热力图计算 ──────────────────────────────────────────────
// 按 7 天一列切分，用于渲染网格
const heatmapWeeks = computed<ReviewHistoryDay[][]>(() => {
  if (!history.value.length) return []
  const weeks: ReviewHistoryDay[][] = []
  let week: ReviewHistoryDay[] = []
  for (const day of history.value) {
    week.push(day)
    if (week.length === 7) {
      weeks.push(week)
      week = []
    }
  }
  if (week.length) weeks.push(week)
  return weeks
})

const maxCount = computed(() => Math.max(1, ...history.value.map(d => d.count)))

// 总复习次数（过去 90 天）
const totalReviews = computed(() => history.value.reduce((s, d) => s + d.count, 0))

// 活跃天数
const activeDays = computed(() => history.value.filter(d => d.count > 0).length)

function heatColor(count: number): string {
  if (count === 0) return 'var(--heatmap-empty)'
  const ratio = count / maxCount.value
  if (ratio < 0.2)  return 'var(--heatmap-1)'
  if (ratio < 0.4)  return 'var(--heatmap-2)'
  if (ratio < 0.7)  return 'var(--heatmap-3)'
  if (ratio < 0.9)  return 'var(--heatmap-4)'
  return 'var(--heatmap-5)'
}

function showTooltip(e: MouseEvent, day: ReviewHistoryDay) {
  const cellEl = e.target as HTMLElement
  const scrollEl = cellEl.closest('.heatmap-scroll') as HTMLElement
  if (!scrollEl) return
  const cellRect = cellEl.getBoundingClientRect()
  const scrollRect = scrollEl.getBoundingClientRect()
  tooltip.value = {
    text: `${day.date}  ${day.count} 次`,
    x: cellRect.left - scrollRect.left + cellRect.width / 2,
    y: cellRect.top - scrollRect.top - 6,
  }
}

function hideTooltip() {
  tooltip.value = null
}

// 月份标签（每个月只显示一次，标注在热力图顶部）
const monthLabels = computed(() => {
  const labels: { label: string; weekIndex: number }[] = []
  let lastMonth = ''
  heatmapWeeks.value.forEach((week, wi) => {
    const firstDay = week[0]
    if (!firstDay) return
    const month = firstDay.date.slice(0, 7) // "YYYY-MM"
    if (month !== lastMonth) {
      labels.push({
        label: new Date(firstDay.date + 'T00:00:00').toLocaleDateString('zh-CN', { month: 'short' }),
        weekIndex: wi,
      })
      lastMonth = month
    }
  })
  return labels
})

onMounted(load)
</script>

<template>
  <div class="page-container">
    <div class="flex items-center justify-between">
      <h1 class="page-title">学习统计</h1>
      <DeckScopeSelect />
      <span class="badge desktop-only" style="font-size: var(--text-caption)"><AppIcon name="folder" :size="12" /> {{ currentScopeLabel }}</span>
    </div>

    <div v-if="loading" class="flex items-center gap-md mt-xl">
      <div class="spinner"></div>
      <span class="text-mute text-sm">加载中...</span>
    </div>

    <p v-else-if="error" class="text-sm mt-xl" style="color:#e57373">⚠️ {{ error }}</p>

    <template v-else-if="statsStore.stats">
      <!-- Stat cards -->
      <div class="stat-grid">
        <div class="stat-card">
          <span class="stat-label">总卡片</span>
          <span class="stat-value">{{ statsStore.stats.total }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">已掌握</span>
          <span class="stat-value teal">{{ statsStore.stats.mastered }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">学习中</span>
          <span class="stat-value accent">{{ statsStore.stats.learning }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">新卡片</span>
          <span class="stat-value">{{ statsStore.stats.new }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">今日到期</span>
          <span class="stat-value warm">{{ statsStore.stats.due_today }}</span>
        </div>
      </div>

      <!-- Progress section -->
      <div class="card mt-xxl" style="background: var(--color-primary-mid);">
        <p class="stat-label" style="margin-bottom: var(--space-lg)">掌握进度</p>
        <div class="progress-bar" style="height: 8px;">
          <div
            class="progress-bar-fill"
            :style="{ width: statsStore.stats.total > 0 ? (statsStore.stats.mastered / statsStore.stats.total * 100) + '%' : '0%' }"
          />
        </div>
        <div class="flex justify-between mt-lg">
          <span class="text-faint text-sm">0</span>
          <span class="text-violet text-sm">
            {{ statsStore.stats.total > 0 ? Math.round(statsStore.stats.mastered / statsStore.stats.total * 100) : 0 }}% 已掌握
          </span>
          <span class="text-faint text-sm">{{ statsStore.stats.total }}</span>
        </div>
      </div>

      <!-- 热力图 -->
      <div class="card mt-xxl heatmap-card" style="background: var(--color-primary-mid);">
        <div class="flex items-center justify-between" style="margin-bottom: var(--space-lg)">
          <p class="stat-label">
            复习热力图
            <span class="text-faint" style="font-weight:400; font-size: var(--text-caption)">过去 90 天</span>
          </p>
          <div class="flex gap-xl text-xs text-faint">
            <span>共 <strong class="text-violet">{{ totalReviews }}</strong> 次</span>
            <span>活跃 <strong class="text-violet">{{ activeDays }}</strong> 天</span>
          </div>
        </div>

        <div class="heatmap-scroll">
          <!-- 月份标签 -->
          <div class="heatmap-months">
            <div
              v-for="m in monthLabels"
              :key="m.label + m.weekIndex"
              class="heatmap-month-label"
              :style="{ left: m.weekIndex * 14 + 'px' }"
            >{{ m.label }}</div>
          </div>

          <!-- 周格子 -->
          <div class="heatmap-grid">
            <div v-for="(week, wi) in heatmapWeeks" :key="wi" class="heatmap-col">
              <div
                v-for="day in week"
                :key="day.date"
                class="heatmap-cell"
                :style="{ background: heatColor(day.count) }"
                @mouseenter="showTooltip($event, day)"
                @mouseleave="hideTooltip"
              />
            </div>
          </div>

          <!-- Tooltip -->
          <Transition name="fade">
            <div
              v-if="tooltip"
              class="heatmap-tooltip"
              :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
            >{{ tooltip.text }}</div>
          </Transition>
        </div>

        <!-- 图例 -->
        <div class="heatmap-legend">
          <span class="text-xs text-faint">少</span>
          <div class="heatmap-cell" style="background: var(--heatmap-empty)" />
          <div class="heatmap-cell" style="background: var(--heatmap-1)" />
          <div class="heatmap-cell" style="background: var(--heatmap-2)" />
          <div class="heatmap-cell" style="background: var(--heatmap-3)" />
          <div class="heatmap-cell" style="background: var(--heatmap-4)" />
          <div class="heatmap-cell" style="background: var(--heatmap-5)" />
          <span class="text-xs text-faint">多</span>
        </div>
      </div>

      <!-- 文章列表已迁至 卡库 › 文章 -->
      <p class="text-faint text-xs mt-xxl" style="text-align:center">
        文章与卡片管理在 <RouterLink to="/articles" class="stats-hub-link">卡库</RouterLink> 中
      </p>
    </template>
  </div>
</template>

<style scoped>
.stats-section-title {
  font-size: var(--text-heading-lg);
  font-weight: 540;
  letter-spacing: -0.4px;
  color: var(--color-on-primary);
}

.stats-hub-link {
  color: var(--color-surface-violet);
  text-decoration: none;
}

/* ── 热力图 ─────────────────────────────────── */
.heatmap-card {
  overflow: hidden;
}

.heatmap-scroll {
  overflow-x: auto;
  padding-bottom: var(--space-md);
  position: relative;
}

.heatmap-months {
  position: relative;
  height: 18px;
  margin-bottom: 4px;
  min-width: max-content;
}

.heatmap-month-label {
  position: absolute;
  font-size: 10px;
  color: var(--color-on-dark-mute);
  white-space: nowrap;
}

.heatmap-grid {
  display: flex;
  gap: 2px;
  min-width: max-content;
}

.heatmap-col {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.heatmap-cell {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  cursor: default;
  flex-shrink: 0;
  transition: opacity 0.15s;
}

.heatmap-cell:hover {
  opacity: 0.75;
  outline: 1px solid rgba(255,255,255,0.25);
  outline-offset: 1px;
}

.heatmap-legend {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-top: var(--space-md);
  justify-content: flex-end;
}

.heatmap-tooltip {
  position: absolute;
  transform: translate(-50%, -100%);
  background: var(--color-primary-deep);
  border: 1px solid var(--color-hairline-dark);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  font-size: 11px;
  color: var(--color-on-primary);
  white-space: nowrap;
  pointer-events: none;
  z-index: 20;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.12s;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

</style>
