// 路由：前台门户（PortalLayout）+ 管理后台（AdminLayout），懒加载拆包
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/',
    component: () => import('../layouts/PortalLayout.vue'),
    children: [
      { path: '', name: 'home', component: () => import('../views/portal/HomeView.vue') },
      { path: 'category/:slug', name: 'category', component: () => import('../views/portal/CategoryView.vue') },
      { path: 'article/:id', name: 'article-detail', component: () => import('../views/portal/ArticleDetailView.vue') },
      { path: 'search', name: 'search', component: () => import('../views/portal/SearchView.vue') },
      { path: 'ai-news', name: 'ai-news', component: () => import('../views/portal/AINewsView.vue') },
      { path: 'favorites', name: 'favorites', component: () => import('../views/portal/FavoritesView.vue'), meta: { requiresAuth: true } },
      { path: 'history', name: 'history', component: () => import('../views/portal/HistoryView.vue'), meta: { requiresAuth: true } },
      { path: 'login', name: 'login', component: () => import('../views/portal/LoginView.vue') },
      { path: 'register', name: 'register', component: () => import('../views/portal/RegisterView.vue') },
    ],
  },
  {
    path: '/admin',
    component: () => import('../layouts/AdminLayout.vue'),
    meta: { requiresAuth: true, roles: ['admin', 'editor', 'moderator'] },
    children: [
      { path: '', name: 'admin-dashboard', component: () => import('../views/admin/DashboardView.vue'), meta: { roles: ['admin'] } },
      { path: 'articles', name: 'admin-articles', component: () => import('../views/admin/ArticleListView.vue'), meta: { roles: ['admin', 'editor', 'moderator'] } },
      { path: 'articles/new', name: 'admin-article-new', component: () => import('../views/admin/ArticleEditView.vue'), meta: { roles: ['admin', 'editor', 'moderator'] } },
      { path: 'articles/:id/edit', name: 'admin-article-edit', component: () => import('../views/admin/ArticleEditView.vue'), meta: { roles: ['admin', 'editor', 'moderator'] } },
      { path: 'smart-collect', name: 'admin-smart-collect', component: () => import('../views/admin/SmartCollectView.vue'), meta: { roles: ['admin', 'editor'] } },
      { path: 'smart-collect/evaluation', name: 'admin-smart-collect-evaluation', component: () => import('../views/admin/SmartCollectEvaluationView.vue'), meta: { roles: ['admin', 'editor'] } },
      { path: 'smart-collect/tasks/:id', name: 'admin-smart-collect-task', component: () => import('../views/admin/SmartCollectTaskDetailView.vue'), meta: { roles: ['admin', 'editor'] } },
      { path: 'reviews', name: 'admin-reviews', component: () => import('../views/admin/ReviewView.vue'), meta: { roles: ['admin', 'moderator'] } },
      { path: 'categories', name: 'admin-categories', component: () => import('../views/admin/CategoryManageView.vue'), meta: { roles: ['admin'] } },
      { path: 'channels', name: 'admin-channels', component: () => import('../views/admin/ChannelsManageView.vue'), meta: { roles: ['admin'] } },
      { path: 'users', name: 'admin-users', component: () => import('../views/admin/UserManageView.vue'), meta: { roles: ['admin'] } },
      { path: 'behavior', name: 'admin-behavior', component: () => import('../views/admin/BehaviorView.vue'), meta: { roles: ['admin'] } },
      { path: 'comments', name: 'admin-comments', component: () => import('../views/admin/CommentsManageView.vue'), meta: { roles: ['admin'] } },
      { path: 'points', name: 'admin-points', component: () => import('../views/admin/PointsManageView.vue'), meta: { roles: ['admin'] } },
        { path: 'ai-calls', name: 'admin-ai-calls', component: () => import('../views/admin/AICallLogsView.vue'), meta: { roles: ['admin'] } },
        { path: 'ai-corrections', name: 'admin-ai-corrections', component: () => import('../views/admin/AICorrectionsView.vue'), meta: { roles: ['admin'] } },
        { path: 'resources', name: 'admin-resources', component: () => import('../views/admin/ResourceManageView.vue'), meta: { roles: ['admin', 'editor', 'moderator'] } },
      { path: 'portal', name: 'admin-portal', component: () => import('../views/admin/PortalManageView.vue'), meta: { roles: ['admin'] } },
      { path: 'stats', name: 'admin-stats', component: () => import('../views/admin/StatsView.vue'), meta: { roles: ['admin'] } },
      { path: 'settings', name: 'admin-settings', component: () => import('../views/admin/SettingsView.vue'), meta: { roles: ['admin'] } },
      { path: 'dify', name: 'admin-dify', component: () => import('../views/admin/DifyWorkflowView.vue'), meta: { roles: ['admin'] } },
      { path: 'theme', name: 'admin-theme', component: () => import('../views/admin/ThemeManageView.vue'), meta: { roles: ['admin'] } },
    ],
  },
  // 3D 地球大屏：独立全屏路由，登录后跳转至此
  {
    path: '/globe',
    name: 'globe',
    component: () => import('../views/GlobeView.vue'),
    meta: { requiresAuth: true },
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    return savedPosition || { top: 0 }
  },
})

// 全局守卫：登录校验 + 角色校验
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.roles && !to.meta.roles.includes(auth.user?.role)) {
    // 编辑访问后台时默认进入文稿管理；无权限页面回到首页
    if (to.path.startsWith('/admin')) {
      return auth.isEditor ? { name: 'admin-articles' } : { name: 'home' }
    }
    return { name: 'home' }
  }
  return true
})

export default router
