<template>
  <div class="globe-page">
    <!-- 3D 地球：整个视口全部用于展示，无导航/logo/搜索 -->
    <GlobeScene
      ref="globeRef"
      class="globe-page__scene"
      :points="markers"
      :intro="introEnabled"
      :interactive="true"
      :show-beams="layers.beams"
      :show-flights="layers.flights"
      :show-heatmap="layers.heatmap"
      :auto-play="layers.autoPlay"
      :quality="isWide ? 'high' : 'low'"
      @ready="ready = true"
      @stage="onStage"
      @point-hover="onHover"
      @point-click="onPointClick"
      @point-dblclick="onPointDblClick"
      @blank-click="info = null"
    />

    <!-- 底部迷你控制面板 -->
    <transition name="fade">
      <div v-if="ready" class="globe-panel" :class="{ 'is-collapsed': panelCollapsed }">
        <button class="globe-panel__toggle" @click="panelCollapsed = !panelCollapsed" :aria-label="panelToggleLabel">
          <span v-text="panelToggleText"></span>
        </button>
        <template v-if="!panelCollapsed">
          <label class="globe-panel__row">
            <input type="checkbox" v-model="layers.beams" />
            <span>垂直光柱</span>
          </label>
          <label class="globe-panel__row">
            <input type="checkbox" v-model="layers.flights" />
            <span>全球飞线</span>
          </label>
          <label class="globe-panel__row">
            <input type="checkbox" v-model="layers.heatmap" />
            <span>新闻热力</span>
          </label>
          <label class="globe-panel__row">
            <input type="checkbox" v-model="layers.autoPlay" />
            <span>自动漫游</span>
          </label>
        </template>
      </div>
    </transition>

    <!-- 开场旅程阶段提示（抵达后整体淡出） -->
    <transition name="fade">
      <div v-if="!ready && stageLabel" class="globe-stage">
        <span class="globe-stage__dot"></span>{{ stageLabel }}
      </div>
    </transition>

    <!-- 悬浮 tooltip：展示该地区新闻标题摘要 -->
    <transition name="tip">
      <div v-if="hover && hover.point && !info" class="globe-tip" :style="tipStyle">
        <div class="globe-tip__region">
          <span class="globe-tip__dot"></span>{{ hover.point.region.name }}
        </div>
        <div class="globe-tip__title">{{ hover.point.title }}</div>
        <div v-if="hover.point.summary" class="globe-tip__summary">{{ hover.point.summary }}</div>
        <div class="globe-tip__foot">{{ hover.point.count }} 条新闻 · 单击看详情 · 双击进首页</div>
      </div>
    </transition>

    <!-- 单击点位后的内容卡：展示地区新闻详情，双击点位进入首页 -->
    <transition name="tip">
      <div v-if="info" class="globe-info">
        <button class="globe-info__close" aria-label="关闭" @click="info = null">×</button>
        <div class="globe-info__region">
          <span class="globe-tip__dot"></span>{{ info.region.name }}
        </div>
        <div class="globe-info__title">{{ info.title }}</div>
        <div v-if="info.summary" class="globe-info__summary">{{ info.summary }}</div>
        <div class="globe-info__foot">
          {{ info.count }} 条新闻 · <b>双击点位</b> 进入首页
        </div>
      </div>
    </transition>

    <!-- 开场提示（抵达地球后淡出） -->
    <transition name="fade">
      <div v-if="!ready" class="globe-page__loading">
        <span class="globe-page__loading-dot"></span>
        <span>正在抵达地球…</span>
      </div>
    </transition>

    <!-- 一键跳过（右下角，仅开场动画期间显示） -->
    <transition name="fade">
      <button v-if="!ready" class="globe-skip" @click="onSkip" aria-label="跳过开场动画">
        跳过
      </button>
    </transition>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { articleApi, portalApi } from '../api'
import { REGIONS } from '../data/regions'
import GlobeScene from '../components/globe/GlobeScene.vue'

const router = useRouter()

const ready = ref(false)
const introEnabled = ref(true)
const hover = ref(null)
const markers = ref([])
const stage = ref('')
const info = ref(null) // 单击点位后的内容卡数据
const globeRef = ref(null) // GlobeScene 模板引用（用于调用 skipIntro）

