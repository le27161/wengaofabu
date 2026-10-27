<template>
  <div class="behavior-admin">
    <div class="admin-head">
      <span class="admin-head__icon">
        <el-icon><DataAnalysis /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">用户行为</h1>
        <p class="admin-head__sub">观看历史（含累计时长）与不感兴趣反馈，供推荐与运营分析使用</p>
      </div>
    </div>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- 观看历史 -->
      <el-tab-pane label="观看历史" name="history">
        <div class="admin-card">
          <div class="table-toolbar">
            <el-input
              v-model="keyword"
              placeholder="搜索用户名 / 昵称 / 文稿标题"
              clearable
              style="width: 300px"
              @keyup.enter="load()"
              @clear="load()"
            />
            <el-button type="primary" @click="load()">查询</el-button>
            <span class="admin-count">共 <strong>{{ total }}</strong> 条观看记录，累计 <strong>{{ formatDuration(totalWatchSeconds) }}</strong></span>
          </div>
          <el-table :data="items" v-loading="loading">
            <el-table-column label="用户" min-width="160">
              <template #default="{ row }">
                <div class="cell-title">
                  <span class="cell-title__main">{{ row.nickname }}</span>
                  <span class="cell-title__sub">@{{ row.username }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="article_title" label="文稿" min-width="240" show-overflow-tooltip />
            <el-table-column label="最近观看时间" width="170">
              <template #default="{ row }">{{ row.viewed_at }}</template>
            </el-table-column>
            <el-table-column label="累计观看时长" width="130">
              <template #default="{ row }">{{ formatDuration(row.watch_seconds) }}</template>
            </el-table-column>
            <el-table-column prop="watch_count" label="观看次数" width="90" />
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-button link type="primary" @click="openArticle(row.article_id)">查看文稿</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <div class="admin-pager">
            <span class="admin-pager__info">共 {{ total }} 条记录</span>
            <el-pagination
              layout="prev, pager, next"
              :total="total"
              :page-size="pageSize"
              :current-page="page"
              @current-change="handleHistoryPage"
            />
          </div>
        </div>
      </el-tab-pane>

      <!-- 不感兴趣 -->
      <el-tab-pane label="不感兴趣" name="dislikes">
        <div class="admin-card">
          <el-table :data="dislikeItems" v-loading="dislikeLoading">
            <el-table-column label="用户" min-width="160">
              <template #default="{ row }">
                <div class="cell-title">
                  <span class="cell-title__main">{{ row.nickname }}</span>
                  <span class="cell-title__sub">@{{ row.username }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="article_title" label="文稿" min-width="240" show-overflow-tooltip />
            <el-table-column label="标记时间" width="170">
              <template #default="{ row }">{{ row.created_at }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-button link type="primary" @click="openArticle(row.article_id)">查看文稿</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <div class="admin-pager">
            <span class="admin-pager__info">共 {{ dislikeTotal }} 条记录</span>
            <el-pagination
              layout="prev, pager, next"
              :total="dislikeTotal"
              :page-size="pageSize"
              :current-page="dislikePage"
              @current-change="handleDislikePage"
            />
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { DataAnalysis } from '@element-plus/icons-vue'
import { behaviorApi } from '../../api'

const activeTab = ref('history')
const keyword = ref('')

// 观看历史
const items = ref([])
const total = ref(0)
const totalWatchSeconds = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)

// 不感兴趣
const dislikeItems = ref([])
const dislikeTotal = ref(0)
const dislikePage = ref(1)
const dislikeLoading = ref(false)

function formatDuration(seconds) {
  const s = Number(seconds) || 0
  if (s <= 0) return '0 秒'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return [h ? `${h} 小时` : '', m ? `${m} 分` : '', sec ? `${sec} 秒` : ''].filter(Boolean).join(' ') || '0 秒'
}

async function load(p) {
  // 只接受数字页码（分页组件传数字）；按钮/回车/清空触发时不传参，
  // 显式类型判断避免事件对象被误当作页码（此前曾把 PointerEvent 传给后端导致 422）
  if (typeof p === 'number' && Number.isFinite(p)) page.value = p
  loading.value = true
  try {
    const res = await behaviorApi.viewHistory({
      keyword: keyword.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    items.value = res.items
    total.value = res.total
    totalWatchSeconds.value = res.total_watch_seconds
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

async function loadDislikes(p) {
  if (p) dislikePage.value = p
  dislikeLoading.value = true
  try {
    const res = await behaviorApi.dislikes({
      keyword: keyword.value || undefined,
      page: dislikePage.value,
      page_size: pageSize,
    })
    dislikeItems.value = res.items
    dislikeTotal.value = res.total
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    dislikeLoading.value = false
  }
}

function onTabChange() {
  if (activeTab.value === 'history') {
    load()
  } else {
    loadDislikes()
  }
}

// 分页切换：显式接收数字页码，避免事件对象被当作页码
function handleHistoryPage(p) {
  page.value = Number(p) || 1
  load()
}

function handleDislikePage(p) {
  dislikePage.value = Number(p) || 1
  loadDislikes()
}

function openArticle(id) {
  window.open(`/article/${id}`, '_blank', 'noopener')
}

onMounted(load)
</script>

<style scoped>
</style>
