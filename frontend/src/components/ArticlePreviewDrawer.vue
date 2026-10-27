<template>
  <el-drawer
    v-model="drawerVisible"
    title="文稿预览"
    size="560px"
    :before-close="handleClose"
    destroy-on-close
  >
    <div v-loading="loading" class="preview" :class="{ 'preview--loading': loading }">
      <template v-if="detail">
        <!-- 封面 -->
        <div class="preview__cover-wrap">
          <img v-if="detail.cover_url" :src="detail.cover_url" :alt="detail.title" class="preview__cover" />
          <div v-else class="preview__cover preview__cover--empty">
            {{ (detail.categories?.[0]?.name || '文').slice(0, 1) }}
          </div>
        </div>

        <!-- 标题与状态 -->
        <div class="preview__head">
          <h2 class="preview__title">{{ detail.title }}</h2>
          <span class="status-badge" :class="statusBadgeClass(detail.status)">
            {{ statusMap[detail.status] || detail.status }}
          </span>
        </div>

        <!-- 元信息 -->
        <p class="preview__meta">
          <span>作者：{{ detail.author_name || '未知' }}</span>
          <span v-if="detail.categories?.length">
            栏目：{{ detail.categories.map((c) => c.name).join('、') }}
          </span>
          <span>更新：{{ detail.updated_at }}</span>
        </p>

        <!-- 数据 -->
        <div class="preview__stats">
          <span class="preview__stat">{{ detail.view_count }} 浏览</span>
          <span class="preview__stat">{{ detail.like_count }} 点赞</span>
          <span class="preview__stat">{{ detail.favorite_count }} 收藏</span>
          <span class="preview__stat">{{ detail.share_count }} 转发</span>
        </div>

        <!-- 摘要 -->
        <p v-if="detail.summary" class="preview__summary">{{ detail.summary }}</p>

        <!-- 正文 -->
        <div class="article-content preview__body" v-html="detail.content"></div>
      </template>

      <el-empty v-else-if="!loading" description="未找到文稿内容" />
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { articleApi } from '../api'

const props = defineProps({
  visible: { type: Boolean, default: false },
  articleId: { type: [Number, String], default: null },
})
const emit = defineEmits(['update:visible'])

const drawerVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const detail = ref(null)
const loading = ref(false)

const statusMap = {
  draft: '草稿',
  pending_first: '待一审',
  pending_second: '待二审',
  published: '已发布',
  rejected: '已驳回',
  offline: '已下线',
}

function statusBadgeClass(s) {
  return {
    draft: 'status-badge--gray',
    pending_first: 'status-badge--orange',
    pending_second: 'status-badge--red',
    published: 'status-badge--green',
    rejected: 'status-badge--red',
    offline: 'status-badge--gray',
  }[s] || 'status-badge--gray'
}

async function load() {
  if (!props.articleId) return
  loading.value = true
  detail.value = null
  try {
    detail.value = await articleApi.detail(props.articleId)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '预览加载失败')
    drawerVisible.value = false
  } finally {
    loading.value = false
  }
}

function handleClose(done) {
  detail.value = null
  done()
}

watch(
  () => [props.visible, props.articleId],
  ([visible, articleId]) => {
    if (visible && articleId) {
      load()
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.preview {
  min-height: 200px;
}

.preview--loading {
  min-height: 320px;
}

.preview__cover-wrap {
  margin-bottom: 16px;
}

.preview__cover {
  width: 100%;
  max-height: 260px;
  object-fit: cover;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  display: block;
}

.preview__cover--empty {
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 42px;
  font-weight: 700;
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.preview__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.preview__title {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 20px;
  line-height: 1.45;
}

.preview__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  color: var(--color-text-muted);
  font-size: 13px;
  margin: 10px 0 12px;
}

.preview__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.preview__stat {
  font-size: 12px;
  color: var(--color-text-secondary);
  background: var(--color-paper);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  padding: 3px 10px;
}

.preview__summary {
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.7;
  background: var(--color-primary-soft);
  border-left: 3px solid var(--color-primary);
  padding: 10px 12px;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  margin: 0 0 16px;
}

.preview__body {
  border-top: 1px solid var(--color-border);
  padding-top: 16px;
}
</style>
