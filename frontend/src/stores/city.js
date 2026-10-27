// 同城搜索状态：当前选择城市，持久化到 localStorage
// 空字符串表示“全部城市”（全站内容）；其他值为具体城市名（同城内容）
import { defineStore } from 'pinia'

// 常用城市预置（编辑文稿时可从下拉选择；导航条下拉由后端 /articles/cities 动态补充有数据的城市）
export const CITY_PRESET = [
  '北京', '上海', '广州', '深圳', '杭州', '成都', '武汉', '西安', '南京', '重庆',
  '天津', '苏州', '长沙', '郑州', '青岛', '沈阳', '大连', '厦门', '福州', '昆明',
  '贵阳', '南宁', '哈尔滨', '长春', '石家庄', '太原', '合肥', '南昌', '济南', '海口',
  '兰州', '西宁', '银川', '乌鲁木齐', '呼和浩特', '拉萨', '香港', '澳门', '台北',
]

const CITY_KEY = 'wgf_city'

export const useCityStore = defineStore('city', {
  state: () => ({
    city: localStorage.getItem(CITY_KEY) || '',
  }),

  getters: {
    // 是否处于“同城模式”
    active: (s) => Boolean(s.city),
    // 当前城市标签（用于页面展示；空串显示“全部城市”）
    label: (s) => s.city || '全部城市',
  },

  actions: {
    setCity(city) {
      this.city = (city || '').trim()
      try {
        if (this.city) {
          localStorage.setItem(CITY_KEY, this.city)
        } else {
          localStorage.removeItem(CITY_KEY)
        }
      } catch {
        // 存储失败（如隐私模式）不影响本次会话
      }
    },
  },
})
