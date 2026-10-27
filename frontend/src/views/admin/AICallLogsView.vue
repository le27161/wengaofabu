<template>
  <div class="ai-log-admin">
    <div class="admin-head">
      <span class="admin-head__icon">
        <el-icon><Cpu /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">AI 调用记录</h1>
        <p class="admin-head__sub">写手在 AI 协作台调用辅助功能的完整记录（入参 / 返回值 / 调用人）</p>
      </div>
    </div>

    <div class="admin-card">
      <div class="table-toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索用户名 / 昵称"
          clearable
          style="width: 240px"
          @keyup.enter="load(1)"
          @clear="load(1)"
        />
        <el-select
          v-model="featureFilter"
          placeholder="全部功能"
          clearable
          style="width: 180px"
          @change="load(1)"
        >
          <el-option
            v-for="(name, type) in FEATURE_OPTIONS"
            :key="type"
            :label="name"
            :value="Number(type)"
          />
        </el-select>
        <el-button type="primary" @click="load(1)">查询</el-button>
      </div>

      <el-table :data="items" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="用户" min-width="170">
          <template #default="{ row }">
            <div class="cell-title">
              <span class="cell-title__main">{{ row.nickname }}</span>
              <span class="cell-title__sub">@{{ row.username }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="功能" width="150">
          <template #default="{ row }">
            <span class="mini-tag mini-tag--violet">{{ row.feature_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="调用时间" width="175">
          <template #default="{ row }">{{ row.created_at }}</template>
        </el-table-column>
        <el-table-column label="关联文稿" width="100">
          <template #default="{ row }">
            <span v-if="row.article_id" class="mini-tag">#{{ row.article_id }}</span>
            <span v-else class="cell-muted">未关联</span>
          </template>
        </el-table-column>
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="json-grid">
              <div class="json-block">
                <h4 class="json-block__title">调用入参</h4>
                <pre class="json-block__pre">{{ pretty(row.input_params) }}</pre>
              </div>
              <div class="json-block">
                <h4 class="json-block__title">返回结果</h4>
                <pre class="json-block__pre">{{ pretty(row.output_data) }}</pre>
              </div>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="admin-pager">
        <span class="admin-pager__info">共 {{ total }} 条记录</span>
        <el-pagination
          layout="total, prev, pager, next"
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
import { ElMessage } from 'element-plus'
import { Cpu } from '@element-plus/icons-vue'
import { aiLogApi } from '../../api'

// AI 功能类型映射（与后端 ai_call_logs.feature_type 注释一致）
const FEATURE_OPTIONS = {
  1: 'AI 分类',
  2: 'AI 生成摘要',
  3: 'AI 多维度审核',
  4: 'AI 内容校验',
  5: 'AI 文稿打分',
}

const keyword = ref('')
const featureFilter = ref(null)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)

function pretty(data) {
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}

// 分页切换：显式接收数字页码，避免事件对象被当作页码
function handlePageChange(p) {
  page.value = Number(p) || 1
  load()
}

async function load(p) {
  if (p) page.value = p
  loading.value = true
  try {
    const res = await aiLogApi.list({
      keyword: keyword.value || undefined,
      feature_type: featureFilter.value ?? undefined,
      page: page.value,
      page_size: pageSize,
    })
    items.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

onMounted(() => load(1))
</script>

<style scoped>
.json-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 8px 24px 16px;
}

.json-block {
  min-width: 0;
}

.json-block__title {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--color-text-secondary, #64748b);
}

.cell-muted {
  color: var(--color-text-secondary, #94a3b8);
  font-size: 12px;
}

.json-block__pre {
  margin: 0;
  padding: 12px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow-y: auto;
}

@media (max-width: 720px) {
  .json-grid {
    grid-template-columns: 1fr;
  }
}
</style>
