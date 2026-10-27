<template>
  <!-- 登录/注册全屏外壳：深空 + 3D 地球远景背景 + 玻璃卡片居中 -->
  <div class="auth-shell">
    <GlobeScene class="auth-shell__bg" :background="true" :star-count="1800" :points="[]" />
    <div class="auth-shell__veil" aria-hidden="true"></div>
    <div class="auth-shell__inner">
      <slot />
    </div>
  </div>
</template>

<script setup>
import GlobeScene from './globe/GlobeScene.vue'
</script>

<style scoped>
.auth-shell {
  position: relative;
  min-height: 100dvh;
  overflow: hidden;
  background: radial-gradient(120% 120% at 50% 40%, #060a12 0%, #010204 60%, #000000 100%);
  color: #d7e6f5;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  font-family: var(--font-body);
}

.auth-shell__bg {
  position: absolute;
  inset: 0;
  z-index: 1;
}

/* 柔光遮罩：压暗背景，让卡片更清晰 */
.auth-shell__veil {
  position: absolute;
  inset: 0;
  z-index: 2;
  background: radial-gradient(80% 60% at 50% 45%, rgba(4, 12, 26, 0.28) 0%, rgba(2, 6, 14, 0.66) 100%);
}

.auth-shell__inner {
  position: relative;
  z-index: 3;
  width: 100%;
  max-width: 430px;
}
</style>
