<template>
  <!-- 管理后台布局：侧边菜单 + 顶栏 + 内容区 -->
  <el-container class="admin-layout">
    <el-aside width="220px" class="admin-aside">
      <div class="admin-brand">
        <router-link to="/admin">
          <strong>文稿发布后台</strong>
        </router-link>
      </div>
      <el-menu :default-active="activeMenu" router class="admin-menu">
        <el-menu-item v-if="auth.isAdmin" index="/admin">
          <el-icon><Odometer /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <!-- 一级分组：按角色过滤，编辑只看到内容管理里的文稿/资源 -->
        <el-sub-menu v-for="group in visibleGroups" :key="group.title" :index="group.title">
          <template #title>
            <el-icon><component :is="group.icon" /></el-icon>
            <span>{{ group.title }}</span>
          </template>
          <el-menu-item v-for="child in group.children" :key="child.path" :index="child.path">
            {{ child.label }}
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="admin-header">
        <div class="admin-header__left">
          <AdminBackLink to="/" label="返回门户" />
        </div>
        <el-dropdown trigger="click">
          <button class="admin-user">
            <el-avatar :size="30" :src="auth.user?.avatar || undefined">
              {{ (auth.user?.nickname || 'A').slice(0, 1) }}
            </el-avatar>
            <span>{{ auth.user?.nickname || auth.user?.username }}</span>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="auth.logout(); router.push('/login')">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="admin-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Document, FolderOpened, Odometer, Setting, User,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import AdminBackLink from '../components/AdminBackLink.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// 后台菜单配置：一级分组 + 二级子项，按角色过滤后渲染
const menuGroups = [
  {
    title: '内容管理',
    icon: Document,
    children: [
      { path: '/admin/articles', label: '文稿管理', roles: ['admin', 'editor', 'moderator'] },
      { path: '/admin/reviews', label: '审核管理', roles: ['admin', 'moderator'] },
      { path: '/admin/resources', label: '资源管理', roles: ['admin', 'editor', 'moderator'] },
      { path: '/admin/smart-collect', label: '智能采编', roles: ['admin', 'editor'] },
      { path: '/admin/smart-collect/evaluation', label: '采编评估', roles: ['admin', 'editor'] },
    ],
  },
  {
    title: '内容配置',
    icon: FolderOpened,
    children: [
      { path: '/admin/categories', label: '栏目管理', roles: ['admin'] },
      { path: '/admin/channels', label: '渠道管理', roles: ['admin'] },
    ],
  },
  {
    title: '用户与数据',
    icon: User,
    children: [
      { path: '/admin/users', label: '用户管理', roles: ['admin'] },
      { path: '/admin/behavior', label: '用户行为', roles: ['admin'] },
      { path: '/admin/comments', label: '评论管理', roles: ['admin'] },
        { path: '/admin/points', label: '积分管理', roles: ['admin'] },
        { path: '/admin/ai-calls', label: 'AI 调用记录', roles: ['admin'] },
        { path: '/admin/ai-corrections', label: 'AI 分类纠正', roles: ['admin'] },
        { path: '/admin/stats', label: '数据统计', roles: ['admin'] },
    ],
  },
  {
    title: '门户与系统',
    icon: Setting,
    children: [
      { path: '/admin/portal', label: '门户设置', roles: ['admin'] },
      { path: '/admin/theme', label: '门户主题', roles: ['admin'] },
      { path: '/admin/settings', label: '系统设置', roles: ['admin'] },
      { path: '/admin/dify', label: 'Dify 工作流', roles: ['admin'] },
    ],
  },
]

// 当前角色可见的分组（空分组自动隐藏）
const visibleGroups = computed(() => {
  const role = auth.user?.role
  return menuGroups
    .map((g) => ({ ...g, children: g.children.filter((c) => c.roles.includes(role)) }))
    .filter((g) => g.children.length)
})

// 高亮当前菜单项（编辑页归入文稿管理）
const activeMenu = computed(() => {
  if (route.path.startsWith('/admin/articles')) return '/admin/articles'
  if (route.path.startsWith('/admin/smart-collect')) return '/admin/smart-collect'
  return route.path
})
</script>

<style scoped>
.admin-layout {
  min-height: 100dvh;
}

.admin-aside {
  background: #0f172a;
  color: #cbd5e1;
}

.admin-brand {
  padding: 18px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.admin-brand a {
  color: #fff;
  font-family: var(--font-heading);
  font-size: 18px;
}

.admin-menu {
  border-right: none;
  background: transparent;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #cbd5e1;
  --el-menu-hover-bg-color: rgba(255, 255, 255, 0.08);
  --el-menu-active-color: #fff;
}

.admin-menu .el-menu-item.is-active {
  background: var(--color-primary);
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.admin-user {
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: none;
  color: var(--color-text);
  font-size: 14px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
}

.admin-main {
  background: var(--color-bg);
  padding: 20px;
}
</style>