// 图层开关（控制面板）
const layers = reactive({
  beams: false,
  flights: true,
  heatmap: false,
  autoPlay: false,
})
const panelCollapsed = ref(false)
const isWide = ref(false)
function onResize() {
  if (typeof window !== 'undefined') {
    isWide.value = window.innerWidth >= 768
  }
}
onMounted(() => {
  isWide.value = window.innerWidth >= 768
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})
const panelToggleLabel = computed(function () {
  return panelCollapsed.value ? '展开控制面板' : '收起控制面板'
})
const panelToggleText = computed(function () {
  return panelCollapsed.value ? '图层' : '收起'
})

// 旅程阶段 → 文案
const STAGE_LABEL = {
  deep: '宇宙深处 · 启程',
  warp: '光粒穿越 · 高速航行',
  solar: '进入太阳系 · 旋转滑入',
  planets: '穿越行星 · 掠过星群',
  orbit: '抵达近地轨道',
}
const stageLabel = computed(() => STAGE_LABEL[stage.value] || '')

function onStage(s) {
  stage.value = s
}

// 演示兜底数据（后端不可用也能渲染地球点位，覆盖全球各大洲）
const DEMO_ARTICLES = [
  { id: 1, title: '北京中关村发布新一代国产 AI 芯片，算力提升 3 倍', summary: '国产算力迎来新突破，数据中心能效比大幅优化', category: '科技' },
  { id: 2, title: '上海浦东数据交易所上线跨境数据新板块', summary: '数据要素市场化配置再进一步，跨境流通提速', category: '经济' },
  { id: 3, title: '深圳大模型开源社区发布千亿参数新版本', summary: '开源生态持续繁荣，推理成本进一步下降', category: '科技' },
  { id: 4, title: '东京展示 8K 影像传感器，暗光成像大幅提升', summary: '影像技术新高度，助力机器视觉与自动驾驶', category: '科技' },
  { id: 5, title: '纽约华尔街 AI 投顾迎来监管新规', summary: '金融科技合规提速，算法交易透明度提升', category: '财经' },
  { id: 6, title: '旧金山硅谷独角兽单轮融资破纪录', summary: '资本再度聚焦生成式 AI 基础设施', category: '财经' },
  { id: 7, title: '伦敦金融科技峰会开幕，聚焦 AI 与支付', summary: '全球金融科技风向标，跨境支付成焦点', category: '财经' },
  { id: 8, title: '柏林工业机器人博览会展示协作新方案', summary: '制造业智能化升级，人机协作成主流', category: '科技' },
  { id: 9, title: '新加坡发布数字新基建五年路线图', summary: '东南亚数字经济加速，数据中心扩容', category: '经济' },
  { id: 10, title: '迪拜沙漠绿能数据中心正式并网', summary: '中东能源转型，绿电驱动算力', category: '能源' },
  { id: 11, title: '孟买软件外包产业加速向 AI 服务转型', summary: '印度 IT 产业新方向，AI 人才需求激增', category: '科技' },
  { id: 12, title: '首尔量子通信实验网取得阶段性进展', summary: '量子科技竞速，安全通信商用临近', category: '科技' },
  { id: 13, title: '台北晶圆厂先进制程良率再创新高', summary: '半导体制造工艺持续精进，产能稳步爬坡', category: '科技' },
  { id: 14, title: '曼谷跨境电商支付试点覆盖东南亚十国', summary: '东南亚数字支付互联互通加速', category: '经济' },
  { id: 15, title: '新德里量子材料实验室揭牌，聚焦室温超导', summary: '基础科研新投入，材料科学前沿探索', category: '科技' },
  { id: 16, title: '多伦多自动驾驶冬季测试车队规模翻倍', summary: '极寒环境算法验证提速，商业化临近', category: '科技' },
  { id: 17, title: '墨尔本海洋风电制氢示范项目并网', summary: '绿氢产业链落地，可再生能源新场景', category: '能源' },
  { id: 18, title: '法兰克福欧洲央行发布数字欧元试点白皮书', summary: '央行数字货币进程提速，跨境支付体系升级', category: '财经' },
  { id: 19, title: '马德里智慧城市大会展示 AI 交通调度', summary: '城市治理数字化，拥堵指数下降三成', category: '科技' },
  { id: 20, title: '罗马文化遗产数字化工程接入大模型导览', summary: '科技赋能文旅，沉浸式体验博物馆', category: '文化' },
  { id: 21, title: '墨西哥城卫星互联网中继站正式投运', summary: '拉美数字连接提速，偏远地区接入网络', category: '科技' },
  { id: 22, title: '布宜诺斯艾利斯金融科技周开幕', summary: '拉美金融科技生态扩张，数字银行渗透率提升', category: '财经' },
  { id: 23, title: '拉各斯移动支付平台用户突破一亿', summary: '非洲数字金融普惠提速', category: '经济' },
  { id: 24, title: '内罗毕云计算园区二期开工，绿电直供', summary: '东非数字基建扩容，数据中心绿电化', category: '科技' },
  { id: 25, title: '特拉维夫网络安全实验室发布量子加密协议', summary: '以色列网络安全创新，后量子密码标准化', category: '科技' },
  { id: 26, title: '伊斯坦布尔欧亚光纤骨干网扩容一倍', summary: '欧亚互联带宽升级，数字走廊成型', category: '经济' },
  { id: 27, title: '香港虚拟资产交易所获批数字证券新牌照', summary: '国际金融中心拥抱合规数字资产', category: '财经' },
  { id: 28, title: '悉尼大学研发太阳能海水淡化模块，成本降四成', summary: '清洁水源技术出海，大洋洲绿色基建提速', category: '能源' },
  { id: 29, title: '莫斯科发布国家超算算力开放计划', summary: '东欧算力枢纽扩容，科研机构免费接入', category: '科技' },
  { id: 30, title: '巴黎 AI 大模型训练集群采用液冷新方案', summary: '绿色数据中心在欧洲加速落地', category: '科技' },
  { id: 31, title: '洛杉矶自动驾驶出租车获准扩展夜间运营', summary: '加州自动驾驶商业化再进一步', category: '科技' },
  { id: 32, title: '圣保罗农业科技初创获种子轮大额融资', summary: '拉美农业数字化升温，精准灌溉成风口', category: '财经' },
  { id: 33, title: '开罗启动全非首家 AI 医疗影像中心', summary: '数字健康普惠非洲，AI 辅助诊断落地', category: '科技' },
  { id: 34, title: '雅加达智慧港口调度系统投入运营', summary: '东南亚物流数字化，吞吐效率提升两成', category: '经济' },
  { id: 35, title: '吉隆坡半导体封测新厂投产，瞄准车规芯片', summary: '马来西亚电子产业升级，东盟制造新节点', category: '科技' },
  { id: 36, title: '阿姆斯特丹共享电动货运单车试点覆盖全城', summary: '欧洲绿色物流创新，最后一公里零碳化', category: '能源' },
  { id: 37, title: '斯德哥尔摩量子计算初创发布纠错新算法', summary: '北欧基础科研发力，量子生态初具规模', category: '科技' },
  { id: 38, title: '芝加哥期货交易所上线 AI 商品指数', summary: '衍生品市场智能化，量化策略迎新标的', category: '财经' },
  { id: 39, title: '利马数字银行用户数翻番，普惠金融提速', summary: '秘鲁金融科技崛起，移动支付渗透率跃升', category: '经济' },
  { id: 40, title: '开普敦海上风电制氢平台完成首轮并网', summary: '南非能源转型关键一步，绿氢出口潜力大', category: '能源' },
  { id: 41, title: '奥克兰机器人厨师登上云端厨房', summary: '新西兰餐饮自动化试水，无人后厨受关注', category: '科技' },
]

