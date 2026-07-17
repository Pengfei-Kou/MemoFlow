<script setup lang="ts">
/**
 * 设置页：复习配额、主题、账号。
 * 从统计页底部独立出来，不用再划过整页统计才能改设置。
 */
import { onMounted, ref } from 'vue'
import {
  fetchReviewSettings, updateReviewSettings, logout, type ReviewSettings,
} from '../api'
import { useStatsStore } from '../stores/stats'

const statsStore = useStatsStore()

// 复习设置（每日新学配额）
const reviewSettings = ref<ReviewSettings | null>(null)
const savingSettings = ref(false)
const settingsMsg = ref('')

async function saveSettings() {
  if (!reviewSettings.value || savingSettings.value) return
  savingSettings.value = true
  settingsMsg.value = ''
  try {
    reviewSettings.value = await updateReviewSettings(reviewSettings.value)
    settingsMsg.value = '✓ 已保存'
    statsStore.invalidate() // 底部导航角标同步刷新
    setTimeout(() => { settingsMsg.value = '' }, 2000)
  } catch {
    settingsMsg.value = '⚠️ 保存失败'
  } finally {
    savingSettings.value = false
  }
}

// 主题切换（本机偏好，存 localStorage）
const theme = ref(localStorage.getItem('mf-theme') ?? 'dark')
function setTheme(t: string) {
  theme.value = t
  localStorage.setItem('mf-theme', t)
  document.documentElement.dataset.theme = t
}

async function handleLogout() {
  try { await logout() } catch { /* cookie 已清即达目的 */ }
  window.location.href = '/login'
}

onMounted(() => {
  fetchReviewSettings().then((s) => { reviewSettings.value = s }).catch(() => {})
})
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">设置 ⚙️</h1>

    <div v-if="reviewSettings" class="card settings-card mt-xl">
      <h2 class="settings-section-title">复习</h2>
      <div class="settings-row mt-lg">
        <span class="text-sm">每日新学上限</span>
        <input
          v-model.number="reviewSettings.new_per_day"
          type="number" min="1" max="500"
          class="form-input settings-num"
        />
        <select v-model="reviewSettings.new_quota_unit" class="form-input settings-unit">
          <option value="articles">篇文章</option>
          <option value="cards">张卡片</option>
        </select>
        <button class="btn btn-pill" :disabled="savingSettings" @click="saveSettings">
          {{ savingSettings ? '保存中…' : '保存' }}
        </button>
      </div>
      <p class="text-faint text-xs mt-sm">
        按篇时配额只管"开新篇"——当天开了头的文章保证能学完。推荐 2 篇/天，清完存量后可调回 1。
      </p>
      <p v-if="settingsMsg" class="text-xs mt-sm" style="color: var(--color-surface-violet)">{{ settingsMsg }}</p>
    </div>

    <div class="card settings-card mt-xl">
      <h2 class="settings-section-title">外观</h2>
      <div class="settings-row mt-lg">
        <span class="text-sm">主题</span>
        <select class="form-input settings-unit" :value="theme" @change="setTheme(($event.target as HTMLSelectElement).value)">
          <option value="dark">深色</option>
          <option value="light">浅色</option>
        </select>
        <span class="text-faint text-xs">本机生效，立即切换</span>
      </div>
    </div>

    <div class="card settings-card mt-xl">
      <h2 class="settings-section-title">账号</h2>
      <button class="btn btn-ghost settings-logout mt-lg" @click="handleLogout">退出登录</button>
    </div>
  </div>
</template>

<style scoped>
.settings-card {
  background-color: var(--color-primary-mid);
}

.settings-section-title {
  font-size: var(--text-body-lg);
  font-weight: 540;
}

.settings-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.settings-num {
  width: 80px;
}

.settings-unit {
  width: auto;
}

.settings-logout {
  color: #e57373;
  border: 1px solid var(--color-hairline-dark);
  padding: var(--space-sm) var(--space-lg);
}
</style>
