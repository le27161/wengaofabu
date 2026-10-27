<template>
  <AuthShell>
    <div class="auth-card">
      <router-link to="/" class="auth-card__brand" aria-label="返回首页">
        <span class="auth-card__dot" aria-hidden="true"></span>
        <span>瞭望全球，洞见真知</span>
      </router-link>

      <h1 class="auth-card__title">登录开启，与时代同频</h1>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large" @submit.prevent="submit">
        <el-form-item label="账号" prop="username">
          <el-input v-model="form.username" placeholder="请输入账号" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
            autocomplete="current-password"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button type="primary" class="auth-card__submit" :loading="loading" @click="submit">
          登录
        </el-button>
      </el-form>

      <p class="auth-card__switch">
        还没有账号？
        <router-link :to="{ name: 'register', query: { redirect: redirect } }">立即注册</router-link>
      </p>
    </div>
  </AuthShell>

  <!-- 登录后兴趣偏好选择：未设置过且未跳过时弹出 -->
  <PreferenceDialog
    v-model="showPref"
    :categories="prefCategories"
    @saved="onPrefSaved"
    @skipped="onPrefSkipped"
  />
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi, categoryApi, portalApi, preferenceApi } from '../../api'
import { useAuthStore } from '../../stores/auth'
import AuthShell from '../../components/AuthShell.vue'
import PreferenceDialog from '../../features/preference/PreferenceDialog.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)
const queryRedirect = route.query.redirect || ''
const redirect = queryRedirect && queryRedirect !== '/' ? queryRedirect : '/globe'

// 根据后台开屏动画开关决定登录后默认跳转目标
async function resolveDefaultRedirect() {
  if (queryRedirect && queryRedirect !== '/') return queryRedirect
  try {
    const res = await portalApi.splash()
    return res.enabled ? '/globe' : '/'
  } catch {
    // 获取失败时保持原行为，仍跳转开屏页
    return '/globe'
  }
}

// 兴趣偏好弹窗状态
const showPref = ref(false)
const prefCategories = ref([])

const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  await formRef.value.validate()
  loading.value = true
  try {
    const res = await authApi.login(form)
    auth.setSession(res.access_token, res.user)
    ElMessage.success('登录成功')
    // 登录成功后默认进入 3D 地球大屏；若来自受保护页面则回到原页面
    await maybeOpenPreference(res.user)
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

// 登录后判断是否需要弹出兴趣偏好选择
async function maybeOpenPreference(user) {
  const skipKey = `wgf_pref_skipped_${user?.id}`
  try {
    const pref = await preferenceApi.get()
    if (pref.has_preference || localStorage.getItem(skipKey)) {
      router.push(await resolveDefaultRedirect())
      return
    }
    const cats = await categoryApi.list()
    prefCategories.value = cats.items || []
    showPref.value = true
  } catch {
    // 查询失败不阻塞登录，直接进入
    router.push(await resolveDefaultRedirect())
  }
}

async function onPrefSaved() {
  showPref.value = false
  router.push(await resolveDefaultRedirect())
}

async function onPrefSkipped() {
  const skipKey = `wgf_pref_skipped_${auth.user?.id}`
  try {
    localStorage.setItem(skipKey, '1')
  } catch {
    // ignore
  }
  showPref.value = false
  router.push(await resolveDefaultRedirect())
}

</script>

<style scoped>
/* 玻璃拟态登录卡 */
.auth-card {
  width: 100%;
  background: rgba(8, 18, 34, 0.55);
  backdrop-filter: blur(16px) saturate(1.25);
  -webkit-backdrop-filter: blur(16px) saturate(1.25);
  border: 1px solid rgba(120, 180, 235, 0.2);
  border-radius: 18px;
  padding: 32px 30px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.auth-card__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-heading);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #eaf4ff;
  margin-bottom: 26px;
}

.auth-card__dot {
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #9fd6ff, #2f7fe0 60%, #14325c);
  box-shadow: 0 0 14px rgba(80, 160, 255, 0.9);
}

.auth-card__title {
  font-family: var(--font-heading);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 1px;
  margin-bottom: 24px;
  background: linear-gradient(120deg, #eaf4ff 0%, #9fd6ff 45%, #6db6ff 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.auth-card :deep(.el-form-item__label) {
  color: rgba(190, 215, 240, 0.85);
}

/* 输入控件主题：统一覆盖 Element Plus 输入变量（挂在 .el-input 根上才能覆盖其默认值） */
.auth-card :deep(.el-input) {
  --el-input-bg-color: rgba(10, 24, 44, 0.62);
  --el-input-hover-fill-color: rgba(14, 30, 54, 0.74);
  --el-input-text-color: #eaf4ff;
  --el-input-placeholder-color: rgba(150, 195, 240, 0.42);
  --el-input-border-color: rgba(120, 180, 235, 0.28);
  --el-input-hover-border-color: rgba(130, 195, 255, 0.55);
  --el-input-focus-border-color: rgba(110, 185, 255, 0.9);
}

.auth-card :deep(.el-input__wrapper) {
  background: var(--el-input-bg-color);
  border: 1px solid var(--el-input-border-color);
  box-shadow: none;
  border-radius: 10px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.auth-card :deep(.el-input__wrapper:hover) {
  border-color: var(--el-input-hover-border-color);
  background-color: var(--el-input-hover-fill-color);
}

.auth-card :deep(.el-input__wrapper.is-focus) {
  border-color: var(--el-input-focus-border-color);
  box-shadow: 0 0 0 3px rgba(70, 150, 255, 0.16);
  background-color: rgba(12, 28, 52, 0.78);
}

.auth-card :deep(.el-input__inner) {
  color: var(--el-input-text-color);
  caret-color: #9fd6ff;
}

/* 占位符：主题蓝灰，替代 Element Plus 默认中性灰 */
.auth-card :deep(.el-input__inner::placeholder) {
  color: var(--el-input-placeholder-color);
}

/* Chrome 自动填充：保持深色玻璃底，避免白/浅蓝底突兀 */
.auth-card :deep(.el-input__wrapper input:-webkit-autofill),
.auth-card :deep(.el-input__wrapper input:-webkit-autofill:hover),
.auth-card :deep(.el-input__wrapper input:-webkit-autofill:focus) {
  -webkit-text-fill-color: #eaf4ff;
  -webkit-box-shadow: 0 0 0 1000px rgba(10, 24, 44, 0.92) inset;
  transition: background-color 999999s ease-in-out 0s;
  caret-color: #9fd6ff;
}

.auth-card__submit {
  width: 100%;
  min-height: var(--size-touch);
  margin-top: var(--space-1);
  border: none;
  background: linear-gradient(135deg, #6db6ff, #3d8bf0);
}

.auth-card__submit:hover {
  background: linear-gradient(135deg, #7cc1ff, #4a96f5);
}

.auth-card__switch {
  text-align: center;
  color: rgba(160, 200, 240, 0.72);
  font-size: 14px;
  margin: 22px 0 0;
}

.auth-card__switch a {
  display: inline-flex;
  align-items: center;
  min-height: var(--size-touch);
  padding: 0 6px;
  color: #7fc6ff;
  font-weight: 500;
}
</style>