/** 关键词匹配权重：中文按字数×2（地区名优先），英文按实际长度，避免「马德里」误配「德里」 */
function kwLen(k) {
  const zh = (k.match(/[\u4e00-\u9fa5]/g) || []).length
  return zh * 2 + (k.length - zh)
}

function matchRegion(article) {
  const text = `${article.title} ${article.summary || ''}`.toLowerCase()
  let best = null
  let bestLen = 0
  for (const r of REGIONS) {
    for (const k of r.kw) {
      const kk = k.toLowerCase()
      if (kk && text.includes(kk)) {
        const len = kwLen(kk)
        if (len > bestLen) {
          bestLen = len
          best = r
        }
      }
    }
  }
  return best
}

function buildMarkers(articles) {
  const map = new Map()
  for (const a of articles) {
    const r = matchRegion(a)
    if (!r) continue
    if (!map.has(r.id)) map.set(r.id, { region: r, articles: [] })
    map.get(r.id).articles.push(a)
  }
  const list = []
  for (const { region, articles } of map.values()) {
    const top = articles[0]
    list.push({
      lat: region.lat,
      lng: region.lng,
      id: region.id, // 供 GlobeScene 按地区稳定分配发光色
      region, // 完整地区对象（含 id/name），tooltip 用 region.name 显示
      title: top.title,
      summary: top.summary || '',
      count: articles.length,
      intensity: Math.min(3, 1 + articles.length),
    })
  }
  // 兜底：未被文章覆盖的地区也生成可点击标记，保证地球各地都有新闻点可点
  let di = 0
  for (const r of REGIONS) {
    if (!map.has(r.id)) {
      const demo = DEMO_ARTICLES[di % DEMO_ARTICLES.length]
      di++
      list.push({
        lat: r.lat,
        lng: r.lng,
        id: r.id,
        region: r,
        title: r.name + ' · ' + (demo.category || '科技') + '动态',
        summary: demo.summary || r.name + '地区相关资讯聚合',
        count: 1,
        intensity: 1,
        fallback: true,
      })
    }
  }
  return list
}

