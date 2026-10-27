<template>
  <div class="resource-admin">
    <div class="admin-head">
      <span class="admin-head__icon" aria-hidden="true">
        <el-icon><Picture /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">资源管理</h1>
        <p class="admin-head__sub">管理图片、视频、音频与 PDF 素材，供文稿封面与正文引用</p>
      </div>
      <div class="admin-head__actions">
        <el-button :loading="urlUploading" @click="urlDialogVisible = true">
          <el-icon><Link /></el-icon>
          链接上传
        </el-button>
        <el-upload :show-file-list="false" :http-request="doUpload" accept="image/*,video/mp4,audio/mpeg,application/pdf">
          <el-button type="primary" :loading="uploading">上传资源</el-button>
        </el-upload>
        <el-button type="danger" plain :disabled="!selectedRows.length" @click="batchRemove">
          <el-icon><Delete /></el-icon>
          批量删除{{ selectedRows.length ? `（${selectedRows.length}）` : '' }}
        </el-button>
      </div>
    </div>

    <!-- 通过线上链接下载图片入库 -->
    <el-dialog v-model="urlDialogVisible" title="通过链接上传图片" width="520px" append-to-body>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="图片链接">
          <el-input
            v-model="imageUrl"
            placeholder="https://example.com/xxx.jpg"
            clearable
            @keyup.enter="submitByUrl"
          />
        </el-form-item>
        <p class="url-tip">支持 jpg / png / gif / webp / svg，提交后系统会下载图片并存入资源库</p>
      </el-form>
      <template #footer>
        <el-button @click="urlDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="urlUploading" @click="submitByUrl">下载并上传</el-button>
      </template>
    </el-dialog>

    <div class="admin-card">
      <div class="admin-card__toolbar">
        <el-input
          v-model="keyword"
          placeholder="按文件名搜索"
          clearable
          style="width: 240px"
          @keyup.enter="reload"
          @clear="reload"
        />
        <el-button @click="reload">
          <el-icon><Search /></el-icon>
          查询
        </el-button>
      </div>

      <el-table :data="resources" v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="48" />
        <el-table-column label="资源" min-width="260">
          <template #default="{ row }">
            <div class="cell-media">
              <img
                v-if="row.file_type.startsWith('image')"
                :src="row.url"
                :alt="row.filename"
                class="cell-thumb"
                loading="lazy"
              />
              <span v-else class="cell-thumb cell-thumb--empty">
                {{ row.file_type.split('/')[1]?.slice(0, 4).toUpperCase() || 'FILE' }}
              </span>
              <div class="cell-title">
                <span class="cell-title__main" :title="row.filename">{{ row.filename }}</span>
                <span class="cell-title__sub">{{ formatSize(row.file_size) }} · {{ row.created_at }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <span class="mini-tag" :class="typeTagClass(row.file_type)">{{ typeLabel(row.file_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="uploader_name" label="上传者" width="140" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link type="primary" @click="copyUrl(row)">
                <el-icon><CopyDocument /></el-icon>
                复制链接
              </el-button>
              <el-button link type="danger" @click="remove(row)">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="admin-pager">
        <span class="admin-pager__info">共 <strong>{{ total }}</strong> 个资源</span>
        <el-pagination
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="changePage"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CopyDocument, Delete, Link, Picture, Search } from '@element-plus/icons-vue'
import { resourceApi } from '../../api'

const resources = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const uploading = ref(false)
const keyword = ref('')
const urlDialogVisible = ref(false)
const imageUrl = ref('')
const urlUploading = ref(false)
const selectedRows = ref([])

function formatSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function load() {
  loading.value = true
  try {
    const res = await resourceApi.list({ page: page.value, page_size: pageSize, keyword: keyword.value })
    resources.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

function changePage(p) {
  page.value = p
  load()
}

async function doUpload({ file }) {
  uploading.value = true
  const fd = new FormData()
  fd.append('file', file)
  try {
    await resourceApi.upload(fd)
    ElMessage.success('上传成功')
    load()
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    uploading.value = false
  }
}

function typeLabel(fileType) {
  if (fileType.startsWith('image')) return '图片'
  if (fileType.startsWith('video')) return '视频'
  if (fileType.startsWith('audio')) return '音频'
  if (fileType.includes('pdf')) return 'PDF'
  return fileType.split('/')[1]?.toUpperCase() || fileType
}

function typeTagClass(fileType) {
  if (fileType.startsWith('image')) return 'mini-tag--green'
  if (fileType.startsWith('video')) return 'mini-tag--violet'
  if (fileType.startsWith('audio')) return 'mini-tag--orange'
  return ''
}

async function submitByUrl() {
  const url = imageUrl.value.trim()
  if (!url) {
    ElMessage.warning('请输入图片链接')
    return
  }
  if (!/^https?:\/\//i.test(url)) {
    ElMessage.warning('仅支持 http/https 链接')
    return
  }
  urlUploading.value = true
  try {
    await resourceApi.uploadByUrl({ url })
    ElMessage.success('链接图片已下载并入库')
    urlDialogVisible.value = false
    imageUrl.value = ''
    reload()
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    urlUploading.value = false
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function copyUrl(row) {
  try {
    await navigator.clipboard.writeText(row.url)
    ElMessage.success('链接已复制')
  } catch {
    ElMessage.info(row.url)
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除资源「${row.filename}」？相关引用将失效。`, '删除确认', { type: 'warning' })
    await resourceApi.remove(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(String(e))
  }
}

async function batchRemove() {
  if (!selectedRows.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedRows.value.length} 个资源？相关引用将失效且不可恢复。`,
      '批量删除确认',
      { type: 'warning' },
    )
  } catch {
    return
  }
  let ok = 0
  let fail = 0
  for (const row of selectedRows.value) {
    try {
      await resourceApi.remove(row.id)
      ok++
    } catch {
      fail++
    }
  }
  selectedRows.value = []
  if (fail) {
    ElMessage.warning(`已删除 ${ok} 个，失败 ${fail} 个`)
  } else {
    ElMessage.success(`已删除 ${ok} 个资源`)
  }
  load()
}

onMounted(load)
</script>

<style scoped>
.url-tip {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-secondary, #64748b);
}
</style>

