<script setup lang="ts">
defineProps<{
  /** 为 null 时不显示 */
  message: string | null
  confirmLabel?: string
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<template>
  <Teleport to="body">
    <div v-if="message" class="modal-overlay" @click.self="emit('cancel')">
      <div class="modal-box card confirm-box">
        <p class="confirm-message">{{ message }}</p>
        <div class="confirm-actions">
          <button class="btn btn-ghost" @click="emit('cancel')">取消</button>
          <button class="btn confirm-danger" @click="emit('confirm')">{{ confirmLabel ?? '删除' }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* 自带 overlay/box 样式：DecksView 的同名类是 scoped 的，Teleport 到 body 后拿不到 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.modal-box {
  background-color: var(--color-primary-mid);
  padding: var(--space-xxl);
  max-height: 90vh;
  overflow-y: auto;
}

.confirm-box {
  max-width: 380px;
  width: calc(100vw - var(--space-xl) * 2);
}
.confirm-message {
  line-height: 1.6;
  margin-bottom: var(--space-xl);
  white-space: pre-line;
}
.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-md);
}
.confirm-danger {
  background-color: transparent;
  border: 1px solid #e57373;
  color: #e57373;
  border-radius: var(--radius-sm);
  padding: 6px 16px;
  transition: all 0.2s ease;
}
.confirm-danger:hover {
  background-color: rgba(229, 115, 115, 0.12);
}
</style>
