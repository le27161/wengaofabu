<template>
  <!-- 后台积分管理：查看用户积分与签到情况，可正负调整积分 -->
  <div>
    <div class="admin-head">
      <span class="admin-head__icon">
        <el-icon><Coin /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">积分管理</h1>
        <p class="admin-head__sub">查看用户积分与签到记录，可调整积分（正数加分、负数扣分）</p>
      </div>
      <span class="admin-count">共 <strong>{{ total }}</strong> 名用户</span>
    </div>

    <div class="admin-card">
      <div class="table-toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索用户名 / 昵称"
          clearable
          style="width: 260px"
          @keyup.enter="load"
          @clear="load"
        />
        <el-button type="primary" @click="load">查询</el-button>
      </div>

      <el-table :data="items" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="用户" min-width="180">
          <template #default="{ row }">
            <div class="cell-media">
              <el-avatar :size="34" :src="row.avatar || undefined">
                {{ (row.nickname || row.username).slice(0, 1) }}
              </el-avatar>
              <div class="cell-title">
                <span class="cell-title__main">{{ row.nickname }}</span>
                <span class="cell-title__sub">@{{ row.username }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="当前积分" width="130">
          <template #default="{ row }">
            <span class="points-value" :class="{ 'points-value--zero': !row.points }">{{ row.points }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="checkin_count" label="签到次数" width="100" />
        <el-table-column label="最近签到" min-width="170">
          <template #default="{ row }">{{ row.last_checkin_at || '从未签到' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right" align="center">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link type="primary" @click="openAdjust(row)">调整积分</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="admin-pager">
        <span class="admin-pager__info">共 {{ total }} 名用户</span>
        <el-pagination
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <!-- 调整积分弹窗 -->
    <el-dialog v-model="dialogVisible" title="调整积分" width="420px">
      <div v-if="current" class="adjust-info">
        <span class="adjust-info__user">{{ current.nickname }}（@{{ current.username }}）</span>
        <span class="adjust-info__points">当前积分 <strong>{{ current.points }}</strong></span>
      </div>
      <el-form label-position="top">
        <el-form-item label="调整值（正数加分 / 负数扣分，调整后不能小于 0）">
          <el-input-number v-model="delta" :step="10" :min="-100000" :max="100000" style="width: 100%" />
        </el-form-item>
      </el-form>
      <div v-if="current" class="adjust-preview">
        调整后预计积分：<strong>{{ current.points + (delta || 0) }}</strong>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="!delta" @click="saveAdjust">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Coin } from '@element-plus/icons-vue'
import { adminPointsApi } from '../../api'

const keyword = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)

const dialogVisible = ref(false)
const current = ref(null)
const delta = ref(0)
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await adminPointsApi.list({
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

function openAdjust(row) {
  current.value = row
  delta.value = 0
  dialogVisible.value = true
}

async function saveAdjust() {
  if (!delta.value) {
    ElMessage.warning('请输入调整值')
    return
  }
  saving.value = true
  try {
    const res = await adminPointsApi.adjust(current.value.id, delta.value)
    ElMessage.success(res.message || '积分已调整')
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '调整失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.points-value {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 700;
  color: var(--color-primary);
  font-variant-numeric: tabular-nums;
}

.points-value--zero {
  color: var(--color-text-muted);
  font-weight: 600;
}

.adjust-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  margin-bottom: 16px;
  background: var(--color-paper-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 14px;
}

.adjust-info__user {
  color: var(--color-text);
  font-weight: 600;
}

.adjust-info__points {
  color: var(--color-text-secondary);
}

.adjust-info__points strong {
  color: var(--color-primary);
}

.adjust-preview {
  margin-top: 4px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.adjust-preview strong {
  color: var(--color-primary);
}
</style>