function onHover(payload) {
  hover.value = payload
}

function onPointClick(point) {
  // 单击点位 → 显示该地区新闻内容卡（双击判定窗口 260ms 已过，确保是单击）
  info.value = point
}

function onPointDblClick() {
  // 双击点位 → 进入首页（文稿发布系统）
  router.push('/').catch((err) => {
    console.error('[GlobeView] 跳转首页失败，回退到 location:', err)
    window.location.href = '/'
  })
}

/** 一键跳过开场动画 */
function onSkip() {
  if (globeRef.value?.skipIntro) globeRef.value.skipIntro()
}

// tooltip 定位：跟随点位，超出视口自动翻转/收边
const tipStyle = computed(() => {
  if (!hover.value || !hover.value.point) return {}
  const x = hover.value.x
  const y = hover.value.y
  const vw = window.innerWidth
  const vh = window.innerHeight
  const cx = Math.min(Math.max(x, 140), vw - 140)
  const flip = y < 150
  return {
    left: cx + 'px',
    top: y + 'px',
    transform: flip ? 'translate(-50%, 16px)' : 'translate(-50%, calc(-100% - 16px))',
  }
})

onMounted(async () => {
  try {
    const splash = await portalApi.splash()
    introEnabled.value = splash.enabled !== false
  } catch {
    introEnabled.value = true
  }
  try {
    const res = await articleApi.list({ sort: 'hot', page_size: 40 })
    markers.value = buildMarkers(res.items.length ? res.items : DEMO_ARTICLES)
  } catch {
    markers.value = buildMarkers(DEMO_ARTICLES)
  }
})
</script>

<style scoped>
.globe-page {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100dvh;
  background: #02040a;
  overflow: hidden;
  font-family: var(--font-body);
}

.globe-page__scene {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

/* 悬浮 tooltip 气泡 */
.globe-tip {
  position: absolute;
  z-index: 50;
  width: 260px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(8, 18, 34, 0.82);
  backdrop-filter: blur(12px) saturate(1.2);
  -webkit-backdrop-filter: blur(12px) saturate(1.2);
  border: 1px solid rgba(120, 180, 235, 0.28);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(80, 160, 255, 0.12) inset;
  color: #d7e6f5;
  pointer-events: none;
}

.globe-tip__region {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  letter-spacing: 0.1em;
  color: #7fd0ff;
  margin-bottom: 6px;
}

.globe-tip__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #7fd0ff;
  box-shadow: 0 0 8px #7fd0ff;
}

.globe-tip__title {
  font-size: 14px;
  font-weight: 600;
  color: #eaf4ff;
  line-height: 1.4;
  margin-bottom: 4px;
}

