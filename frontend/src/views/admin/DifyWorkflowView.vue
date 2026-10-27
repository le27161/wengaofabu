<template>
  <div class="dify-page">
    <div class="admin-head">
      <span class="admin-head__icon">
        <el-icon><Connection /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">Dify 工作流</h1>
        <p class="admin-head__sub">登记 Dify 工作流（一个应用 = 一组 API 地址 + Key），业务代码通过 run_workflow() 调用</p>
      </div>
      <div class="admin-head__actions">
        <el-button type="primary" @click="openCreate">新增工作流</el-button>
      </div>
    </div>

    <div class="admin-card">
      <el-table v-if="workflows.length" :data="workflows" v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="业务标识" width="170">
          <template #default="{ row }"><code>{{ row.name }}</code></template>
        </el-table-column>
        <el-table-column prop="description" label="用途" min-width="150" show-overflow-tooltip />
        <el-table-column prop="api_base" label="API 地址" min-width="210" show-overflow-tooltip />
        <el-table-column prop="api_key" label="API Key" width="130" />
        <el-table-column prop="timeout" label="超时(s)" width="90" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="status-badge" :class="row.enabled ? 'status-badge--green' : 'status-badge--gray'">
              {{ row.enabled ? '启用' : '停用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link @click="openRun(row)">试运行</el-button>
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!loading" description="暂无登记的工作流，点击右上角「新增工作流」" />
    </div>

    <!-- 新增 / 编辑 -->
    <el-dialog
      v-model="dialog.visible"
      :title="dialog.isEdit ? '编辑工作流' : '新增工作流'"
      width="560px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="业务标识" required>
          <el-input v-model="form.name" placeholder="如 article_summary（唯一，英文/数字/下划线）" />
        </el-form-item>
        <el-form-item label="API 地址" required>
          <el-input v-model="form.api_base" placeholder="https://api.dify.ai/v1 或自建地址" />
        </el-form-item>
        <el-form-item label="API Key" required>
          <el-input v-model="form.api_key" placeholder="app-xxx；编辑时留空保留原 Key" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="用途说明">
          <el-input v-model="form.description" placeholder="这个工作流用来做什么" />
        </el-form-item>
        <el-form-item label="输入参数">
          <el-input
            v-model="form.input_schema_text"
            type="textarea"
            :rows="4"
            placeholder='JSON 格式，如 {"title": "文章标题", "content": "正文"}'
          />
        </el-form-item>
        <el-form-item label="超时(秒)">
          <el-input-number v-model="form.timeout" :min="5" :max="3600" :step="60" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 试运行 -->
    <el-dialog v-model="runDialog.visible" title="试运行工作流" width="640px">
      <el-alert
        type="info"
        :closable="false"
        title="按工作流「开始」节点的输入变量填写 JSON，阻塞模式返回 outputs"
        class="run-tip"
      />
      <el-input
        v-model="runDialog.inputs"
        type="textarea"
        :rows="6"
        placeholder='{"title": "...", "content": "..."}'
      />
      <div v-if="runDialog.result" class="run-result">
        <div class="run-result__label">运行结果：</div>
        <pre>{{ runDialog.result }}</pre>
      </div>
      <template #footer>
        <el-button @click="runDialog.visible = false">关闭</el-button>
        <el-button type="primary" :loading="runDialog.loading" @click="doRun">运行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection } from '@element-plus/icons-vue'
import { difyApi } from '../../api'

const workflows = ref([])
const loading = ref(false)
const saving = ref(false)

const emptyForm = () => ({
  name: '',
  api_base: '',
  api_key: '',
  description: '',
  input_schema_text: '{}',
  enabled: true,
  timeout: 30,
})

const dialog = reactive({ visible: false, isEdit: false, id: null })
const form = reactive(emptyForm())

const runDialog = reactive({ visible: false, id: null, name: '', inputs: '{}', loading: false, result: '', timeout: 30 })

async function loadList() {
  loading.value = true
  try {
    const res = await difyApi.list()
    workflows.value = res.items
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

onMounted(loadList)

function openCreate() {
  Object.assign(form, emptyForm())
  dialog.isEdit = false
  dialog.id = null
  dialog.visible = true
}

function openEdit(row) {
  Object.assign(form, {
    name: row.name,
    api_base: row.api_base,
    api_key: '',
    description: row.description,
    input_schema_text:
      row.input_schema && typeof row.input_schema === 'object'
        ? JSON.stringify(row.input_schema, null, 2)
        : '{}',
    enabled: row.enabled,
    timeout: row.timeout,
  })
  dialog.isEdit = true
  dialog.id = row.id
  dialog.visible = true
}

async function save() {
  if (!form.name.trim() || !form.api_base.trim()) {
    ElMessage.warning('请填写业务标识和 API 地址')
    return
  }
  if (!dialog.isEdit && !form.api_key.trim()) {
    ElMessage.warning('请填写 API Key')
    return
  }
  let inputSchema = {}
  try {
    inputSchema = form.input_schema_text.trim() ? JSON.parse(form.input_schema_text) : {}
  } catch {
    ElMessage.error('输入参数不是合法的 JSON')
    return
  }
  const apiKey = form.api_key.trim()
  // 编辑时：空值或掩码占位（**** 开头）都视为未修改，不提交 api_key，避免覆盖真实 Key
  const apiKeyUnchanged = dialog.isEdit && (!apiKey || apiKey.startsWith('****'))
  const payload = {
    name: form.name.trim(),
    api_base: form.api_base.trim(),
    ...(apiKey && !apiKeyUnchanged ? { api_key: apiKey } : {}),
    description: form.description,
    input_schema: inputSchema,
    enabled: form.enabled,
    timeout: form.timeout,
  }
  saving.value = true
  try {
    if (dialog.isEdit) {
      await difyApi.update(dialog.id, payload)
    } else {
      await difyApi.create(payload)
    }
    ElMessage.success('保存成功')
    dialog.visible = false
    loadList()
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除工作流「${row.name}」吗？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await difyApi.remove(row.id)
    ElMessage.success('删除成功')
    loadList()
  } catch (e) {
    ElMessage.error(String(e))
  }
}

function openRun(row) {
  runDialog.id = row.id
  runDialog.name = row.name
  runDialog.inputs = '{}'
  runDialog.result = ''
  runDialog.timeout = row.timeout || 30
  runDialog.visible = true
}

async function doRun() {
  let inputs = {}
  try {
    inputs = runDialog.inputs.trim() ? JSON.parse(runDialog.inputs) : {}
  } catch {
    ElMessage.error('输入参数不是合法的 JSON')
    return
  }
  runDialog.loading = true
  try {
    const res = await difyApi.run(runDialog.id, { inputs, user: 'admin' }, (runDialog.timeout || 30) * 1000)
    runDialog.result = JSON.stringify(res, null, 2)
  } catch (e) {
    runDialog.result = JSON.stringify({ error: String(e) }, null, 2)
  } finally {
    runDialog.loading = false
  }
}
</script>

<style scoped>
.run-tip {
  margin-bottom: 12px;
}

.run-result {
  margin-top: 14px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
}

.run-result__label {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}

.run-result pre {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--color-text);
}
</style>
