<script setup lang="ts">
/**
 * 卡片快速编辑弹窗（复习页 / 卡片库共用）。
 * LLM 拆错的句子、不准的翻译，当场改，复习进度不受影响。
 */
import { ref, watch } from 'vue'
import { updateBlock, type Block } from '../api'

const props = defineProps<{
  /** 为 null 时不显示 */
  block: Block | null
}>()

const emit = defineEmits<{
  /** 保存成功，携带更新后的卡片 */
  saved: [block: Block]
  cancel: []
}>()

const quiz = ref('')
const content = ref('')
const saving = ref(false)
const error = ref('')

watch(
  () => props.block,
  (b) => {
    if (b) {
      quiz.value = b.quiz
      content.value = b.content
      error.value = ''
    }
  },
  { immediate: true }
)

async function save() {
  if (!props.block || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const updated = await updateBlock(props.block.id, {
      quiz: quiz.value.trim(),
      content: content.value.trim(),
    })
    emit('saved', updated)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="block" class="modal-overlay" @click.self="emit('cancel')">
      <div class="modal-box card edit-box">
        <h3 class="edit-title">编辑卡片 <span class="text-faint text-xs">#{{ block.id }}</span></h3>

        <div class="edit-field">
          <label class="edit-label" for="edit-quiz">提示（问题）</label>
          <textarea id="edit-quiz" v-model="quiz" class="form-input edit-textarea" rows="2"></textarea>
        </div>

        <div class="edit-field">
          <label class="edit-label" for="edit-content">原句（答案）</label>
          <textarea id="edit-content" v-model="content" class="form-input edit-textarea" rows="3"></textarea>
        </div>

        <p v-if="error" class="text-sm" style="color:#e57373">⚠️ {{ error }}</p>

        <div class="edit-actions">
          <button class="btn btn-ghost" @click="emit('cancel')">取消</button>
          <button class="btn btn-pill" :disabled="saving || !quiz.trim() || !content.trim()" @click="save">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: var(--space-lg);
}

.modal-box {
  background-color: var(--color-primary-mid);
  padding: var(--space-xxl);
  max-height: 90vh;
  overflow-y: auto;
}

.edit-box {
  width: min(520px, 100%);
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.edit-title {
  font-size: var(--text-body-lg);
  font-weight: 540;
}

.edit-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.edit-label {
  font-size: var(--text-micro);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-on-dark-mute);
}

.edit-textarea {
  resize: vertical;
  line-height: 1.5;
  font-family: var(--font-sans);
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-md);
}
</style>
