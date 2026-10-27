<template>
  <div class="theme-page">
    <el-card shadow="never">
      <template #header>
        <div class="theme-header">
          <span>门户主题</span>
          <span class="theme-header__tip">
            切换用户在前台看到的风格（首页 / 栏目页 / 文章详情页）；登录页与后台保持经典风格不变
          </span>
        </div>
      </template>

      <el-skeleton v-if="loading" :rows="3" animated />

      <div v-else class="theme-grid">
        <button
          v-for="t in themes"
          :key="t.key"
          class="theme-card"
          :class="{ 'theme-card--active': current === t.key }"
          type="button"
          :aria-pressed="current === t.key"
          @click="switchTheme(t.key)"
        >
          <span class="theme-card__preview" :class="`preview-${t.key}`" aria-hidden="true">
            <span class="theme-card__preview-title">Aa</span>
            <span class="theme-card__preview-line"></span>
            <span class="theme-card__preview-line preview-line--short"></span>
          </span>
          <span class="theme-card__body">
            <span class="theme-card__name">{{ t.name }}</span>
            <span class="theme-card__desc">{{ t.desc }}</span>
          </span>
          <el-tag v-if="current === t.key" type="success" size="small">当前</el-tag>
        </button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { themeApi } from '../../api'

const themes = [
  { key: 'editorial', name: '经典编辑', desc: '新闻门户 · 衬线标题 + 规则线，原门户风格' },
  { key: 'cyber', name: '赛博霓虹', desc: '暗色底 + 霓虹青/品红辉光，科技感' },
  { key: 'comic', name: '漫画波普', desc: '奶油底 + 三原色 + 粗黑描边，波普漫画感' },
  { key: 'shan-shui', name: '山水墨韵', desc: '宣纸水墨 + 朱砂钤印 + 宋体行书，国风山水卷轴感' },
]

const current = ref('editorial')
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await themeApi.get()
    current.value = res.theme || 'editorial'
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
})

async function switchTheme(key) {
  if (current.value === key) return
  try {
    await themeApi.set(key)
    current.value = key
    ElMessage.success(`已切换到「${themes.find((t) => t.key === key)?.name}」`)
  } catch (e) {
    ElMessage.error(String(e))
  }
}
</script>

<style scoped>
.theme-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.theme-header > span:first-child {
  font-size: 15px;
  font-weight: 600;
}

.theme-header__tip {
  font-size: 12px;
  color: var(--color-text-muted);
}

.theme-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.theme-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  text-align: left;
  border: 2px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  padding: 14px;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
  font-family: inherit;
}

.theme-card:hover {
  border-color: var(--color-primary);
  transform: translateY(-2px);
}

.theme-card--active {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.theme-card__preview {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px;
  border-radius: var(--radius-sm);
  min-height: 92px;
}

.theme-card__preview-title {
  font-size: 26px;
  font-weight: 700;
  line-height: 1;
}

.theme-card__preview-line {
  height: 6px;
  border-radius: 3px;
  width: 100%;
}

.preview-line--short {
  width: 62%;
}

.theme-card__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.theme-card__name {
  font-size: 15px;
  font-weight: 600;
}

.theme-card__desc {
  font-size: 12px;
  color: var(--color-text-muted);
}

/* 预览色板：仅用于后台选择卡片，颜色与 themes.css 保持一致 */
.preview-editorial {
  background: #f8fafc;
  color: #1e293b;
}
.preview-editorial .theme-card__preview-line {
  background: #2563eb;
}

.preview-cyber {
  background: #0a0e1a;
  color: #00e5ff;
}
.preview-cyber .theme-card__preview-line {
  background: #ff2d78;
}

.preview-comic {
  background: #fff6e0;
  color: #2f6bff;
  border: 2px solid #1a1a2e;
}
.preview-comic .theme-card__preview-line {
  background: #ff3b30;
}

.preview-shan-shui {
  background: #f7f1e3;
  color: #2b2620;
  border: 1px solid #c9a86a;
}
.preview-shan-shui .theme-card__preview-line {
  background: #b3342a;
}
</style>