.globe-tip__summary {
  font-size: 12px;
  color: rgba(170, 205, 240, 0.8);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.globe-tip__foot {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(120, 180, 235, 0.16);
  font-size: 11px;
  color: rgba(150, 190, 230, 0.6);
}

/* 单击点位后的内容卡（左侧中下，不遮挡地球主体） */
.globe-info {
  position: absolute;
  z-index: 60;
  left: 28px;
  bottom: 32px;
  width: 320px;
  padding: 18px 18px 14px;
  border-radius: 14px;
  background: rgba(8, 18, 34, 0.86);
  backdrop-filter: blur(14px) saturate(1.25);
  -webkit-backdrop-filter: blur(14px) saturate(1.25);
  border: 1px solid rgba(120, 190, 255, 0.3);
  box-shadow: 0 16px 50px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(80, 160, 255, 0.14) inset;
  color: #d7e6f5;
}

.globe-info__close {
  position: absolute;
  top: 10px;
  right: 12px;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 8px;
  background: rgba(120, 180, 235, 0.12);
  color: rgba(180, 215, 245, 0.85);
  font-size: 17px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.globe-info__close:hover {
  background: rgba(120, 190, 255, 0.26);
  color: #eaf4ff;
}

.globe-info__region {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  letter-spacing: 0.12em;
  color: #7fd0ff;
  margin-bottom: 8px;
}

.globe-info__title {
  font-size: 16px;
  font-weight: 600;
  color: #eaf4ff;
  line-height: 1.45;
  margin-bottom: 6px;
}

.globe-info__summary {
  font-size: 13px;
  color: rgba(170, 205, 240, 0.82);
  line-height: 1.55;
}

.globe-info__foot {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(120, 180, 235, 0.16);
  font-size: 12px;
  color: rgba(150, 190, 230, 0.68);
}

.globe-info__foot b {
  color: #7fd0ff;
  font-weight: 600;
}

/* 开场提示 */
.globe-page__loading {
  position: absolute;
  z-index: 40;
  left: 50%;
  top: 64%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  gap: 10px;
  color: rgba(160, 200, 240, 0.75);
  font-size: 13px;
  letter-spacing: 0.08em;
  pointer-events: none;
}

.globe-page__loading-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #7fc6ff;
  box-shadow: 0 0 12px #7fc6ff;
  animation: breathe 1.4s ease-in-out infinite;
}

@keyframes breathe {
  0%, 100% { transform: scale(0.6); opacity: 0.5; }
  50% { transform: scale(1.25); opacity: 1; }
}

/* 一键跳过按钮（右下角，玻璃拟态胶囊） */
.globe-skip {
  position: absolute;
  z-index: 45;
  right: 24px;
  bottom: 24px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border: 1px solid rgba(120, 190, 255, 0.28);
  border-radius: 999px;
  background: rgba(8, 18, 34, 0.55);
  backdrop-filter: blur(12px) saturate(1.2);
  -webkit-backdrop-filter: blur(12px) saturate(1.2);
  color: rgba(200, 230, 255, 0.88);
  font-size: 13px;
  font-family: var(--font-body);
  letter-spacing: 0.12em;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease, transform 0.15s ease;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(80, 160, 255, 0.08) inset;
}

.globe-skip:hover {
  background: rgba(30, 70, 120, 0.55);
  color: #eaf4ff;
  border-color: rgba(120, 200, 255, 0.45);
  transform: translateY(-1px);
}

.globe-skip:active {
  transform: translateY(0) scale(0.97);
}

/* 旅程阶段提示（顶部居中，随阶段淡入切换） */
.globe-stage {
  position: absolute;
  z-index: 40;
  left: 50%;
  top: 9%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 20px;
  border-radius: 999px;
  background: rgba(6, 16, 32, 0.45);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(120, 190, 255, 0.22);
  color: rgba(200, 230, 255, 0.92);
  font-size: 13px;
  letter-spacing: 0.22em;
  white-space: nowrap;
  pointer-events: none;
  box-shadow: 0 6px 30px rgba(0, 0, 0, 0.35);
}

.globe-stage__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #7fd0ff;
  box-shadow: 0 0 12px #7fd0ff;
  animation: breathe 1.4s ease-in-out infinite;
}

.tip-enter-active,
.tip-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.tip-enter-from,
.tip-leave-to {
  opacity: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 底部迷你控制面板（可收起，玻璃拟态） */
.globe-panel {
  position: absolute;
  z-index: 48;
  left: 50%;
  bottom: 24px;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 14px;
  background: rgba(8, 18, 34, 0.6);
  backdrop-filter: blur(14px) saturate(1.25);
  -webkit-backdrop-filter: blur(14px) saturate(1.25);
  border: 1px solid rgba(120, 190, 255, 0.28);
  box-shadow: 0 10px 36px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(80, 160, 255, 0.1) inset;
  color: rgba(200, 230, 255, 0.9);
  font-family: var(--font-body);
  font-size: 13px;
}

.globe-panel__toggle {
  border: none;
  background: rgba(120, 190, 255, 0.14);
  color: rgba(200, 230, 255, 0.92);
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 12px;
  letter-spacing: 0.08em;
  transition: background 0.18s ease;
}

.globe-panel__toggle:hover {
  background: rgba(120, 200, 255, 0.3);
}

.globe-panel__row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  white-space: nowrap;
  opacity: 0.92;
}

.globe-panel__row input {
  accent-color: #4dabf7;
  cursor: pointer;
}

.globe-panel.is-collapsed {
  padding: 6px 8px;
}
</style>
