// 全球地区/城市热点坐标（科技新闻大屏用）
// 每个地区包含经纬度 + 关键词，用于把文稿标题/摘要匹配到球面对应点位。
// 匹配不到时由 HomeView 用确定性哈希把稿件落到最近的点位。

export const REGIONS = [
  { id: 'beijing', name: '北京', en: 'Beijing', lat: 39.9, lng: 116.4, kw: ['北京', '中国', 'beijing', '首都', '中关村'] },
  { id: 'shanghai', name: '上海', en: 'Shanghai', lat: 31.2, lng: 121.5, kw: ['上海', 'shanghai', '浦东', '沪'] },
  { id: 'shenzhen', name: '深圳', en: 'Shenzhen', lat: 22.5, lng: 114.1, kw: ['深圳', 'shenzhen', '粤港澳', '大湾区', '腾讯'] },
  { id: 'hongkong', name: '香港', en: 'Hong Kong', lat: 22.3, lng: 114.2, kw: ['香港', 'hong kong', '港交所', '香港科技'] },
  { id: 'tokyo', name: '东京', en: 'Tokyo', lat: 35.7, lng: 139.7, kw: ['东京', '日本', 'tokyo', 'japan', '索尼', '丰田'] },
  { id: 'seoul', name: '首尔', en: 'Seoul', lat: 37.6, lng: 127.0, kw: ['首尔', '韩国', 'seoul', 'korea', '三星'] },
  { id: 'singapore', name: '新加坡', en: 'Singapore', lat: 1.35, lng: 103.8, kw: ['新加坡', 'singapore', '东盟'] },
  { id: 'sydney', name: '悉尼', en: 'Sydney', lat: -33.9, lng: 151.2, kw: ['悉尼', '澳大利亚', 'sydney', 'australia'] },
  { id: 'moscow', name: '莫斯科', en: 'Moscow', lat: 55.8, lng: 37.6, kw: ['莫斯科', '俄罗斯', 'moscow', 'russia'] },
  { id: 'london', name: '伦敦', en: 'London', lat: 51.5, lng: -0.1, kw: ['伦敦', '英国', 'london', 'uk', '英国科技'] },
  { id: 'paris', name: '巴黎', en: 'Paris', lat: 48.9, lng: 2.35, kw: ['巴黎', '法国', 'paris', 'france'] },
  { id: 'berlin', name: '柏林', en: 'Berlin', lat: 52.5, lng: 13.4, kw: ['柏林', '德国', 'berlin', 'germany', '慕尼黑'] },
  { id: 'newyork', name: '纽约', en: 'New York', lat: 40.7, lng: -74.0, kw: ['纽约', '美国', 'new york', 'usa', '华尔街', '硅谷'] },
  { id: 'sanfrancisco', name: '旧金山', en: 'San Francisco', lat: 37.8, lng: -122.4, kw: ['旧金山', '硅谷', 'san francisco', '湾区', '加州'] },
  { id: 'losangeles', name: '洛杉矶', en: 'Los Angeles', lat: 34.05, lng: -118.2, kw: ['洛杉矶', 'los angeles', '好莱坞'] },
  { id: 'saopaulo', name: '圣保罗', en: 'Sao Paulo', lat: -23.5, lng: -46.6, kw: ['圣保罗', '巴西', 'sao paulo', 'brazil'] },
  { id: 'cairo', name: '开罗', en: 'Cairo', lat: 30.0, lng: 31.2, kw: ['开罗', '埃及', 'cairo', 'egypt'] },
  { id: 'dubai', name: '迪拜', en: 'Dubai', lat: 25.2, lng: 55.3, kw: ['迪拜', '阿联酋', 'dubai', 'uae', '中东'] },
  { id: 'mumbai', name: '孟买', en: 'Mumbai', lat: 19.1, lng: 72.9, kw: ['孟买', '印度', 'mumbai', 'india', '班加罗尔'] },
  { id: 'jakarta', name: '雅加达', en: 'Jakarta', lat: -6.2, lng: 106.8, kw: ['雅加达', '印尼', 'jakarta', 'indonesia'] },
  { id: 'taipei', name: '台北', en: 'Taipei', lat: 25.0, lng: 121.5, kw: ['台北', '台湾', 'taipei', '台积电', '台湾科技'] },
  { id: 'bangkok', name: '曼谷', en: 'Bangkok', lat: 13.8, lng: 100.5, kw: ['曼谷', '泰国', 'bangkok', 'thailand'] },
  { id: 'kualalumpur', name: '吉隆坡', en: 'Kuala Lumpur', lat: 3.1, lng: 101.7, kw: ['吉隆坡', '马来西亚', 'kuala lumpur', 'malaysia'] },
  { id: 'newdelhi', name: '新德里', en: 'New Delhi', lat: 28.6, lng: 77.2, kw: ['新德里', '德里', 'new delhi'] },
  { id: 'telaviv', name: '特拉维夫', en: 'Tel Aviv', lat: 32.1, lng: 34.8, kw: ['特拉维夫', '以色列', 'tel aviv', 'israel'] },
  { id: 'istanbul', name: '伊斯坦布尔', en: 'Istanbul', lat: 41.0, lng: 28.9, kw: ['伊斯坦布尔', '土耳其', 'istanbul', 'turkey'] },
  { id: 'frankfurt', name: '法兰克福', en: 'Frankfurt', lat: 50.1, lng: 8.7, kw: ['法兰克福', 'frankfurt', '欧洲央行'] },
  { id: 'madrid', name: '马德里', en: 'Madrid', lat: 40.4, lng: -3.7, kw: ['马德里', '西班牙', 'madrid', 'spain'] },
  { id: 'rome', name: '罗马', en: 'Rome', lat: 41.9, lng: 12.5, kw: ['罗马', '意大利', 'rome', 'italy'] },
  { id: 'amsterdam', name: '阿姆斯特丹', en: 'Amsterdam', lat: 52.4, lng: 4.9, kw: ['阿姆斯特丹', '荷兰', 'amsterdam', 'netherlands'] },
  { id: 'stockholm', name: '斯德哥尔摩', en: 'Stockholm', lat: 59.3, lng: 18.1, kw: ['斯德哥尔摩', '瑞典', 'stockholm', 'sweden'] },
  { id: 'toronto', name: '多伦多', en: 'Toronto', lat: 43.7, lng: -79.4, kw: ['多伦多', '加拿大', 'toronto', 'canada'] },
  { id: 'chicago', name: '芝加哥', en: 'Chicago', lat: 41.9, lng: -87.6, kw: ['芝加哥', 'chicago'] },
  { id: 'mexicocity', name: '墨西哥城', en: 'Mexico City', lat: 19.4, lng: -99.1, kw: ['墨西哥城', '墨西哥', 'mexico city', 'mexico'] },
  { id: 'buenosaires', name: '布宜诺斯艾利斯', en: 'Buenos Aires', lat: -34.6, lng: -58.4, kw: ['布宜诺斯艾利斯', '阿根廷', 'buenos aires', 'argentina'] },
  { id: 'lima', name: '利马', en: 'Lima', lat: -12.0, lng: -77.0, kw: ['利马', '秘鲁', 'lima', 'peru'] },
  { id: 'lagos', name: '拉各斯', en: 'Lagos', lat: 6.5, lng: 3.4, kw: ['拉各斯', '尼日利亚', 'lagos', 'nigeria'] },
  { id: 'nairobi', name: '内罗毕', en: 'Nairobi', lat: -1.3, lng: 36.8, kw: ['内罗毕', '肯尼亚', 'nairobi', 'kenya'] },
  { id: 'capetown', name: '开普敦', en: 'Cape Town', lat: -33.9, lng: 18.4, kw: ['开普敦', '南非', 'cape town', 'south africa'] },
  { id: 'melbourne', name: '墨尔本', en: 'Melbourne', lat: -37.8, lng: 145.0, kw: ['墨尔本', 'melbourne'] },
  { id: 'auckland', name: '奥克兰', en: 'Auckland', lat: -36.8, lng: 174.8, kw: ['奥克兰', '新西兰', 'auckland', 'new zealand'] },
]

// 把经纬度转为球面单位向量（y 轴向上）
export function latLngToVector3(lat, lng, radius = 1) {
  const phi = ((90 - lat) * Math.PI) / 180
  const theta = ((lng + 180) * Math.PI) / 180
  return {
    x: -radius * Math.sin(phi) * Math.cos(theta),
    y: radius * Math.cos(phi),
    z: radius * Math.sin(phi) * Math.sin(theta),
  }
}
