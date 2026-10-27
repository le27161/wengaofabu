<template>
  <div class="dashboard">
    <div class="admin-head">
      <span class="admin-head__icon">
        <el-icon><Odometer /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">仪表盘</h1>
        <p class="admin-head__sub">平台运营核心指标与待办事项</p>
      </div>
    </div>

    <!-- 数据卡片 -->
    <div class="stat-cards">
      <div v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-card__label">{{ card.label }}</span>
        <strong class="stat-card__value">{{ card.value }}</strong>
        <span v-if="card.tip" class="stat-card__tip">{{ card.tip }}</span>
      </div>
    </div>

    <div class="dashboard__grid">
      <!-- 待审核文稿 -->
      <section class="panel">
        <div class="panel__head">
          <h2>待审核文稿</h2>
          <router-link to="/admin/reviews" class="panel__more">去审核 ›</router-link>
        </div>
        <el-table :data="pending" size="small" empty-text="暂无待审核文稿">
          <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
          <el-table-column label="阶段" width="100">
            <template #default="{ row }">
              <span class="status-badge" :class="row.status === 'pending_first' ? 'status-badge--orange' : 'status-badge--red'">
                {{ row.status === 'pending_first' ? '待一审' : '待二审' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="author_name" label="作者" width="100" />
        </el-table>
      </section>

      <!-- 快捷入口 -->
      <section class="panel">
        <div class="panel__head"><h2>快捷操作</h2></div>
        <div class="quick-links">
          <router-link to="/admin/articles/new" class="quick-link">
            <strong>写新文稿</strong><span>创建草稿并提交审核</span>
          </router-link>
          <router-link to="/admin/users" class="quick-link">
            <strong>创建账号</strong><span>注册编辑或管理员</span>
          </router-link>
          <router-link to="/admin/categories" class="quick-link">
            <strong>管理栏目</strong><span>新增/编辑文稿分类</span>
          </router-link>
          <router-link to="/admin/portal" class="quick-link">
            <strong>门户设置</strong><span>配置首页轮播与公告</span>
          </router-link>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Odometer } from '@element-plus/icons-vue'
import { articleApi, reviewApi, statsApi } from '../../api'

const overview = ref({})
const pending = ref([])

const cards = computed(() => [
  { label: '注册用户', value: overview.value.total_users ?? '-', tip: `编辑 ${overview.value.total_editors ?? 0} 人` },
  { label: '文稿总数', value: overview.value.total_articles ?? '-', tip: `已发布 ${overview.value.published_articles ?? 0}` },
  { label: '待审核', value: overview.value.pending_review ?? '-', tip: '一级/二级审核' },
  { label: '今日浏览', value: overview.value.today_views ?? '-', tip: `今日事件 ${overview.value.today_events ?? 0}` },
  { label: '累计浏览', value: overview.value.total_views ?? '-' },
  { label: '累计互动', value: (overview.value.total_likes ?? 0) + (overview.value.total_favorites ?? 0) + (overview.value.total_shares ?? 0), tip: '点赞+收藏+转发' },
])

onMounted(async () => {
  try {
    const [statsRes, l1, l2] = await Promise.all([
      statsApi.overview(),
      reviewApi.pending({ level: 1, page_size: 5 }),
      reviewApi.pending({ level: 2, page_size: 5 }),
    ])
    overview.value = statsRes
    pending.value = [...l1.items, ...l2.items]
  } catch (e) {
    ElMessage.error(String(e))
  }
})
</script>

<style scoped>
.stat-cards {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  padding: 18px;
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-card__label {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.stat-card__value {
  font-size: 28px;
  font-family: var(--font-heading);
  color: var(--color-primary);
}

.stat-card__tip {
  color: var(--color-text-muted);
  font-size: 12px;
}

.dashboard__grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 24px;
}

.panel {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--shadow-card);
}

.panel__head {
  display: flex;
  align-items: center;
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: 10px;
  margin-bottom: 14px;
}

.panel__head h2 {
  font-size: 18px;
}

.panel__more {
  margin-left: auto;
  font-size: 13px;
  color: var(--color-text-muted);
}

.quick-links {
  display: grid;
  gap: 10px;
}

.quick-link {
  display: flex;
  flex-direction: column;
  padding: 12px 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  transition: all 0.2s ease;
}

.quick-link:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.quick-link span {
  color: var(--color-text-muted);
  font-size: 13px;
}

@media (max-width: 1200px) {
  .stat-cards {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 900px) {
  .dashboard__grid {
    grid-template-columns: 1fr;
  }

  .stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>

