<template>
  <!-- 门户报头（编辑风）：品牌行（品牌 + 搜索 + 用户）+ 栏目导航条 + 页脚 -->
  <!-- 主题外壳：非登录页挂载 theme-<key> 类，驱动 CSS 变量换肤 -->
  <div class="portal-shell" :class="shellClass">
    <header v-if="!isAuthPage" class="masthead">
      <div class="container masthead__top">
        <router-link to="/" class="brand" aria-label="文稿发布首页">
          <svg class="brand__logo" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
            <rect width="32" height="32" rx="6" fill="#2563EB" />
            <path d="M9 9h14v3H12v4h10v3H12v4h11v3H9z" fill="#fff" />
          </svg>
          <span class="brand__text">在线融媒体文稿平台</span>
        </router-link>

        <SearchPanel />

        <div class="user-actions">
          <template v-if="auth.isLoggedIn">
            <el-dropdown trigger="click" @visible-change="onUserMenuOpen">
              <button class="user-btn">
                <el-avatar :size="28" :src="auth.user?.avatar || undefined">
                  {{ (auth.user?.nickname || auth.user?.username || 'U').slice(0, 1) }}
                </el-avatar>
                <span>{{ auth.user?.nickname || auth.user?.username }}</span>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <!-- 积分展示 + 每日签到 -->
                  <el-dropdown-item disabled class="user-menu__points">
                    <span>我的积分</span>
                    <strong>{{ userPoints }}</strong>
                  </el-dropdown-item>
                  <el-dropdown-item
                    :disabled="todayCheckedIn || checkingIn"
                    @click="doCheckin"
                  >
                    {{ todayCheckedIn ? '今日已签到 ✓' : '每日签到' }}
                  </el-dropdown-item>
                  <el-dropdown-item @click="router.push('/favorites')">我的收藏</el-dropdown-item>
                  <el-dropdown-item @click="openPreference">兴趣偏好</el-dropdown-item>
                  <el-dropdown-item @click="router.push('/history')">观看历史</el-dropdown-item>
                  <el-dropdown-item v-if="auth.isEditor" @click="router.push('/admin/articles')">
                    写稿/管理
                  </el-dropdown-item>
                  <el-dropdown-item v-if="auth.isAdmin" @click="router.push('/admin')">
                    管理后台
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-else>
            <router-link to="/login" class="link-btn">登录</router-link>
            <router-link to="/register" class="link-btn link-btn--solid">注册</router-link>
          </template>
        </div>
      </div>

      <nav class="masthead__nav" aria-label="主导航">
        <div class="container masthead__nav-inner">
          <router-link to="/" exact-active-class="active">首页</router-link>
          <router-link to="/ai-news" exact-active-class="active">AI 新闻助手</router-link>
          <router-link
            v-for="cat in categories"
            :key="cat.id"
            :to="{ name: 'category', params: { slug: cat.slug } }"
            :class="{ active: currentSlug === cat.slug }"
          >
            {{ cat.name }}
          </router-link>

          <!-- 同城搜索：选择城市后切换为同城内容 -->
          <div class="city-picker">
            <el-select
              v-model="city"
              class="city-picker__select"
              placeholder="同城搜索"
              filterable
              clearable
              @change="onCityChange"
            >
              <el-option label="全部城市（全站内容）" value="" />
              <el-option v-for="c in cityOptions" :key="c" :label="c" :value="c" />
            </el-select>
          </div>
        </div>
      </nav>
    </header>

    <main class="site-main" :class="{ 'site-main--full': isAuthPage }">
      <router-view />
    </main>

    <footer v-if="!isAuthPage" class="colophon">
      <div class="container colophon__inner">
        <div>
          <strong>文稿发布系统</strong>
          <p>聚合时政、经济、科技、文化等栏目资讯的内容发布平台</p>
        </div>
        <div class="colophon__links">
          <router-link to="/">首页</router-link>
          <router-link
            v-for="cat in categories"
            :key="cat.id"
            :to="{ name: 'category', params: { slug: cat.slug } }"
          >
            {{ cat.name }}
          </router-link>
        </div>
      </div>
    </footer>

    <!-- 兴趣偏好弹窗：用户菜单入口，可随时修改 -->
    <PreferenceDialog
      v-model="showPref"
      :categories="prefCategories"
      :initial-ids="prefIds"
      @saved="onPrefSaved"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { articleApi, categoryApi, pointsApi, portalApi, preferenceApi, themeApi } from '../api'
