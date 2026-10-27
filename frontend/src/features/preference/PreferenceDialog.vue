<template>
  <div v-if="modelValue" class="pref-overlay" @click.self="onOverlayClick">
    <div class="pref-card">
      <header class="pref-card__head">
        <span class="pref-card__eyebrow">个性化推荐</span>
        <h2 class="pref-card__title">选择你感兴趣的栏目</h2>
        <p class="pref-card__subtitle">可多选，我们将据此为你推荐更贴合的内容</p>
      </header>

      <div class="pref-grid">
        <button
          v-for="cat in categories"
          :key="cat.id"
          type="button"
          class="pref-chip"
          :class="{ 'pref-chip--on': isSelected(cat.id) }"
          @click="toggle(cat.id)"
        >
          <span class="pref-chip__mark" :aria-hidden="true">{{ (cat.name || '类').slice(0, 1) }}</span>
          <span class="pref-chip__name">{{ cat.name }}</span>
          <span class="pref-chip__check" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="3">
              <path d="m4.5 12.5 5 5 10-11" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </span>
        </button>
      </div>

      <footer class="pref-card__foot">
        <button type="button" class="pref-btn pref-btn--ghost" @click="skip">暂不设置</button>
        <button
          type="button"
          class="pref-btn pref-btn--primary"
          :disabled="saving || selected.length === 0"
          @click="save"
        >
          {{ saving ? '保存中…' : selected.length ? `保存偏好（${selected.length}）` : '请选择栏目' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { preferenceApi } from '../../api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  categories: { type: Array, default: () => [] },
  initialIds: { type: Array, default: () => [] }, // 已选栏目ID，打开时回显
})

const emit = defineEmits(['update:modelValue', 'saved', 'skipped'])

const selected = ref([])
const saving = ref(false)

// 每次打开弹窗时，用已存偏好回显选中状态
watch(
  () => props.modelValue,
  (open) => {
    if (open) selected.value = [...(props.initialIds || [])]
  },
)

function isSelected(id) {
  return selected.value.includes(id)
}

function toggle(id) {
  const i = selected.value.indexOf(id)
  if (i >= 0) selected.value.splice(i, 1)
  else selected.value.push(id)
}

async function save() {
  if (!selected.value.length || saving.value) return
  saving.value = true
  try {
    await preferenceApi.save(selected.value)
    ElMessage.success('偏好已保存，推荐将更贴合你的兴趣')
    emit('update:modelValue', false)
    emit('saved', [...selected.value])
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    saving.value = false
  }
}

function skip() {
  emit('update:modelValue', false)
  emit('skipped')
}

function onOverlayClick() {
  // 点击遮罩不关闭，避免误触；仅支持显式操作
}
</script>

<style scoped>
/* 兴趣偏好选择弹窗：多选卡片栅格 + 渐变选中态，编辑刊式艺术感 */
.pref-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  place-items: center;
  padding: var(--space-5);
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(6px);
  animation: pref-fade var(--dur-base) var(--ease-out);
}

.pref-card {
  width: 100%;
  max-width: 560px;
  background: var(--color-paper);
  border: var(--rule) solid var(--color-rule);
  border-radius: var(--radius-lg, 16px);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.18);
  padding: var(--space-6);
  animation: pref-rise var(--dur-base) var(--ease-out);
}

.pref-card__head {
  text-align: center;
  margin-bottom: var(--space-5);
}

.pref-card__eyebrow {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--color-accent);
  background: var(--color-primary-soft);
  padding: 4px 12px;
  border-radius: 999px;
  margin-bottom: 10px;
}

.pref-card__title {
  font-family: var(--font-heading);
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--color-ink);
  margin: 0 0 var(--space-1);
}

.pref-card__subtitle {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--color-ink-2);
}

/* 栏目栅格：每行5个，窄屏降为2列 */
.pref-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}

.pref-chip {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 14px 6px 10px;
  border: var(--rule) solid var(--color-rule);
  border-radius: var(--radius-md, 12px);
  background: linear-gradient(180deg, var(--color-paper-2), var(--color-paper));
  color: var(--color-ink-2);
  cursor: pointer;
  transition:
    transform var(--dur-base) var(--ease-out),
    border-color var(--dur-base) var(--ease-out),
    box-shadow var(--dur-base) var(--ease-out),
    background var(--dur-base) var(--ease-out),
    color var(--dur-base) var(--ease-out);
}

.pref-chip:hover {
  transform: translateY(-2px);
  border-color: var(--color-accent);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.14);
}

/* 每个栏目一个淡雅色相，营造错落的编辑刊式节奏 */
.pref-chip:nth-child(5n + 1) .pref-chip__mark { background: #eef2ff; color: #4338ca; }
.pref-chip:nth-child(5n + 2) .pref-chip__mark { background: #ecfdf5; color: #047857; }
.pref-chip:nth-child(5n + 3) .pref-chip__mark { background: #fff7ed; color: #c2410c; }
.pref-chip:nth-child(5n + 4) .pref-chip__mark { background: #fdf2f8; color: #be185d; }
.pref-chip:nth-child(5n + 5) .pref-chip__mark { background: #f0f9ff; color: #0369a1; }

.pref-chip__mark {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 700;
  transition: background var(--dur-base) var(--ease-out), color var(--dur-base) var(--ease-out);
}

.pref-chip__name {
  font-size: 13px;
  font-weight: 500;
}

.pref-chip__check {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--color-accent);
  color: #fff;
  opacity: 0;
  transform: scale(0.5);
  transition: opacity var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-out);
}

.pref-chip--on {
  border-color: var(--color-accent);
  background: linear-gradient(160deg, var(--color-accent), var(--color-primary-dark));
  color: #fff;
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.25);
}

.pref-chip--on .pref-chip__mark {
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
}

.pref-chip--on .pref-chip__name {
  color: #fff;
}

.pref-chip--on .pref-chip__check {
  opacity: 1;
  transform: scale(1);
}

.pref-card__foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

.pref-btn {
  min-height: var(--size-touch);
  padding: 0 var(--space-5);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: background var(--dur-base) var(--ease-out), color var(--dur-base) var(--ease-out);
}

.pref-btn--ghost {
  border: none;
  background: none;
  color: var(--color-ink-3);
}

.pref-btn--ghost:hover {
  color: var(--color-ink-2);
}

.pref-btn--primary {
  border: none;
  background: var(--color-accent);
  color: #fff;
}

.pref-btn--primary:hover:not(:disabled) {
  background: var(--color-primary-dark);
}

.pref-btn--primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@keyframes pref-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes pref-rise {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@media (max-width: 640px) {
  .pref-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .pref-card {
    padding: var(--space-5);
  }
}
</style>
