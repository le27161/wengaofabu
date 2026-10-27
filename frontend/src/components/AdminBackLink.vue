<template>
  <router-link :to="to" class="admin-back-link">
    <span class="admin-back-link__icon" aria-hidden="true">
      <el-icon><Back /></el-icon>
    </span>
    <span class="admin-back-link__label">{{ label }}</span>
  </router-link>
</template>

<script setup>
import { Back } from '@element-plus/icons-vue'

defineProps({
  to: { type: [String, Object], required: true },
  label: { type: String, required: true },
})
</script>

<style scoped>
.admin-back-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2, 8px);
  min-height: 36px;
  padding: 4px 14px 4px 6px;
  color: var(--color-ink-2, #64748b);
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-rule, #e2e8f0);
  border-radius: 999px;
  font-size: var(--text-sm, 14px);
  font-weight: 600;
  line-height: 1;
  text-decoration: none;
  transition: border-color var(--dur-fast, 150ms) ease,
    color var(--dur-fast, 150ms) ease,
    background-color var(--dur-fast, 150ms) ease;
}

.admin-back-link:hover,
.admin-back-link:focus-visible {
  color: var(--color-primary, #2563eb);
  background: var(--color-primary-soft, #dbeafe);
  border-color: var(--color-primary, #2563eb);
  outline: none;
}

.admin-back-link__icon {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--color-paper-2, #f1f5f9);
  color: var(--color-primary, #2563eb);
  transition: background-color var(--dur-fast, 150ms) ease,
    color var(--dur-fast, 150ms) ease;
}

.admin-back-link:hover .admin-back-link__icon,
.admin-back-link:focus-visible .admin-back-link__icon {
  background: var(--color-primary, #2563eb);
  color: #fff;
}
</style>