import { useAuthStore } from '../stores/auth'
import { useCityStore, CITY_PRESET } from '../stores/city'
import SearchPanel from '../features/search/SearchPanel.vue'
import PreferenceDialog from '../features/preference/PreferenceDialog.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const cityStore = useCityStore()
const categories = ref([])
const theme = ref('editorial')
const grayscale = ref(false)
// 积分签到状态：菜单打开时刷新；签到成功更新
const todayCheckedIn = ref(false)
const checkingIn = ref(false)
const userPoints = computed(() => auth.user?.points ?? 0)

// 同城搜索：当前城市 + 城市选项（预置城市 ∪ 已有数据的城市）
const city = computed({
  get: () => cityStore.city,
  set: (val) => cityStore.setCity(val),
})
const cityOptions = ref([...CITY_PRESET])

// 兴趣偏好弹窗状态（用户菜单入口）
const showPref = ref(false)
const prefCategories = ref([])
const prefIds = ref([])

// 当前栏目高亮（从路由 slug 判断；computed 保证切换栏目时高亮同步更新）
const currentSlug = computed(() => route.params.slug || '')

// 登录/注册页保持经典编辑风，不参与换肤
const isAuthPage = computed(() => ['login', 'register'].includes(route.name))
const shellClass = computed(() => {
  const themeClass = !isAuthPage.value && theme.value !== 'editorial' ? `theme-${theme.value}` : ''
  // 哀悼灰度模式：无论是否换肤都生效（登录/注册页也一并置灰）
  const grayClass = grayscale.value ? 'portal-grayscale' : ''
  return [themeClass, grayClass].filter(Boolean).join(' ')
})

// 把主题类同步到 <body>：Element Plus 的下拉/浮层（如右上角用户菜单）
// 默认渲染在 body 下，无法继承 .portal-shell 上的主题变量，挂到 body 后浮层才能随主题换肤。
watchEffect(() => {
  document.body.classList.remove('theme-cyber', 'theme-comic', 'theme-shan-shui')
  const cls = shellClass.value
  if (cls) document.body.classList.add(cls)
})

// 离开门户外壳（如进入后台）时清理 body 上的主题类，避免污染后台/登录页
onUnmounted(() => {
  document.body.classList.remove('theme-cyber', 'theme-comic', 'theme-shan-shui')
})

onMounted(async () => {
  // 拉取后台配置的门户主题（失败静默降级为经典编辑风，不影响页面使用）
  try {
    const res = await themeApi.get()
    theme.value = res.theme || 'editorial'
  } catch {
    // 主题拉取失败不阻塞页面
  }
  try {
    const gres = await portalApi.grayscale()
    grayscale.value = gres.enabled
  } catch {
    // 灰度开关拉取失败不阻塞页面
  }
  try {
    const res = await categoryApi.list()
    categories.value = res.items
  } catch (e) {
    ElMessage.error(String(e))
  }
  // 拉取已有数据的城市，补充到下拉选项（失败不影响预置城市）
  try {
    const res = await articleApi.cities()
    const extras = (res.items || []).filter((c) => c && !cityOptions.value.includes(c))
    if (extras.length) cityOptions.value = cityOptions.value.concat(extras)
  } catch {
    // 城市列表拉取失败不阻塞页面
  }
})

// ---- 同城搜索：选择城市后写入 store 并回到首页展示同城内容 ----
function onCityChange(val) {
  cityStore.setCity(val)
  if (route.name !== 'home') {
    router.push({ name: 'home' })
  }
}

