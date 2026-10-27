<template>
  <!-- 后台评论管理：查看全部评论/回复，支持关键词检索与删除 -->
  <div>
    <div class="admin-head">
      <span class="admin-head__icon">
        <el-icon><ChatDotRound /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">评论管理</h1>
        <p class="admin-head__sub">查看用户对文稿的评论与回复，可删除违规内容（删除顶层评论会级联删除其回复）</p>
      </div>
      <span class="admin-count">共 <strong>{{ total }}</strong> 条评论</span>
    </div>

    <div class="admin-card">
      <div class="filter-bar">
        <el-input
          v-model="keyword"
          placeholder="搜索用户名 / 昵称 / 评论内容 / 文稿标题"
          clearable
          style="width: 340px"
          @keyup.enter="load"
          @clear="load"
        />
        <el-button type="primary" @click="load">查询</el-button>
      </div>

      <el-table :data="items" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="用户" width="160">
          <template #default="{ row }">{{ row.nickname }}（{{ row.username }}）</template>
        </el-table-column>
        <el-table-column prop="article_title" label="所属文稿" min-width="200" show-overflow-tooltip />
        <el-table-column label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.parent_id ? 'info' : 'primary'" size="small" effect="plain">
              {{ row.parent_id ? '回复' : '评论' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="260" show-overflow-tooltip />
        <el-table-column label="回复对象" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.parent_content || '—' }}</template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ row.created_at }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound } from '@element-plus/icons-vue'
import { adminCommentApi, commentApi } from '../../api'

const keyword = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await adminCommentApi.list({
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    items.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// 分页切换：显式接收数字页码，避免事件对象被当作页码
function handlePageChange(p) {
  page.value = Number(p) || 1
  load()
}

async function remove(row) {
  const tip = row.parent_id
    ? '确定删除这条回复吗？'
    : '删除该评论会同时删除其全部回复，确定删除吗？'
  try {
    await ElMessageBox.confirm(tip, '删除评论', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }
  try {
    await commentApi.remove(row.id)
    ElMessage.success('评论已删除')
    load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.filter-bar {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}

.pager {
  display: flex;
  justify-content: center;
  padding: 16px;
}
</style>
