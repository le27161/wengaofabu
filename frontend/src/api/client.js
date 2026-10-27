// Axios 实例：统一携带 JWT，统一处理 401 跳转登录
import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import router from '../router'

const client = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// 请求拦截：附加 Bearer Token
client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// 响应拦截：直接返回 data；401 时清理会话并跳转登录
client.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (err.response?.status === 401 && !String(err.config.url).includes('/auth/login')) {
      const auth = useAuthStore()
      auth.logout()
      router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
    }
    // 422 等校验错误的 detail 是数组，转成可读文本，避免页面显示 "[object Object]"
    const detail = err.response?.data?.detail
    const msg = Array.isArray(detail)
      ? detail.map((d) => d.msg || JSON.stringify(d)).join('；')
      : detail
    return Promise.reject(msg || err.message || '请求失败')
  },
)

export default client

