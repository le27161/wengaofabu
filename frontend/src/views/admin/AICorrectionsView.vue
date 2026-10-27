<template>
  <div class="ai-corrections-page">
    <div class="admin-head">
      <span class="admin-head__icon">
        <el-icon><RefreshLeft /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">AI 分类纠正</h1>
        <p class="admin-head__sub">写手对 AI 分类结果的纠正样本，可导出为高质量训练数据集（标题 + 正文 + 纠错前后分类）</p>
      </div>
    </div>

    <div class="admin-card">
      <div class="table-toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索标题 / 纠正分类"
          clearable
          style="width: 240px"
          @keyup.enter="load(1)"
          @clear="load(1)"
        />
        <el-select
          v-model="categoryFilter"
          placeholder="全部纠正分类"
          clearable
          style="width: 180px"
          @change="load(1)"
        >
          <el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" />
        </el-select>
        <el-button type="primary" @click="load(1)">查询</el-button>
        <div class="table-toolbar__spacer" />
        <el-date-picker
          v-model="exportRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
        />
        <el-button type="success" plain :loading="exporting" @click="exportJson">
          <el-icon class="export-icon"><Download /></el-icon>
          导出 JSON（训练数据集）
        </el-button>
      </div>

      <el-table :data="items" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="标题" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="corr-title">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column label="正文预览" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="corr-content">{{ row.content || '（无正文）' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="模型分类" width="110">
          <template #default="{ row }">
            <span class="mini-tag mini-tag--gray">{{ row.model_category || '未知' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="纠正分类" width="110">
          <template #default="{ row }">
            <span class="mini-tag mini-tag--green">{{ row.corrected_category }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提交人" min-width="150">
          <template #default="{ row }">
            <div class="cell-title">
              <span class="cell-title__main">{{ row.nickname }}</span>
              <span class="cell-title__sub">@{{ row.username }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="175">
          <template #default="{ row }">{{ row.created_at }}</template>
        </el-table-column>
      </el-table>

      <div class="admin-pager">
        <span class="admin-pager__info">共 {{ total }} 条样本</span>
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
import { Download, RefreshLeft } from '@element-plus/icons-vue'
import { aiCorrectionApi } from '../../api'

const keyword = ref('')
const categoryFilter = ref(null)
const categoryOptions = ref([])
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const exporting = ref(false)
const exportRange = ref([])

async function load(p) {
  loading.value = true
  try {
    const res = await aiCorrectionApi.list({
      keyword: keyword.value || undefined,
      corrected_category: categoryFilter.value || undefined,
      page: p,
      page_size: pageSize,
    })
    items.value = res.items
    total.value = res.total
    page.value = res.page
    // 纠正分类下拉选项：从当前页数据中去重收集（足够覆盖常用分类）
    categoryOptions.value = [...new Set(res.items.map((i) => i.corrected_category))]
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  load(p)
}

// 导出全量训练样本 JSON（浏览器下载 ai_corrections.json）
async function exportJson() {
  exporting.value = true
  try {
    const [startDate, endDate] = exportRange.value || []
    const blob = await aiCorrectionApi.exportJson({
      start_date: startDate || undefined,
      end_date: endDate || undefined,
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'ai_corrections.json'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    ElMessage.success(
      startDate && endDate ? `已导出 ${startDate} 至 ${endDate} 的训练样本` : '已导出全量训练样本'
    )
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    exporting.value = false
  }
}

onMounted(() => load(1))
</script>

<style scoped>
.table-toolbar__spacer {
  flex: 1;
}

.export-icon {
  margin-right: 4px;
}

.corr-title {
  font-weight: 600;
  color: var(--color-text, #1e293b);
}

.corr-content {
  color: var(--color-text-secondary, #64748b);
  font-size: 13px;
}
</style>
