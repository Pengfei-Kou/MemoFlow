<script setup lang="ts">
import { ref } from 'vue'
import { login } from '../api'

const username = ref('')
const password = ref('')
const remember = ref(true)
const error = ref('')
const submitting = ref(false)

async function submit() {
  if (!username.value || !password.value || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    await login(username.value, password.value, remember.value)
    // 整页跳转：让所有 store 带着新会话重新初始化
    window.location.href = '/'
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '登录失败'
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <form class="login-card card" @submit.prevent="submit">
      <div class="login-logo">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--color-surface-violet)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M2 12l10-6 10 6-10 6Z" />
          <path d="M2 17l10 6 10-6" />
          <path d="M2 7l10 6 10-6" />
        </svg>
        <span class="login-logo-text">MemoFlow</span>
      </div>

      <div class="login-field">
        <label class="login-label" for="login-username">用户名</label>
        <input
          id="login-username"
          v-model="username"
          class="form-input"
          type="text"
          autocomplete="username"
          autocapitalize="none"
          autofocus
        />
      </div>

      <div class="login-field">
        <label class="login-label" for="login-password">密码</label>
        <input
          id="login-password"
          v-model="password"
          class="form-input"
          type="password"
          autocomplete="current-password"
        />
      </div>

      <label class="login-remember">
        <input v-model="remember" type="checkbox" />
        <span>记住我（90 天免登录）</span>
      </label>

      <p v-if="error" class="login-error">⚠️ {{ error }}</p>

      <button class="btn btn-pill login-submit" type="submit" :disabled="submitting">
        {{ submitting ? '登录中…' : '登录' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-xl);
  padding-top: calc(var(--space-xl) + env(safe-area-inset-top));
  background-color: var(--color-primary);
}

.login-card {
  width: min(380px, 100%);
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
  background-color: var(--color-primary-mid);
  border-color: var(--color-hairline-dark);
  padding: var(--space-xxl);
}

.login-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  margin-bottom: var(--space-lg);
}

.login-logo-text {
  font-size: var(--text-display-md);
  font-weight: 540;
  letter-spacing: -0.3px;
  color: var(--color-on-primary);
}

.login-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.login-label {
  font-size: var(--text-micro);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-on-dark-mute);
}

.login-remember {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--text-caption);
  color: var(--color-on-dark-mute);
  cursor: pointer;
  user-select: none;
}

.login-remember input {
  accent-color: var(--color-surface-violet);
}

.login-error {
  font-size: var(--text-caption);
  color: #e57373;
}

.login-submit {
  justify-content: center;
  min-height: 44px;
  margin-top: var(--space-sm);
}
</style>