// ---- 兴趣偏好弹窗（用户菜单入口，可随时修改）----
async function openPreference() {
  try {
    const [catRes, prefRes] = await Promise.all([
      categoryApi.list(),
      preferenceApi.get(),
    ])
    prefCategories.value = catRes.items
    prefIds.value = prefRes.categories || []
    showPref.value = true
  } catch (e) {
    ElMessage.error(String(e))
  }
}

function onPrefSaved(ids) {
  prefIds.value = ids
  ElMessage.success('兴趣偏好已更新')
}

// 打开用户菜单时刷新积分与今日签到状态
async function onUserMenuOpen(visible) {
  if (!visible || !auth.isLoggedIn) return
  try {
    const res = await pointsApi.me()
    todayCheckedIn.value = res.today_checked_in
    if (auth.user && auth.user.points !== res.points) {
      auth.setUser({ ...auth.user, points: res.points })
    }
  } catch {
    // 刷新失败不阻塞菜单使用，签到接口会再次给出明确错误
  }
}

// 每日签到：积分范围由后台系统设置控制（默认 1~5），每天一次
async function doCheckin() {
  if (todayCheckedIn.value || checkingIn.value) return
  checkingIn.value = true
  try {
    const res = await pointsApi.checkin()
    todayCheckedIn.value = true
    auth.setUser({ ...auth.user, points: res.points })
    ElMessage.success(res.message || '签到成功')
  } catch (e) {
    const detail = e?.response?.data?.detail
    if (detail && String(detail).includes('已签到')) {
      todayCheckedIn.value = true
      ElMessage.info(String(detail))
    } else {
      ElMessage.error(detail || e?.message || '签到失败')
    }
  } finally {
    checkingIn.value = false
  }
}

function logout() {
  auth.logout()
  ElMessage.success('已退出登录')
  router.push('/')
}
</script>

<style scoped>
/* Hallmark · genre: editorial · macrostructure: Front Page (masthead) · design-system: design.md · designed-as-app */
/* Hallmark · pre-emit critique: P4 H4 E4 S4 R4 V4 */
.masthead {
  z-index: var(--z-header);
  background: var(--color-paper);
  border-bottom: var(--rule) solid var(--color-rule);
}

.portal-shell {
  display: flex;
  flex-direction: column;
  min-height: 100dvh;
  background: var(--color-bg);
  color: var(--color-text);
  /* 主题外壳统一字体：让所有继承字体的文本（导航/搜索/排行/正文）随主题切换 */
  font-family: var(--font-body);
}

.masthead__top {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  min-height: var(--header-h);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  min-height: var(--size-touch);
  padding: 0 var(--space-1);
}

.brand__logo {
  flex-shrink: 0;
}

.brand__logo rect {
  fill: var(--color-primary);
}

.brand__text {
  font-family: var(--font-heading);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--color-ink);
}

.search-box {
  flex: 1;
  max-width: 420px;
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 2px;
  border-bottom: var(--rule) solid var(--color-rule-strong);
  transition: border-color var(--dur-base) var(--ease-out);
}

.search-box:focus-within {
  border-color: var(--color-accent);
}

.search-box input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--text-sm);
  color: var(--color-ink);
}

.search-box button {
  border: none;
  background: none;
  color: var(--color-ink-2);
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-sm);
  transition: color var(--dur-base) var(--ease-out), background var(--dur-base) var(--ease-out);
}

.search-box button:hover {
  color: var(--color-accent);
  background: var(--color-primary-soft);
}

.user-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.link-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 0 var(--space-4);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-ink-2);
  border: var(--rule) solid transparent;
  border-radius: var(--radius-sm);
  transition: color var(--dur-base) var(--ease-out), border-color var(--dur-base) var(--ease-out);
}

.link-btn:hover {
  color: var(--color-accent);
}

.link-btn--solid {
  color: var(--color-paper);
  background: var(--color-accent);
}

.link-btn--solid:hover {
  color: var(--color-paper);
  background: var(--color-primary-dark);
}

.user-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: none;
  color: var(--color-ink);
  font-size: var(--text-sm);
  min-height: var(--size-touch);
  padding: 0 var(--space-2);
  border-radius: var(--radius-sm);
}

.user-btn:hover {
  background: var(--color-paper-2);
}

