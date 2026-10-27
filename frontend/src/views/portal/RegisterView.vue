<template>
  <AuthShell>
    <div class="auth-card">
      <router-link to="/" class="auth-card__brand" aria-label="返回首页">
        <span class="auth-card__dot" aria-hidden="true"></span>
        <span>星球新闻</span>
      </router-link>

      <h1 class="auth-card__title">注册账号</h1>
      <p class="auth-card__subtitle">
        {{ editorRegisterEnabled ? '可选择注册为普通用户或编辑（编辑可写稿投稿）' : '当前仅开放普通用户注册，编辑账号请联系管理员开通' }}
      </p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
        <el-form-item label="账号" prop="username">
          <el-input v-model="form.username" placeholder="3-50 位字符" autocomplete="username" />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="form.nickname" placeholder="选填" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="选填" autocomplete="email" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="至少 6 位" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input v-model="form.confirm" type="password" placeholder="再次输入密码" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item v-if="editorRegisterEnabled" label="注册身份">
          <el-radio-group v-model="form.role">
            <el-radio value="user">普通用户</el-radio>
            <el-radio value="editor">编辑（可写稿）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-button type="primary" class="auth-card__submit" :loading="loading" @click="submit">注册</el-button>
      </el-form>

      <p class="auth-card__switch">
        已有账号？
        <router-link :to="{ name: 'login', query: { redirect: redirect } }">去登录</router-link>
      </p>
    </div>
  </AuthShell>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi, portalApi } from '../../api'
import AuthShell from '../../components/AuthShell.vue'

const route = useRoute()
const router = useRouter()
const formRef = ref()
const loading = ref(false)
const redirect = route.query.redirect || '/'
// 是否允许注册为编辑（后台「门户设置」控制；默认开启）
const editorRegisterEnabled = ref(true)

const form = reactive({ username: '', nickname: '', email: '', password: '', confirm: '', role: 'user' })
const rules = {
  username: [
    { required: true, message: '请输入账号', trigger: 'blur' },
    { min: 3, max: 50, message: '账号长度 3-50 位', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== form.password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

async function submit() {
  await formRef.value.validate()
  loading.value = true
  try {
    await authApi.register({
      username: form.username,
      nickname: form.nickname,
      email: form.email,
      password: form.password,
      role: form.role,
    })
    ElMessage.success('注册成功，请登录')
    router.push({ name: 'login', query: { redirect } })
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

// 拉取编辑注册策略：关闭时隐藏“编辑（可写稿）”选项
onMounted(async () => {
  try {
    const res = await portalApi.registerEditor()
    editorRegisterEnabled.value = res.enabled
    if (!res.enabled && form.role === 'editor') form.role = 'user'
  } catch {
    // 拉取失败按开启处理，不阻塞注册
  }
})

</script>

<style scoped>
/* 玻璃拟态注册卡（与登录卡同款） */
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
  font-size: 19px;
  font-weight: 700;
  color: #eaf4ff;
  margin-bottom: 28px;
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
  color: #eaf4ff;
  margin-bottom: 6px;
}

.auth-card__subtitle {
  color: rgba(160, 200, 240, 0.72);
  margin: 0 0 24px;
  font-size: 14px;
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

.auth-card :deep(.el-radio) {
  color: rgba(190, 215, 240, 0.85);
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
