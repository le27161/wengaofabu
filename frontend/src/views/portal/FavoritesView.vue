<template>
  <div class="container favorites-page">
    <header class="page-head">
      <h1 class="page-head__title">我的收藏</h1>
      <p class="page-head__count" v-if="!loading">共 {{ total }} 篇</p>
    </header>

    <div v-loading="loading" class="article-grid">
      <ArticleCard v-for="a in articles" :key="a.id" :article="a" />
    </div>
    <el-empty v-if="!loading && !articles.length" description="还没有收藏任何文稿">
      <router-link to="/" class="empty-link">去逛逛</router-link>
    </el-empty>

    <div class="pager">
      <el-pagination
        layout="prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="load"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { interactionApi } from '../../api'
import ArticleCard from '../../components/ArticleCard.vue'

const articles = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)

async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const res = await interactionApi.favorites({ page: page.value, page_size: pageSize })
    articles.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* Hallmark · genre: editorial · macrostructure: Catalogue · design-system: design.md · designed-as-app */
/* Hallmark · pre-emit critique: P4 H4 E4 S4 R4 V4 */
.favorites-page {
  padding-top: var(--space-5);
}

.page-head {
  border-bottom: 2px solid var(--color-ink);
  padding-bottom: var(--space-3);
  margin-bottom: var(--space-5);
}

.page-head__title {
  font-family: var(--font-heading);
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--color-ink);
}

.page-head__count {
  color: var(--color-ink-2);
  font-size: var(--text-sm);
  margin: var(--space-2) 0 0;
}

.article-grid {
  display: flex;
  flex-direction: column;
  min-height: 200px;
}

.empty-link {
  display: inline-flex;
  align-items: center;
  min-height: var(--size-touch);
  padding: 0 var(--space-5);
  color: var(--color-paper);
  background: var(--color-accent);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}

.empty-link:hover {
  background: var(--color-primary-dark);
}

.pager {
  display: flex;
  justify-content: center;
  margin-top: var(--space-6);
}

.pager :deep(.el-pagination button),
.pager :deep(.el-pagination .el-pager li) {
  min-height: 32px;
}
</style>