/* 用户菜单积分展示项：下拉浮层渲染在 body 下，需全局样式（主题类已同步到 body） */
:global(.user-menu__points) {
  display: flex !important;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

:global(.user-menu__points strong) {
  font-size: 16px;
  font-variant-numeric: tabular-nums;
  color: var(--color-accent, #2563eb);
}

.masthead__nav {
  border-top: var(--rule) solid var(--color-rule);
  background: var(--color-paper-2);
}

.masthead__nav-inner {
  display: flex;
  align-items: center;
  gap: 2px;
  overflow-x: auto;
  scrollbar-width: none;
  min-height: 44px;
}

.masthead__nav-inner::-webkit-scrollbar {
  display: none;
}

.masthead__nav a {
  position: relative;
  display: inline-flex;
  align-items: center;
  height: 44px;
  padding: 0 var(--space-4);
  white-space: nowrap;
  color: var(--color-ink-2);
  font-size: var(--text-sm);
  font-weight: 500;
  transition: color var(--dur-base) var(--ease-out);
}

.masthead__nav a:hover {
  color: var(--color-accent);
}

.masthead__nav a.active {
  color: var(--color-ink);
  font-weight: 700;
}

.masthead__nav a.active::after {
  content: '';
  position: absolute;
  left: var(--space-4);
  right: var(--space-4);
  bottom: 0;
  height: 2px;
  background: var(--color-accent);
}

/* 同城搜索：导航条右侧城市选择器 */
.city-picker {
  margin-left: auto;
  padding-left: var(--space-3);
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.city-picker__select {
  width: 140px;
}

.city-picker__select :deep(.el-select__wrapper) {
  min-height: 32px;
  box-shadow: none;
  border-bottom: var(--rule) solid var(--color-rule-strong);
  border-radius: 0;
  background: transparent;
}

.city-picker__select :deep(.el-select__wrapper:hover),
.city-picker__select :deep(.el-select__wrapper.is-focused) {
  box-shadow: none;
}

.city-picker__select :deep(.el-select__placeholder) {
  color: var(--color-ink-3);
  font-size: var(--text-sm);
}

.city-picker__select :deep(.el-select__selected-item) {
  color: var(--color-accent);
  font-weight: 600;
  font-size: var(--text-sm);
}

.site-main {
  flex: 1;
  min-height: calc(100dvh - 280px);
}

.site-main--full {
  min-height: 100dvh;
}

.colophon {
  background: var(--color-footer-bg);
  color: var(--color-footer-text);
  margin-top: 48px;
  padding: 32px 0;
}

.colophon__inner {
  display: flex;
  justify-content: space-between;
  gap: var(--space-5);
  flex-wrap: wrap;
}

.colophon strong {
  color: var(--color-footer-strong);
  font-family: var(--font-heading);
  font-size: 18px;
}

.colophon p {
  margin: 6px 0 0;
  font-size: var(--text-xs);
  color: var(--color-footer-text);
}

.colophon__links {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
  font-size: var(--text-sm);
}

.colophon__links a {
  color: var(--color-footer-text);
  transition: color var(--dur-base) var(--ease-out);
}

.colophon__links a:hover {
  color: var(--color-footer-link-hover);
}

@media (min-width: 1024px) {
  .masthead {
    position: sticky;
    top: 0;
  }
}

@media (max-width: 768px) {
  .masthead__top {
    flex-wrap: wrap;
    gap: var(--space-3);
    padding-top: 10px;
    padding-bottom: 10px;
  }

  .search-box {
    order: 3;
    flex-basis: 100%;
    max-width: none;
    margin-left: 0;
  }

  .search-box button {
    width: var(--size-touch);
    height: var(--size-touch);
  }

  .link-btn {
    min-height: var(--size-touch);
  }

  .user-btn span {
    display: none;
  }

  .user-btn {
    min-width: var(--size-touch);
    justify-content: center;
  }

  .colophon__links a {
    display: inline-flex;
    align-items: center;
    min-height: var(--size-touch);
    padding: 0 var(--space-2);
  }
}
</style>
