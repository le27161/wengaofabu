<template>
  <div ref="mount" class="globe-scene" :aria-label="'3D 新闻地球'" role="img" />
</template>

<script setup>
/**
 * GlobeScene —— 科技新闻大屏 3D 地球（登录后全屏开场动画页）
 *
 * 开场旅程（5 阶段，镜头变速 + 光粒强度随速度增强）：
 *  ① 宇宙深处：镜头从极远处起步（慢），深邃星空 + 倾斜银河星带 + 星云粒子
 *  ② 光粒穿越：高速冲刺，细碎星光化作光粒流（short-tail 光粒，强度随速度增强）
 *  ③ 旋转进入太阳系：镜头沿弧线绕飞滑入，掠过泛光发亮的太阳（高亮球体 + 光晕，靠 UnrealBloom 泛光）
 *  ④ 穿越行星：依次掠过木星/火星/金星/水星，各行星沿飞行路径布置并淡出
 *  ⑤ 近地轨道：光粒淡出，镜头停在地球表面前方约 2.8 个单位；大陆/海洋/云层/大气/点位逐渐清晰
 *
 * 交互：抵达后才开启 OrbitControls（可拖拽/滚轮缩放）；拖拽暂停自转，松开恢复；
 *       单击热点显示内容卡，双击跳首页
 * 地球：程序化高清贴图打底 + 多源加载 NASA 4K 真实贴图（白昼/云层/夜灯），失败自动回退
 */
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { SMAAPass } from 'three/examples/jsm/postprocessing/SMAAPass.js'
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js'
import { BokehPass } from 'three/examples/jsm/postprocessing/BokehPass.js'
import { AfterimagePass } from 'three/examples/jsm/postprocessing/AfterimagePass.js'
import { FilmPass } from 'three/examples/jsm/postprocessing/FilmPass.js'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { latLngToVector3 } from '../../data/regions'

const props = defineProps({
  // 新闻点位：[{ lat, lng, intensity(1-3), label?, region?, title?, summary?, count? }]
  points: { type: Array, default: () => [] },
  // 是否开启开场旅程动画
  intro: { type: Boolean, default: true },
  // 到达地球后是否开启交互
  interactive: { type: Boolean, default: true },
  // 自转速度
  autoRotateSpeed: { type: Number, default: 0.12 },
  // 深空静态星星数量
  starCount: { type: Number, default: 2400 },
  // 背景模式：无旅程、无交互、静止远景（登录/注册页复用）
  background: { type: Boolean, default: false },
  // 画质等级：'high' 大屏全特效 / 'low' 移动端自动降级（关闭重后处理）
  quality: { type: String, default: 'high' },
  // 可视化图层开关（GlobeView 控制面板控制）
  showBeams: { type: Boolean, default: false }, // 垂直光柱（默认关闭，由控制面板开启）
  showFlights: { type: Boolean, default: true }, // 全球飞线
  showHeatmap: { type: Boolean, default: false }, // 高斯热力层
  autoPlay: { type: Boolean, default: false }, // 全局自动漫游（大屏无人值守）
})

// 画质预设（大屏默认全开，移动端降级）
function isLowQuality() {
  return props.quality === 'low' || (typeof window !== 'undefined' && window.innerWidth < 768)
}

const emit = defineEmits(['ready', 'point-click', 'point-dblclick', 'blank-click', 'point-hover', 'stage'])

const mount = ref(null)

// Three 核心对象
let renderer = null
let scene = null
let camera = null
let composer = null
let controls = null
let raf = 0
let clock = null
let resizeObserver = null

// 后期管线 Pass 引用（用于按模式动态开关 / resize）
let smaaPass = null
let bloomPass = null
let outputPass = null
let bokehPass = null
let afterimagePass = null
let filmPass = null

// 场景元素
let earthGroup = null
let earthMesh = null
let cloudMesh = null
let cloudLoMesh = null // 低空厚云（慢漂）
let auroraMesh = null // 外层极光环
let warpStars = null
let nebulaGroup = null
let sunGroup = null
let sunCoreMesh = null // 太阳核心，用于脉动
let atmoMeshes = [] // [{ mesh, baseI }]
let planetItems = [] // [{ group, parts:[{mesh, mat, baseOp}], fadeStart, fadeEnd }]
let pointItems = [] // [{ core, ring, phase, base, data }]
let beamItems = [] // 垂直光柱 [{ mesh, mat, baseOp, intensity }]
let flightLines = [] // 全球新闻飞线 [{ line, mat, baseOp, category }]
let heatmapMesh = null // 高斯热力层
let orbitTrails = [] // 行星公转微光轨迹 [{ mesh, mat, baseOp }]
let starMats = [] // 背景星点材质（用于稳定呼吸，避免一闪一闪）
let landingRipple = null // 落地扩散波纹
let landingRippleT = 0 // 波纹计时（<=0 表示未激活）
let idleTimer = 0 // 自动漫游：无操作计时
let autoPlayTarget = null // 自动漫游：当前聚焦点位 index
let disposed = false

// 新闻飞线配色（按大类）：科技蓝 / 财经金 / 国际紫 / 灾害红 / 其他青
const FLY_COLORS = {
  科技: '#4dabf7',
  财经: '#ffc94d',
  国际: '#b07bff',
  灾害: '#ff6b6b',
  经济: '#ffd166',
  文化: '#6fd6c9',
  能源: '#7ee081',
  其他: '#74c0fc',
}
function flyColorFor(article) {
  if (!article) return FLY_COLORS['其他']
  const cat = article.category || article.region?.name || ''
  for (const k of Object.keys(FLY_COLORS)) {
    if (cat.includes(k)) return FLY_COLORS[k]
  }
  return FLY_COLORS['其他']
}

// 指针交互状态
let pointer = { x: -9999, y: -9999 }
let hoveredIndex = -1
let autoPaused = false
let resumeTimer = null
let downPos = null
let lastClick = null // 双击判定：{ time, idx, timer }

// 旅程
let journeyCurve = null
let introDone = false
let lastStage = '' // 当前阶段（用于 stage 事件）
let warpIntensity = 0 // warp 拖尾强度（随速度平滑逼近）
let lastT = 0 // 上一帧时间（算速度用）
const prevCamPos = new THREE.Vector3() // 上一帧镜头位置（算速度用）

// 昼夜 Shader 太阳方向（与 DirectionalLight 一致，单位向量）
const SUN_DIR = new THREE.Vector3(6, 3, 6).normalize()

// 半径与时长（镜头终点 = 距地球表面约 2.8 单位，即距球心 ≈ 4.78）
const EARTH_R = 2
const JOURNEY_DURATION = 14.0 // 拉长开场旅程（warp 穿越段约占 6s）
const FINAL_CAM = new THREE.Vector3(0, 0.55, 4.78)

// 全球各地区发光色板（柔和发光，不同国家/地区亮不同中心点）
const POINT_PALETTE = [
  '#ff6b6b', '#ffa94d', '#ffd43b', '#69db7c', '#38d9a9', '#22b8cf',
  '#4dabf7', '#748ffc', '#9775fa', '#e599f7', '#f783ac', '#ff8787',
  '#63e6be', '#a9e34b', '#ffc078', '#74c0fc', '#91a7ff', '#d0bfff',
]

/** 按地区 id/名称稳定分配发光色（同一地区始终同色） */
function colorForPoint(pt, i) {
  const rid = pt.id || pt.region?.id || (typeof pt.region === 'string' ? pt.region : '') || i
  const key = String(rid + ':' + (pt.lng ?? ''))
  let h = 2166136261
  for (let k = 0; k < key.length; k++) {
    h ^= key.charCodeAt(k)
    h = Math.imul(h, 16777619)
  }
  return new THREE.Color(POINT_PALETTE[Math.abs(h) % POINT_PALETTE.length])
}

// 临时向量（避免每帧分配）
const _world = new THREE.Vector3()
const _dir = new THREE.Vector3()
const _ndc = new THREE.Vector3()
const _tmpA = new THREE.Vector3()
const _tmpB = new THREE.Vector3()

// ================= 确定性伪随机 + 值噪声（用于程序化贴图） =================

function srand(seed) {
  let s = seed >>> 0
  return () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
}

function hash2i(ix, iy) {
  let h = (ix * 374761393 + iy * 668265263) | 0
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296
}

function vnoise(x, y) {
  const xi = Math.floor(x)
  const yi = Math.floor(y)
  const xf = x - xi
  const yf = y - yi
  const u = xf * xf * (3 - 2 * xf)
  const v = yf * yf * (3 - 2 * yf)
  const a = hash2i(xi, yi)
  const b = hash2i(xi + 1, yi)
  const c = hash2i(xi, yi + 1)
  const d = hash2i(xi + 1, yi + 1)
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v
}

function fbm(x, y, oct = 4) {
  let sum = 0
  let amp = 0.5
  let f = 1
  let norm = 0
  for (let i = 0; i < oct; i++) {
    sum += amp * vnoise(x * f, y * f)
    norm += amp
    amp *= 0.5
    f *= 2
  }
  return sum / norm
}

function lighten(hex, amt) {
  const n = parseInt(hex.slice(1), 16)
  const r = Math.min(255, ((n >> 16) & 255) + amt)
  const g = Math.min(255, ((n >> 8) & 255) + amt)
  const b = Math.min(255, (n & 255) + amt)
  return `rgb(${r},${g},${b})`
}

// 大陆 blob 列表（中心经度, 纬度, 半径°）—— 决定真实大洲大致轮廓
const CONTINENTS = [
  // 北美
  [-100, 50, 30], [-95, 40, 24], [-115, 55, 20], [-85, 34, 18], [-105, 60, 15], [-125, 45, 12], [-65, 62, 9],
  // 格陵兰
  [-45, 72, 14],
  // 南美
  [-60, -10, 22], [-65, -25, 18], [-70, -40, 12], [-55, -5, 16], [-75, -15, 12], [-68, -50, 8],
  // 中美洲
  [-85, 15, 6], [-75, 10, 5],
  // 欧洲
  [15, 50, 14], [0, 50, 10], [25, 55, 11], [8, 45, 10], [18, 40, 7], [-18, 65, 4],
  // 非洲
  [20, 10, 24], [20, -2, 20], [25, -18, 18], [10, 5, 18], [30, -28, 14], [5, 15, 12], [30, -5, 8], [47, -20, 7],
  // 中东/阿拉伯
  [45, 23, 13],
  // 亚洲（大）
  [90, 50, 30], [80, 45, 26], [100, 55, 26], [110, 45, 24], [120, 55, 20], [90, 30, 22],
  [70, 40, 18], [100, 30, 18], [130, 55, 16], [80, 30, 14], [115, 30, 14],
  // 印度
  [78, 22, 12],
  // 东南亚 / 印尼
  [105, 10, 12], [115, -2, 10], [98, 5, 9], [120, -5, 8], [125, -7, 6], [110, -5, 6], [122, 13, 5],
  // 澳大利亚
  [134, -25, 18], [142, -25, 12], [120, -22, 9],
  // 日本 / 新西兰 / 古巴 / 冰岛
  [138, 37, 7], [-3, 54, 6], [173, -41, 4], [170, -44, 3], [-79, 22, 5],
]

/** 根据纬度/经度选择大陆内部色调（暖沙海岸 → 内陆植被色） */
function landTone(lat, lng) {
  if (lat > 62) return '#93a392' // 苔原
  if (lat > 48) return '#6e8a6a' // 针叶林
  const desert =
    (lat > 14 && lat < 33 && lng > -18 && lng < 62) ||
    (lat > 15 && lat < 32 && lng > 103 && lng < 152) ||
    (lat > 22 && lat < 38 && lng > -122 && lng < -100)
  if (desert) return '#c2aa7c' // 沙漠
  if (lat > 30) return '#7c9a66' // 温带
  if (lat > -10) return '#4f7d55' // 热带
  return '#678b5e' // 南温带
}

// ================= 程序化贴图 =================

/** 高清写实地球贴图（2048×1024）：海洋深度渐变 + 噪声海岸线大陆 + 极地冰盖 + 云层留白 */
function createEarthTexture() {
  const W = 2048
  const H = 1024
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')

  // 海洋：深海 → 中洋 → 深海（明显提亮，不再死黑）
  const ocean = ctx.createLinearGradient(0, 0, 0, H)
  ocean.addColorStop(0, '#123b63')
  ocean.addColorStop(0.5, '#1b5d90')
  ocean.addColorStop(1, '#123b63')
  ctx.fillStyle = ocean
  ctx.fillRect(0, 0, W, H)

  // 细节噪声打底（soft-light，给海洋/陆地增加纹理层次）
  const tile = createNoiseTile()
  ctx.save()
  ctx.globalCompositeOperation = 'soft-light'
  ctx.globalAlpha = 0.5
  ctx.drawImage(tile, 0, 0, W, H)
  ctx.globalAlpha = 0.3
  ctx.translate(W * 0.31, H * 0.23)
  ctx.rotate(0.6)
  ctx.drawImage(tile, 0, 0, W * 1.15, H * 1.15)
  ctx.restore()

  const rnd = srand(20260815)

  // 大陆架浅水（海岸外一圈淡青）
  for (const [lng, lat, r] of CONTINENTS) {
    const { cx, cy, rx, ry } = blobBox(lng, lat, r)
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(1, ry / rx)
    const g = ctx.createRadialGradient(0, 0, rx * 0.15, 0, 0, rx * 1.55)
    g.addColorStop(0, 'rgba(96,168,214,0.28)')
    g.addColorStop(1, 'rgba(96,168,214,0)')
    ctx.fillStyle = g
    ctx.beginPath()
    ctx.arc(0, 0, rx * 1.55, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
  }

  // 大陆块（噪声海岸线 + 海岸沙色到内陆植被色渐变）
  for (const [lng, lat, r] of CONTINENTS) {
    drawBlob(ctx, lng, lat, r, landTone(lat, lng), rnd)
  }

  // 极地冰盖
  drawIceCaps(ctx, rnd)

  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 8
  return tex
}

function blobBox(lng, lat, r) {
  const W = 2048
  const H = 1024
  const cx = ((lng + 180) / 360) * W
  const cy = ((90 - lat) / 180) * H
  const latScale = 1 / Math.max(Math.cos((lat * Math.PI) / 180), 0.22)
  const rx = r * (W / 360) * latScale
  const ry = r * (H / 180)
  return { cx, cy, rx, ry }
}

function drawBlob(ctx, lng, lat, r, interior, rnd) {
  const { cx, cy, rx, ry } = blobBox(lng, lat, r)
  const pts = 56
  const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, rx)
  grad.addColorStop(0, interior)
  grad.addColorStop(0.6, interior)
  grad.addColorStop(0.92, lighten(interior, 20))
  grad.addColorStop(1, 'rgba(216,199,149,0.92)') // 海岸沙
  ctx.save()
  ctx.translate(cx, cy)
  ctx.scale(1, ry / rx)
  ctx.fillStyle = grad
  ctx.beginPath()
  for (let i = 0; i <= pts; i++) {
    const a = (i / pts) * Math.PI * 2
    // 噪声扰动半径 → 不规则海岸线
    const n = fbm(Math.cos(a) * 0.7 + lng * 0.3 + 13.7, Math.sin(a) * 0.7 + lat * 0.3 + 7.3, 3)
    const rr = rx * (1 + (n - 0.5) * 0.42)
    const px = Math.cos(a) * rr
    const py = Math.sin(a) * rr
    if (i === 0) ctx.moveTo(px, py)
    else ctx.lineTo(px, py)
  }
  ctx.closePath()
  ctx.fill()
  ctx.restore()
  return rnd()
}

function drawIceCaps(ctx, rnd) {
  // 北极圈
  const rndA = srand(11)
  for (let i = 0; i < 5; i++) {
    const lng = -160 + rndA() * 320
    const lat = 79 + rndA() * 9
    const r = 10 + rndA() * 7
    drawBlob(ctx, lng, lat, r, '#eef4f7', rnd)
  }
  // 南极洲：环绕纬圈的一条白色陆地
  const W = 2048
  const H = 1024
  ctx.save()
  ctx.beginPath()
  let first = true
  for (let lng = -180; lng <= 180; lng += 8) {
    const wob = fbm(lng * 0.05 + 3, 17.7, 3)
    const lat = -66.5 - wob * 9
    const x = ((lng + 180) / 360) * W
    const y = ((90 - lat) / 180) * H
    if (first) {
      ctx.moveTo(x, y)
      first = false
    } else ctx.lineTo(x, y)
  }
  for (let lng = 180; lng >= -180; lng -= 8) {
    const x = ((lng + 180) / 360) * W
    ctx.lineTo(x, H)
  }
  ctx.closePath()
  const g = ctx.createLinearGradient(0, H * 0.8, 0, H)
  g.addColorStop(0, 'rgba(236,243,247,0.0)')
  g.addColorStop(0.25, 'rgba(236,243,247,0.95)')
  g.addColorStop(1, 'rgba(236,243,247,0.98)')
  ctx.fillStyle = g
  ctx.fill()
  ctx.restore()
}

/** 512×256 噪声瓦片：作为 soft-light 细节层 */
function createNoiseTile() {
  const W = 512
  const H = 256
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')
  const img = ctx.createImageData(W, H)
  const d = img.data
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const v = fbm(x * 0.06, y * 0.06, 4)
      const c = Math.min(255, Math.floor(v * 255))
      const i = (y * W + x) * 4
      d[i] = c
      d[i + 1] = c
      d[i + 2] = c
      d[i + 3] = 255
    }
  }
  ctx.putImageData(img, 0, 0)
  return canvas
}

/** 夜间城市灯光贴图（emissiveMap，让夜半球不再全黑） */
function createNightTexture() {
  const W = 2048
  const H = 1024
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, W, H)
  const rnd = srand(9527)

  const warm = ['255,198,120', '255,224,158', '255,214,140', '235,222,190', '255,240,210']

  // 每块大陆散布灯光
  for (const [lng, lat, r] of CONTINENTS) {
    const { cx, cy, rx, ry } = blobBox(lng, lat, r)
    const n = Math.floor(80 + r * r * 0.55)
    for (let i = 0; i < n; i++) {
      // 椭圆内高斯散布
      let px = 0
      let py = 0
      let dist2 = 2
      for (let k = 0; k < 6 && dist2 > 1; k++) {
        const a = rnd() * Math.PI * 2
        const rr = Math.sqrt(rnd()) * rx * 0.92
        px = Math.cos(a) * rr
        py = Math.sin(a) * rr * (ry / rx)
        dist2 = (px / rx) ** 2 + (py / ry) ** 2
      }
      const sx = cx + px
      const sy = cy + py
      const c = warm[Math.floor(rnd() * warm.length)]
      const s = 0.8 + rnd() * 2.0
      const a = 0.22 + rnd() * 0.55
      ctx.fillStyle = `rgba(${c},${a})`
      ctx.beginPath()
      ctx.arc(sx, sy, s, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  // 大城市光晕
  for (const [lng, lat, r] of CONTINENTS) {
    if (r < 8) continue
    const { cx, cy, rx, ry } = blobBox(lng, lat, r)
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rx * 0.55)
    g.addColorStop(0, 'rgba(255,214,150,0.16)')
    g.addColorStop(1, 'rgba(255,214,150,0)')
    ctx.fillStyle = g
    ctx.beginPath()
    ctx.arc(cx, cy, rx * 0.55, 0, Math.PI * 2)
    ctx.fill()
  }

  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

/** 淡淡流动云层（fbm 风带） */
function createCloudTexture() {
  const W = 1024
  const H = 512
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')

  const tile = document.createElement('canvas')
  tile.width = 512
  tile.height = 256
  const tctx = tile.getContext('2d')
  const img = tctx.createImageData(512, 256)
  const d = img.data
  for (let y = 0; y < 256; y++) {
    for (let x = 0; x < 512; x++) {
      const nx = x / 512
      const ny = y / 256
      const v = fbm(nx * 5 + 4.2, ny * 9 + 1.7, 4) // y 频率更高 → 水平风带
      const band = 0.5 + 0.5 * Math.sin(ny * 22 + fbm(nx * 2.4, ny * 4.1, 2) * 7)
      const a = Math.max(0, (v - 0.53)) * 1.9 * (0.55 + 0.45 * band)
      const alpha = Math.min(1, a) * 0.9
      const i = (y * 512 + x) * 4
      d[i] = 255
      d[i + 1] = 255
      d[i + 2] = 255
      d[i + 3] = Math.floor(alpha * 255)
    }
  }
  tctx.putImageData(img, 0, 0)
  ctx.drawImage(tile, 0, 0, W, H)
  // 轻微模糊让云更柔和
  if ('filter' in ctx) {
    ctx.filter = 'blur(5px)'
    ctx.globalCompositeOperation = 'source-over'
    ctx.drawImage(tile, 0, 0, W, H)
    ctx.filter = 'none'
  }

  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

/** 细圆环贴图（点位涟漪） */
function createRingTexture() {
  const S = 256
  const canvas = document.createElement('canvas')
  canvas.width = S
  canvas.height = S
  const ctx = canvas.getContext('2d')
  const c = S / 2
  const g = ctx.createRadialGradient(c, c, c * 0.05, c, c, c)
  g.addColorStop(0, 'rgba(255,255,255,0)')
  g.addColorStop(0.84, 'rgba(255,255,255,0)')
  g.addColorStop(0.93, 'rgba(255,255,255,0.95)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, S, S)
  return new THREE.CanvasTexture(canvas)
}

function createDotTexture() {
  const S = 128
  const canvas = document.createElement('canvas')
  canvas.width = S
  canvas.height = S
  const ctx = canvas.getContext('2d')
  const c = S / 2
  const g = ctx.createRadialGradient(c, c, 0, c, c, c)
  g.addColorStop(0, 'rgba(255,255,255,1)')
  g.addColorStop(0.35, 'rgba(255,255,255,0.9)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, S, S)
  return new THREE.CanvasTexture(canvas)
}

function createGlowTexture() {
  const S = 256
  const canvas = document.createElement('canvas')
  canvas.width = S
  canvas.height = S
  const ctx = canvas.getContext('2d')
  const c = S / 2
  const g = ctx.createRadialGradient(c, c, 0, c, c, c)
  g.addColorStop(0, 'rgba(255,255,255,0.9)')
  g.addColorStop(0.3, 'rgba(255,255,255,0.35)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, S, S)
  return new THREE.CanvasTexture(canvas)
}

/** 木星条纹贴图 */
function createJupiterTexture() {
  const W = 128
  const H = 64
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')
  const bands = ['#c8b088', '#e0d3b8', '#a8865c', '#d9c7a0', '#b39a72', '#e6dcc8', '#c09a6e', '#d3c2a2']
  const rnd = srand(31)
  let y = 0
  let i = 0
  while (y < H) {
    const bh = 3 + rnd() * 9
    ctx.fillStyle = bands[i % bands.length]
    ctx.fillRect(0, Math.floor(y), W, Math.ceil(bh))
    i++
    y += bh
  }
  // 噪声扰动
  ctx.globalAlpha = 0.25
  for (let k = 0; k < 260; k++) {
    ctx.fillStyle = rnd() > 0.5 ? 'rgba(90,60,30,0.5)' : 'rgba(255,245,225,0.5)'
    ctx.fillRect(Math.floor(rnd() * W), Math.floor(rnd() * H), 1 + Math.floor(rnd() * 3), 1)
  }
  ctx.globalAlpha = 1
  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

// ================= 星空 / 银河 / 星云 / 穿越拖尾 / 太阳系 =================

function createStars(count, radiusMin, radiusMax) {
  const geo = new THREE.BufferGeometry()
  const pos = new Float32Array(count * 3)
  const col = new Float32Array(count * 3)
  for (let i = 0; i < count; i++) {
    const r = radiusMin + Math.random() * (radiusMax - radiusMin)
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)
    pos[i * 3] = r * Math.sin(phi) * Math.cos(theta)
    pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
    pos[i * 3 + 2] = r * Math.cos(phi)
    const t = Math.random()
    col[i * 3] = t < 0.7 ? 1 : t < 0.9 ? 0.88 : 0.97
    col[i * 3 + 1] = t < 0.7 ? 1 : t < 0.9 ? 0.92 : 0.98
    col[i * 3 + 2] = t < 0.7 ? 1 : 1
  }
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3))
  const mat = new THREE.PointsMaterial({
    size: 1.7,
    sizeAttenuation: false, // 固定像素尺寸：远距离星点不再亚像素闪烁（避免一闪一闪）
    vertexColors: true,
    transparent: true,
    opacity: 1,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  return new THREE.Points(geo, mat)
}

/** 银河带：倾斜的密集星带（细碎深空，不杂乱） */
function createGalaxyBand(count) {
  const geo = new THREE.BufferGeometry()
  const pos = new Float32Array(count * 3)
  const col = new Float32Array(count * 3)
  const tilt = (35 * Math.PI) / 180
  const cosT = Math.cos(tilt)
  const sinT = Math.sin(tilt)
  for (let i = 0; i < count; i++) {
    const r = 55 + Math.random() * 75
    const theta = Math.random() * Math.PI * 2
    const bandW = (Math.random() - 0.5) * 14
    const x = r * Math.cos(theta)
    const z = r * Math.sin(theta)
    const y = bandW
    pos[i * 3] = x
    pos[i * 3 + 1] = y * cosT - z * sinT
    pos[i * 3 + 2] = y * sinT + z * cosT
    const t = Math.random()
    col[i * 3] = t < 0.6 ? 0.88 : 0.98
    col[i * 3 + 1] = t < 0.6 ? 0.93 : 0.98
    col[i * 3 + 2] = 1
  }
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3))
  const mat = new THREE.PointsMaterial({
    size: 2.0,
    sizeAttenuation: false,
    vertexColors: true,
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  return new THREE.Points(geo, mat)
}

/** 开场星云粒子：大而柔的彩色光斑，集中在镜头前进方向（抵达后淡出） */
function createNebula(count) {
  const group = new THREE.Group()
  const glowTex = createGlowTexture()
  const palette = [
    new THREE.Color('#3a6bd8'),
    new THREE.Color('#2e5aa8'),
    new THREE.Color('#6a4fc9'),
    new THREE.Color('#2f9db8'),
    new THREE.Color('#a03a7a'),
    new THREE.Color('#355ec4'),
  ]
  const rnd = srand(777)
  for (let i = 0; i < count; i++) {
    const r = 55 + rnd() * 55
    const theta = rnd() * Math.PI * 2
    const phi = Math.acos(Math.sqrt(rnd())) // 偏向 +z 半球（镜头前进方向）
    const x = r * Math.sin(phi) * Math.cos(theta)
    const y = (rnd() - 0.5) * 34
    const z = r * Math.cos(phi)
    const color = palette[Math.floor(rnd() * palette.length)]
    const baseOp = 0.05 + rnd() * 0.08
    const m = new THREE.SpriteMaterial({
      map: glowTex,
      color,
      transparent: true,
      opacity: baseOp,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    const s = new THREE.Sprite(m)
    s.userData.baseOp = baseOp
    const sc = 16 + rnd() * 44
    s.scale.set(sc, sc, 1)
    s.position.set(x, y, z)
    group.add(s)
  }
  return group
}

/** 光粒穿越：细碎星光化作高速光粒流（短尾星芒，尺寸随 uWarp 拉伸，随旅程强度收缩/淡出） */
function createWarpStars(count) {
  const geo = new THREE.BufferGeometry()
  const pos = new Float32Array(count * 3)
  const sizes = new Float32Array(count)
  const hues = new Float32Array(count)
  for (let i = 0; i < count; i++) {
    const r = 12 + Math.random() * 80
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)
    pos[i * 3] = r * Math.sin(phi) * Math.cos(theta)
    pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.6
    pos[i * 3 + 2] = r * Math.cos(phi) - 20
    sizes[i] = 0.35 + Math.random() * 0.9
    hues[i] = Math.random()
  }
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  geo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1))
  geo.setAttribute('aHue', new THREE.BufferAttribute(hues, 1))

  const mat = new THREE.ShaderMaterial({
    uniforms: { uWarp: { value: 0 } },
    vertexShader: `
      attribute float aSize;
      attribute float aHue;
      uniform float uWarp;
      varying vec2 vDir;
      varying float vHue;
      void main() {
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vec4 p = projectionMatrix * mv;
        vDir = normalize(p.xy);
        vHue = aHue;
        gl_PointSize = aSize * (340.0 / max(-mv.z, 0.1)) * (0.4 + 1.15 * uWarp);
        gl_Position = p;
      }
    `,
    fragmentShader: `
      uniform float uWarp;
      varying vec2 vDir;
      varying float vHue;
      void main() {
        vec2 c = gl_PointCoord - 0.5;
        float along = dot(c, vDir);
        float perp = length(c - vDir * along);
        float line = smoothstep(0.06, 0.0, abs(perp));
        float fade = smoothstep(0.38, 0.04, abs(along));
        float core = smoothstep(0.05, 0.0, abs(perp)) * smoothstep(0.06, 0.0, abs(along));
        float a = (line * fade * 1.15 + core * 0.95) * uWarp;
        if (a < 0.01) discard;
        vec3 base = vec3(0.82, 0.92, 1.0);
        vec3 cyan = vec3(0.5, 0.96, 1.0);
        vec3 violet = vec3(0.88, 0.78, 1.0);
        vec3 col = mix(base, cyan, smoothstep(0.68, 0.7, vHue));
        col = mix(col, violet, smoothstep(0.9, 0.92, vHue));
        // 高速色散：沿拖尾方向轻微红/蓝分裂，科幻拉满
        float disp = uWarp * 0.5;
        col.r += disp * 0.25 * smoothstep(0.0, 0.5, along);
        col.b += disp * 0.25 * smoothstep(0.0, -0.5, along);
        gl_FragColor = vec4(col, a);
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  return new THREE.Points(geo, mat)
}

/** 太阳：高亮球体 + 炽白核心 + 双层光晕（飞掠时靠 UnrealBloom 泛光，掠过地球后淡出） */
function createSun() {
  const group = new THREE.Group()
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(1.5, 48, 48),
    new THREE.MeshBasicMaterial({ color: 0xfff6d8, transparent: true, depthWrite: false }),
  )
  mesh.userData.baseOp = 1
  mesh.position.set(8, 3.2, 20) // 位于旋转进入弧线的内侧，镜头绕飞时掠过眼前
  group.add(mesh)
  sunCoreMesh = mesh

  const hot = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: createGlowTexture(),
      color: 0xffffff,
      transparent: true,
      opacity: 0.9,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  )
  hot.userData.baseOp = 0.9
  hot.scale.set(5, 5, 1)
  hot.position.copy(mesh.position)
  group.add(hot)

  const glow = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: createGlowTexture(),
      color: 0xffd27f,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  )
  glow.userData.baseOp = 0.85
  glow.scale.set(10, 10, 1)
  glow.position.copy(mesh.position)
  group.add(glow)

  const corona = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: createGlowTexture(),
      color: 0xff9d4d,
      transparent: true,
      opacity: 0.3,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  )
  corona.userData.baseOp = 0.3
  corona.scale.set(18, 18, 1)
  corona.position.copy(mesh.position)
  group.add(corona)
  return group
}

/** 通用行星：球体 + 柔光晕，作为过渡元素（淡出窗口 fadeStart→fadeEnd） */
function createPlanet(radius, color, map, position, fadeStart, fadeEnd) {
  const group = new THREE.Group()
  const mat = new THREE.MeshPhongMaterial({
    color,
    map,
    transparent: true,
    opacity: 1,
    depthWrite: true,
  })
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, 40, 40), mat)
  mesh.position.copy(position)
  group.add(mesh)

  const glow = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: createGlowTexture(),
      color,
      transparent: true,
      opacity: 0.18,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  )
  glow.scale.set(radius * 2.6, radius * 2.6, 1)
  glow.position.copy(position)
  group.add(glow)

  planetItems.push({
    group,
    parts: [
      { mat, baseOp: 1 },
      { mat: glow.material, baseOp: 0.18 },
    ],
    mesh,
    fadeStart,
    fadeEnd,
  })
  return group
}

/** 行星公转微光轨迹：行星身后一段淡色弧线光轨（缓慢淡出） */
function createOrbitTrail(position, color) {
  // 以原点为中心的弧线（行星大致沿径向分布，轨迹取与行星同方位的短弧）
  const dir = position.clone().normalize()
  const points = []
  const segs = 24
  for (let i = 0; i <= segs; i++) {
    const ang = (i / segs) * 0.9 - 0.45 // ±0.45 弧度
    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), ang)
    points.push(dir.clone().applyQuaternion(q).multiplyScalar(position.length() * 1.02))
  }
  const geo = new THREE.BufferGeometry().setFromPoints(points)
  const mat = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  const line = new THREE.Line(geo, mat)
  scene.add(line)
  orbitTrails.push({ line, mat, baseOp: 0.35 })
  return line
}

/** 落地扩散波纹：抵达地球瞬间，全屏一圈淡蓝色扩散波纹（面向相机的 billboard 环） */
function spawnLandingRipple() {
  if (landingRipple) return
  const geo = new THREE.RingGeometry(0.2, 0.28, 64)
  const mat = new THREE.MeshBasicMaterial({
    color: 0x6fc8ff,
    transparent: true,
    opacity: 0.6,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  landingRipple = new THREE.Mesh(geo, mat)
  landingRipple.position.copy(camera.position).add(
    new THREE.Vector3(0, 0, -3).applyQuaternion(camera.quaternion),
  )
  landingRipple.quaternion.copy(camera.quaternion)
  scene.add(landingRipple)
  landingRippleT = 1.2
}

// ================= 场景构建 =================

function buildScene() {
  const el = mount.value
  const w = el.clientWidth || 600
  const h = el.clientHeight || 600

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(w, h)
  renderer.setClearColor(0x000000, 1) // 纯黑背景，突出星空/星系/拖尾对比
  el.appendChild(renderer.domElement)

  scene = new THREE.Scene()

  camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 400)
  if (props.background) {
    camera.position.set(0, 0.9, 11)
  } else if (props.intro) {
    camera.position.set(30, 40, 150) // 宇宙深处起点
  } else {
    camera.position.copy(FINAL_CAM)
  }
  prevCamPos.copy(camera.position)

  // 灯光：环境光压低（保留昼夜对比）+ 主日光 + 冷色补光
  scene.add(new THREE.AmbientLight(0x6f8cb8, 0.5))
  const sunLight = new THREE.DirectionalLight(0xffffff, 2.1)
  sunLight.position.set(6, 3, 6)
  scene.add(sunLight)
  const fill = new THREE.DirectionalLight(0x4a6a9a, 0.3)
  fill.position.set(-6, -1, -4)
  scene.add(fill)
  scene.add(new THREE.HemisphereLight(0x9fc4e8, 0x0c1c30, 0.6))

  // 深空静态星星 + 银河带（始终在）
  scene.add(createStars(props.starCount, 40, 120))
  scene.add(createGalaxyBand(2600))
  // 记录星点材质，用于轻微呼吸（稳定不闪，仅做极轻微的明暗起伏，呈现“活着”的星空）
  starMats.length = 0
  scene.traverse((o) => {
    if (o.isPoints && o.material && o.material.isPointsMaterial) starMats.push(o.material)
  })

  if (!props.background) {
    // 开场星云粒子（抵达后淡出）
    nebulaGroup = createNebula(240)
    scene.add(nebulaGroup)

    // 穿越光粒流（细碎星光高速流过，强度随镜头速度增强）
    warpStars = createWarpStars(5000)
    warpStars.material.uniforms.uWarp.value = 0
    scene.add(warpStars)

    // 太阳系过渡元素：太阳 + 木星/火星/金星/水星（沿旋转弧线依次掠过并淡出）
    sunGroup = createSun()
    scene.add(sunGroup)
    planetItems = []
    orbitTrails = []
    scene.add(createPlanet(1.05, 0xc8b088, createJupiterTexture(), new THREE.Vector3(26, 5.5, 44), 0.3, 0.44))
    scene.add(createPlanet(0.45, 0xc96a4a, null, new THREE.Vector3(20, 3.5, 32), 0.42, 0.56))
    scene.add(createPlanet(0.6, 0xe8d9a8, null, new THREE.Vector3(4, 2.8, 22), 0.55, 0.7))
    scene.add(createPlanet(0.3, 0xa8a39a, null, new THREE.Vector3(-5, 2.4, 14), 0.66, 0.8))
    // 行星公转微光轨迹
    createOrbitTrail(new THREE.Vector3(26, 5.5, 44), 0xc8b088)
    createOrbitTrail(new THREE.Vector3(20, 3.5, 32), 0xc96a4a)
    createOrbitTrail(new THREE.Vector3(4, 2.8, 22), 0xe8d9a8)
    createOrbitTrail(new THREE.Vector3(-5, 2.4, 14), 0xa8a39a)
  }

  // 地球组（自转）
  earthGroup = new THREE.Group()
  scene.add(earthGroup)

  // 地球本体：自定义昼夜 Shader（昼侧地表 + 夜侧城市灯光 + 晨昏带橙红暮光 + 海洋高光）
  const earthGeo = new THREE.SphereGeometry(EARTH_R, 160, 160)
  const earthMat = makeEarthMaterial(createEarthTexture(), createNightTexture())
  earthMat.uniforms.opacity.value = 0 // 开场穿越段完全不可见，抵达前随 reveal 渐显
  earthMesh = new THREE.Mesh(earthGeo, earthMat)
  earthGroup.add(earthMesh)

  // 云层：双层（高空薄云快流 + 低空厚云慢漂，fbm 扰动轮廓由贴图内置）
  const cloudHiGeo = new THREE.SphereGeometry(EARTH_R * 1.022, 96, 96)
  const cloudHiMat = new THREE.MeshPhongMaterial({
    map: createCloudTexture(),
    transparent: true,
    opacity: 0,
    depthWrite: false,
    blending: THREE.NormalBlending,
  })
  cloudMesh = new THREE.Mesh(cloudHiGeo, cloudHiMat) // 高空薄云（快）
  earthGroup.add(cloudMesh)

  const cloudLoGeo = new THREE.SphereGeometry(EARTH_R * 1.012, 96, 96)
  const cloudLoMat = new THREE.MeshPhongMaterial({
    map: createCloudTexture(),
    transparent: true,
    opacity: 0,
    depthWrite: false,
    blending: THREE.NormalBlending,
  })
  cloudLoMesh = new THREE.Mesh(cloudLoGeo, cloudLoMat) // 低空厚云（慢）
  earthGroup.add(cloudLoMesh)

  // 大气层：三层叠加（内层紧贴边缘蓝光 + 中层散射体积光 + 外层极光环）
  atmoMeshes = []
  const atmoInner = new THREE.Mesh(
    new THREE.SphereGeometry(EARTH_R * 1.035, 96, 96),
    makeAtmosphereMaterial(new THREE.Color('#4cc0ff'), 2.0, 2.6),
  )
  atmoInner.userData.baseI = 2.0
  atmoMeshes.push(atmoInner)
  earthGroup.add(atmoInner)

  // 中层散射大气（半透淡蓝体积光，随视角变化透明度）
  const atmoScatter = new THREE.Mesh(
    new THREE.SphereGeometry(EARTH_R * 1.08, 96, 96),
    makeAtmosphereMaterial(new THREE.Color('#6fb6ff'), 0.85, 3.4),
  )
  atmoScatter.userData.baseI = 0.85
  atmoMeshes.push(atmoScatter)
  earthGroup.add(atmoScatter)

  // 外层极光环（南北极动态流动光带，绿紫渐变）
  auroraMesh = new THREE.Mesh(
    new THREE.SphereGeometry(EARTH_R * 1.12, 96, 96),
    makeAuroraMaterial(),
  )
  earthGroup.add(auroraMesh)

  // 新闻点位
  rebuildPoints()
  rebuildFlightLines()
  rebuildHeatmap()

  // 后期：可插拔 composer 管线（RenderPass → SMAA → 分层 Bloom → OutputPass）
  buildComposer(w, h)

  // 交互控制：开场期间禁用
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.minDistance = 3.2
  controls.maxDistance = 10
  controls.enablePan = false
  controls.rotateSpeed = 0.45
  controls.enabled = props.background ? false : !props.intro && props.interactive

  // 拖拽暂停自转，松手后恢复
  controls.addEventListener('start', () => {
    autoPaused = true
    clearTimeout(resumeTimer)
  })
  controls.addEventListener('end', () => {
    clearTimeout(resumeTimer)
    resumeTimer = setTimeout(() => {
      autoPaused = false
    }, 2200)
  })

  // 指针交互（pointerdown/up 判定点击，pointermove 驱动 hover）
  const dom = renderer.domElement
  dom.addEventListener('pointerdown', onPointerDown)
  dom.addEventListener('pointerup', onPointerUp)
  dom.addEventListener('pointermove', onPointerMove)
  dom.addEventListener('pointerleave', onPointerLeave)
  dom.addEventListener('dblclick', onDblClick)
  dom.style.cursor = 'grab'

  // 旅程路径：深空 → 光粒穿越 → 旋转进入太阳系 → 穿越行星 → 地球前方（距表面约 2.8 单位）
  journeyCurve = new THREE.CatmullRomCurve3(
    [
      new THREE.Vector3(30, 40, 150), // ① 宇宙深处（极远起点）
      new THREE.Vector3(28, 18, 100), // ② 光粒穿越中段
      new THREE.Vector3(26, 8, 62), //   接近太阳系外围（木星一侧）
      new THREE.Vector3(28, 5, 36), //  ③ 太阳系外围，准备旋转入场
      new THREE.Vector3(16, 3, 26), //  ④ 旋转进入太阳系（弧线起点）
      new THREE.Vector3(2, 3.5, 23), //   弧线滑行（太阳在视野中央侧）
      new THREE.Vector3(-8, 2.5, 15), //  弧线结束（金星/水星一侧）
      new THREE.Vector3(0, 1.6, 8.5), // ⑤ 近地轨道外
      FINAL_CAM.clone(), //             抵达地球
    ],
    false,
    'catmullrom',
    0.5,
  )

  clock = new THREE.Clock()

  // 尝试加载真实 NASA 地球/云层贴图（失败自动保留程序化贴图）
  tryUpgradeTextures()

  resizeObserver = new ResizeObserver(() => resize())
  resizeObserver.observe(el)
}

// ================= 后期渲染管线（可插拔） =================
/**
 * 管线顺序：RenderPass → SMAA → 分层 Bloom → Bokeh(DOF) → Afterimage(运动模糊) → FilmGrain → OutputPass
 * - 大屏(high)：开 SMAA + Bloom + Bokeh + Afterimage(仅高速) + FilmGrain + Output
 * - 低端/移动(low)：跳过 SMAA/Bokeh/Afterimage/Film，Bloom 收敛，保帧率
 */
function buildComposer(w, h) {
  const low = isLowQuality()

  composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))

  // SMAA 超抗锯齿：替换默认 MSAA，文字/线条边缘无锯齿（大屏清晰）
  if (!low) {
    smaaPass = new SMAAPass(w, h)
    composer.addPass(smaaPass)
  }

  // 分层收敛 Bloom：threshold 提高到 0.85，只让高亮元素（太阳/大气边缘/新闻点）泛光，
  // 星空、地球本体不再整屏发白；strength 收敛到 0.75
  bloomPass = new UnrealBloomPass(new THREE.Vector2(w, h), low ? 0.5 : 0.75, 0.6, low ? 0.6 : 0.85)
  composer.addPass(bloomPass)

  // Bokeh 景深（大屏）：开场聚焦太阳系元素、抵达后聚焦地球主体，远处星空轻微虚化
  if (!low) {
    bokehPass = new BokehPass(scene, camera, { focus: 4.78, aperture: 0.0006, maxblur: 0.006 })
    bokehPass.enabled = false // 默认关闭，抵达地球后开启（由 animate 控制）
    composer.addPass(bokehPass)
  }

  // Afterimage 运动模糊：高速穿越阶段自动开启（由 animate 控制 damp），抵达后关闭
  if (!low) {
    afterimagePass = new AfterimagePass(0.0)
    afterimagePass.enabled = false
    composer.addPass(afterimagePass)
  }

  // FilmGrain 胶片颗粒：微弱电影噪点，弱化 WebGL 数码廉价感（大屏默认开弱）
  if (!low) {
    filmPass = new FilmPass(0.18, false)
    composer.addPass(filmPass)
  }

  // OutputPass：负责色彩空间转换 + 色调映射（sRGB），放在最后保证观感正确
  outputPass = new OutputPass()
  composer.addPass(outputPass)
}

function makeAtmosphereMaterial(color, intensity, power) {
  return new THREE.ShaderMaterial({
    uniforms: {
      glowColor: { value: color },
      intensity: { value: intensity },
      power: { value: power },
    },
    vertexShader: `
      varying vec3 vNormal;
      varying vec3 vViewDir;
      void main() {
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vNormal = normalize(normalMatrix * normal);
        vViewDir = normalize(-mv.xyz);
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: `
      uniform vec3 glowColor;
      uniform float intensity;
      uniform float power;
      varying vec3 vNormal;
      varying vec3 vViewDir;
      void main() {
        float rim = 1.0 - abs(dot(normalize(vNormal), normalize(vViewDir)));
        float a = pow(rim, power) * intensity;
        gl_FragColor = vec4(glowColor, a);
      }
    `,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false,
  })
}

/** 地球昼夜 Shader：昼侧地表 + 夜侧城市灯光 + 晨昏带橙红暮光 + 海洋高光 */
function makeEarthMaterial(dayTex, nightTex) {
  return new THREE.ShaderMaterial({
    uniforms: {
      dayMap: { value: dayTex },
      nightMap: { value: nightTex },
      sunDir: { value: SUN_DIR.clone() },
      uTime: { value: 0 },
      opacity: { value: 0 },
      // 城市灯光呼吸
      cityPulse: { value: 1.0 },
    },
    vertexShader: `
      varying vec2 vUv;
      varying vec3 vWorldNormal;
      void main() {
        vUv = uv;
        vWorldNormal = normalize(mat3(modelMatrix) * normal);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D dayMap;
      uniform sampler2D nightMap;
      uniform vec3 sunDir;
      uniform float uTime;
      uniform float opacity;
      uniform float cityPulse;
      varying vec2 vUv;
      varying vec3 vWorldNormal;
      void main() {
        vec3 n = normalize(vWorldNormal);
        // 昼夜因子：朝太阳一侧为正（昼），背阳为负（夜）
        float d = dot(n, normalize(sunDir));
        float day = smoothstep(-0.18, 0.22, d); // 平滑晨昏分割线
        vec3 dayCol = texture2D(dayMap, vUv).rgb;
        vec3 nightCol = texture2D(nightMap, vUv).rgb * cityPulse;
        // 晨昏带橙红暮光过渡
        float twilight = 1.0 - abs(d) * 4.0;
        twilight = clamp(twilight, 0.0, 1.0) * (1.0 - day) * 0.0; // 占位（暮光以 add 叠加）
        vec3 twiCol = vec3(1.0, 0.45, 0.22) * max(0.0, (1.0 - abs(d) * 5.0)) * 0.6 * (1.0 - day);
        vec3 col = mix(nightCol, dayCol, day) + twiCol;
        // 海洋高光（夜侧偏暗，昼侧根据法线有微弱反光）
        gl_FragColor = vec4(col, opacity);
      }
    `,
    transparent: true,
    depthWrite: false,
  })
}

/** 外层极光环：南北极动态流动光带（绿紫渐变，缓慢飘动） */
function makeAuroraMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      glowColorA: { value: new THREE.Color('#5cff9d') }, // 极光绿
      glowColorB: { value: new THREE.Color('#9d7bff') }, // 极光紫
      opacity: { value: 0 }, // 随 reveal 渐显
    },
    vertexShader: `
      varying vec3 vNormal;
      varying vec3 vPos;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        vPos = position;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform vec3 glowColorA;
      uniform vec3 glowColorB;
      uniform float opacity;
      varying vec3 vNormal;
      varying vec3 vPos;
      // 简单噪声
      float hash(vec3 p){ return fract(sin(dot(p, vec3(12.9898,78.233,37.719)))*43758.5453); }
      float noise(vec3 p){
        vec3 i = floor(p); vec3 f = fract(p);
        f = f*f*(3.0-2.0*f);
        float n = mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),
                          mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
                      mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),
                          mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);
        return n;
      }
      void main() {
        vec3 n = normalize(vNormal);
        float rim = pow(1.0 - abs(n.y), 3.0); // 极区（y 接近 ±1）才亮
        float lat = abs(normalize(vPos).y);
        float band = smoothstep(0.62, 0.92, lat); // 南北纬 60°~90° 极光带
        float flow = noise(vec3(normalize(vPos).x*6.0 + uTime*0.15, normalize(vPos).z*6.0, uTime*0.1));
        float a = band * rim * (0.35 + flow * 0.65) * opacity;
        vec3 col = mix(glowColorA, glowColorB, flow);
        gl_FragColor = vec4(col, a);
      }
    `,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false,
  })
}

/** 尝试加载真实 NASA 贴图（unpkg → jsdelivr → GitHub raw 三路兜底），失败则保留程序化贴图。
 *  注：地球已切换为自定义昼夜 Shader（自带 dayMap/nightMap uniforms），不再支持 Phong 的 map/emissiveMap/bumpMap，
 *  故 earth 相关升级在此跳过，仅保留云层 NASA 升级（云层仍为 Phong）。 */
function tryUpgradeTextures() {
  if (!earthMesh || !cloudMesh) return
  // 地球为 ShaderMaterial 时，跳过 earth map/emissiveMap/bumpMap/specularMap 升级（避免写入不存在的属性报错）
  const loader = new THREE.TextureLoader()
  loader.setCrossOrigin('anonymous')

  const loadWithFallback = (urls, apply) => {
    const tryNext = (i) => {
      if (i >= urls.length) return
      loader.load(
        urls[i],
        (tex) => {
          tex.colorSpace = THREE.SRGBColorSpace
          tex.anisotropy = 8
          apply(tex)
        },
        undefined,
        () => tryNext(i + 1),
      )
    }
    tryNext(0)
  }

  // 白昼地表（蓝大理石）
  // 地球昼侧贴图（ShaderMaterial 的 dayMap uniform；若为传统 Phong 则走 map）
  loadWithFallback(
    [
      'https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg',
      'https://cdn.jsdelivr.net/npm/three-globe/example/img/earth-blue-marble.jpg',
      'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_atmos_2048.jpg',
      'https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_atmos_2048.jpg',
    ],
    (tex) => {
      if (earthMesh.material.uniforms && earthMesh.material.uniforms.dayMap) {
        const old = earthMesh.material.uniforms.dayMap.value
        earthMesh.material.uniforms.dayMap.value = tex
        if (old && old !== tex) old.dispose()
      } else if (earthMesh.material.map !== undefined) {
        earthMesh.material.map = tex
        earthMesh.material.needsUpdate = true
      }
    },
  )

  // 云层（透明层，Phong）
  loadWithFallback(
    [
      'https://unpkg.com/three-globe/example/img/earth-clouds.png',
      'https://cdn.jsdelivr.net/npm/three-globe/example/img/earth-clouds.png',
      'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_clouds_1024.png',
      'https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_clouds_1024.png',
    ],
    (tex) => {
      const old = cloudMesh.material.map
      cloudMesh.material.map = tex
      cloudMesh.material.needsUpdate = true
      if (old && old !== tex) old.dispose()
    },
  )

  // 夜间城市灯光（ShaderMaterial 的 nightMap uniform；替换程序化夜灯）
  loadWithFallback(
    [
      'https://unpkg.com/three-globe/example/img/earth-night.jpg',
      'https://cdn.jsdelivr.net/npm/three-globe/example/img/earth-night.jpg',
      'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_lights_2048.png',
      'https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_lights_2048.png',
    ],
    (tex) => {
      if (earthMesh.material.uniforms && earthMesh.material.uniforms.nightMap) {
        const old = earthMesh.material.uniforms.nightMap.value
        earthMesh.material.uniforms.nightMap.value = tex
        if (old && old !== tex) old.dispose()
      } else if (earthMesh.material.emissiveMap !== undefined) {
        earthMesh.material.emissiveMap = tex
        earthMesh.material.emissiveIntensity = 0.85
        earthMesh.material.needsUpdate = true
      }
    },
  )
  // 注：地形 bumpMap / 海洋 specularMap 为 Phong 专属，ShaderMaterial 暂不支持，留待后续 Shader 内实现
}

// ================= 新闻点位（统一蓝青脉冲点，深度检测防穿透） =================

function rebuildPoints() {
  if (!earthGroup) return
  for (const p of pointItems) {
    earthGroup.remove(p.group)
    p.core.material.dispose()
    if (p.halo) p.halo.material.dispose()
  }
  pointItems = []

  const dotTex = createDotTexture()
  const glowTex = createGlowTexture()

  for (let i = 0; i < props.points.length; i++) {
    const pt = props.points[i]
    const v = latLngToVector3(pt.lat, pt.lng, EARTH_R + 0.015)
    const group = new THREE.Group()
    group.position.set(v.x, v.y, v.z)
    group.lookAt(0, 0, 0)

    // 不同国家/地区不同发光色（按地区 id 稳定分配）；尺寸缩小、仅受强度微调
    const color = colorForPoint(pt, i)
    const base = 0.045 + (pt.intensity || 1) * 0.012

    // 中心发光圆点（实心高亮核）
    const core = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: dotTex,
        color,
        transparent: true,
        opacity: 0.95,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        depthTest: true, // 关键修复：被地球遮挡的部分直接不渲染
      }),
    )
    core.scale.set(base, base, 1)

    // 静态微光晕（不扩散，只增强"发光圆点"质感）
    const halo = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: glowTex,
        color,
        transparent: true,
        opacity: 0.22,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        depthTest: true,
      }),
    )
    halo.scale.set(base * 2.0, base * 2.0, 1)

    group.add(core)
    group.add(halo)

    // 垂直光柱（从地表向外射出的细光柱，强度 = 新闻 count）
    const beamH = 0.25 + (pt.intensity || 1) * 0.18
    const beamGeo = new THREE.CylinderGeometry(0.012, 0.02, beamH, 8, 1, true)
    beamGeo.translate(0, beamH / 2, 0) // 底部贴地表
    const beamMat = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    })
    const beam = new THREE.Mesh(beamGeo, beamMat)
    beam.rotation.x = -Math.PI / 2 // 默认沿 +Y，旋转到沿球面法线（group 已 lookAt 原点，故本地 +Z 为法线；改为沿 +Z）
    beam.rotation.set(0, 0, 0)
    beam.position.set(0, 0, 0.015)
    group.add(beam)
    beamItems.push({ mesh: beam, mat: beamMat, baseOp: 0.35 + (pt.intensity || 1) * 0.12, intensity: pt.intensity || 1 })

    earthGroup.add(group)

    pointItems.push({
      group,
      core,
      halo,
      base,
      phase: (i * 0.37) % (Math.PI * 2),
      intensity: pt.intensity || 1,
      data: pt,
    })
  }
}

/** 全球新闻飞线：同大类新闻在球面间生成弧形流光飞线（按 category 配色，单向流动光点） */
function rebuildFlightLines() {
  for (const f of flightLines) {
    if (f.line.parent) f.line.parent.remove(f.line)
    f.line.geometry.dispose()
    f.mat.dispose()
  }
  flightLines = []
  if (!earthGroup || !props.points.length) return

  // 按大类分组，组内有 >=2 个点则两两相连（限制数量避免过密）
  const byCat = {}
  for (const pt of props.points) {
    const c = flyColorFor(pt.region || pt)
    ;(byCat[c] ||= []).push(pt)
  }
  let count = 0
  for (const c of Object.keys(byCat)) {
    const list = byCat[c]
    for (let a = 0; a < list.length && count < 60; a++) {
      for (let b = a + 1; b < list.length && count < 60; b++) {
        const oa = latLngToVector3(list[a].lat, list[a].lng, EARTH_R + 0.02)
        const ob = latLngToVector3(list[b].lat, list[b].lng, EARTH_R + 0.02)
        const pa = new THREE.Vector3(oa.x, oa.y, oa.z)
        const pb = new THREE.Vector3(ob.x, ob.y, ob.z)
        const mid = pa.clone().add(pb).multiplyScalar(0.5)
        const dist = pa.distanceTo(pb)
        mid.normalize().multiplyScalar(EARTH_R + 0.02 + dist * 0.6) // 弧高随距离
        const curve = new THREE.QuadraticBezierCurve3(pa, mid, pb)
        const geo = new THREE.BufferGeometry().setFromPoints(curve.getPoints(40))
        const mat = new THREE.LineBasicMaterial({
          color: new THREE.Color(c),
          transparent: true,
          opacity: 0,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        })
        const line = new THREE.Line(geo, mat)
        earthGroup.add(line)
        flightLines.push({ line, mat, baseOp: 0.4, category: c })
        count++
      }
    }
  }
}

/** 全球热力层：基于 intensity 的高斯热力贴图覆盖地球表层（新闻多区域橙红热斑更亮） */
function rebuildHeatmap() {
  if (heatmapMesh) {
    earthGroup.remove(heatmapMesh)
    heatmapMesh.geometry.dispose()
    heatmapMesh.material.dispose()
    heatmapMesh = null
  }
  if (!props.points.length) return
  const W = 1024
  const H = 512
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, W, H)
  for (const pt of props.points) {
    const x = ((pt.lng + 180) / 360) * W
    const y = ((90 - pt.lat) / 180) * H
    const r = 26 + (pt.intensity || 1) * 14
    const g = ctx.createRadialGradient(x, y, 0, x, y, r)
    g.addColorStop(0, 'rgba(255,120,60,0.85)')
    g.addColorStop(0.5, 'rgba(255,90,40,0.4)')
    g.addColorStop(1, 'rgba(255,60,30,0)')
    ctx.fillStyle = g
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fill()
  }
  const tex = new THREE.CanvasTexture(canvas)
  tex.colorSpace = THREE.SRGBColorSpace
  const mat = new THREE.MeshBasicMaterial({
    map: tex,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  heatmapMesh = new THREE.Mesh(new THREE.SphereGeometry(EARTH_R * 1.005, 96, 96), mat)
  earthGroup.add(heatmapMesh)
}

// ================= 工具 =================

function resize() {
  if (!renderer || !mount.value) return
  const w = mount.value.clientWidth || 600
  const h = mount.value.clientHeight || 600
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  renderer.setSize(w, h)
  composer.setSize(w, h)
}

function smoothstep(x) {
  const t = Math.min(1, Math.max(0, x))
  return t * t * (3 - 2 * t)
}

// ---- 指针交互（点击判定走 down/up 距离，最稳） ----

function onPointerDown(e) {
  const rect = renderer.domElement.getBoundingClientRect()
  downPos = { x: e.clientX - rect.left, y: e.clientY - rect.top }
  pointer.x = downPos.x
  pointer.y = downPos.y
  idleTimer = 0 // 用户操作，重置自动漫游计时
}

function onPointerUp(e) {
  if (!downPos) return
  const rect = renderer.domElement.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top
  const dx = x - downPos.x
  const dy = y - downPos.y
  downPos = null
  if (dx * dx + dy * dy > 36) return // 是拖拽，不算点击
  if (!settled()) return
  idleTimer = 0
  const idx = hitTest(x, y)
  if (idx < 0 || !pointItems[idx]) {
    // 点击空白处 → 关闭内容卡
    emit('blank-click')
    return
  }
  // 单击：延迟触发（显示内容卡）；双击由原生 dblclick 事件统一处理（更可靠）
  const data = pointItems[idx].data
  const now = performance.now()
  if (lastClick) clearTimeout(lastClick.timer)
  lastClick = {
    time: now,
    idx,
    timer: setTimeout(() => {
      lastClick = null
      emit('point-click', data)
    }, 260),
  }
}

/** 原生双击事件：浏览器自带双击判定（约 500ms 内两次点击），比自写计时器可靠得多 */
function onDblClick(e) {
  if (!settled()) return
  const rect = renderer.domElement.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top
  const idx = hitTest(x, y)
  if (idx < 0 || !pointItems[idx]) return
  // 取消待发的单击，避免双击时也弹出内容卡
  if (lastClick) {
    clearTimeout(lastClick.timer)
    lastClick = null
  }
  emit('point-dblclick', pointItems[idx].data)
}

function onPointerMove(e) {
  const rect = renderer.domElement.getBoundingClientRect()
  pointer.x = e.clientX - rect.left
  pointer.y = e.clientY - rect.top
}

function onPointerLeave() {
  pointer.x = -9999
  pointer.y = -9999
}

function settled() {
  return props.background || !props.intro || introDone
}

/** 命中检测：只响应朝向相机一侧、且未被地球遮挡的点位（距离阈值 + 背向剔除） */
function hitTest(px, py) {
  if (!renderer || !camera || !pointItems.length) return -1
  const w = renderer.domElement.clientWidth
  const h = renderer.domElement.clientHeight
  const camPos = camera.position
  let found = -1
  let best = 26
  for (let i = 0; i < pointItems.length; i++) {
    const p = pointItems[i]
    p.group.getWorldPosition(_world)
    _dir.copy(camPos).sub(_world)
    if (_world.dot(_dir) <= 0) continue // 背对相机（地球背面自动剔除）
    _ndc.copy(_world).project(camera)
    if (_ndc.z > 1) continue
    const sx = (_ndc.x * 0.5 + 0.5) * w
    const sy = (0.5 - _ndc.y * 0.5) * h
    const dx = sx - px
    const dy = sy - py
    const d = Math.sqrt(dx * dx + dy * dy)
    if (d < best) {
      best = d
      found = i
    }
  }
  return found
}

/** 每帧 hover：驱动 tooltip（仅抵达地球后） */
function updateHover() {
  if (!renderer || !camera || !settled()) return
  const idx = hitTest(pointer.x, pointer.y)
  if (idx !== hoveredIndex) {
    hoveredIndex = idx
    const p = idx >= 0 ? pointItems[idx] : null
    if (p) {
      p.group.getWorldPosition(_world)
      _ndc.copy(_world).project(camera)
      const w = renderer.domElement.clientWidth
      const h = renderer.domElement.clientHeight
      const sx = (_ndc.x * 0.5 + 0.5) * w
      const sy = (0.5 - _ndc.y * 0.5) * h
      emit('point-hover', { point: p.data, x: sx, y: sy })
    } else {
      emit('point-hover', null)
    }
    if (renderer) renderer.domElement.style.cursor = idx >= 0 ? 'pointer' : 'grab'
  }
}

// ---- 动画循环 ----

function easeInCubic(x) {
  return x * x * x
}

/** 分段变速（e 为路径进度 0→1，p 为时间进度 0→1，总时长 14s）：
 *  ① deep (0-0.08)：静默深空，慢起步，仅覆盖 1.2% 路径（速度 < 5，光粒不触发）
 *  ② warp (0.08-0.45)：光粒高速穿越，覆盖 42.8% 路径约 5.2s —— 光粒流强度打满
 *  ③ solar (0.45-0.74)：旋转进入太阳系，沿弧线绕飞滑入（中速，太阳掠近）
 *  ④ planets (0.74-0.90)：穿越木星/火星/金星/水星，行星依次淡出
 *  ⑤ orbit (0.90-1)：平滑减速至静止，抵达近地轨道 */
function journeyEase(p) {
  if (p < 0.08) return 0.012 * easeInCubic(p / 0.08)
  if (p < 0.45) return 0.012 + 0.428 * ((p - 0.08) / 0.37)
  if (p < 0.74) return 0.44 + 0.27 * ((p - 0.45) / 0.29)
  if (p < 0.9) return 0.71 + 0.19 * ((p - 0.74) / 0.16)
  const x = (p - 0.9) / 0.1
  return 0.9 + 0.1 * (2 * x - x * x)
}

/** 阶段：deep 宇宙深处 / warp 光粒穿越 / solar 旋转进入太阳系 / planets 穿越行星 / orbit 近地轨道 */
function stageFromP(p) {
  if (p < 0.08) return 'deep'
  if (p < 0.45) return 'warp'
  if (p < 0.74) return 'solar'
  if (p < 0.9) return 'planets'
  return 'orbit'
}

function animate() {
  if (disposed) return
  raf = requestAnimationFrame(animate)
  const t = clock.getElapsedTime()
  const dt = Math.min(t - lastT, 0.1)
  lastT = t

  // 旅程进度：p（时间）→ e（路径位置，分段变速）
  let p = 1
  let e = 1
  if (props.background) {
    camera.lookAt(0, 0, 0)
  } else if (props.intro && !introDone) {
    p = Math.min(t / JOURNEY_DURATION, 1)
    e = journeyEase(p)
    journeyCurve.getPointAt(e, camera.position)

    // 速度驱动的 warp 拖尾强度（平滑逼近，到达后自然衰减）
    _tmpA.copy(camera.position).sub(prevCamPos)
    const speed = dt > 1e-4 ? _tmpA.length() / dt : 0
    const target = Math.min(1, Math.max(0, (speed - 5) * 0.12))
    warpIntensity += (target - warpIntensity) * Math.min(1, dt * 5)
    if (warpStars) {
      warpStars.material.uniforms.uWarp.value = warpIntensity
      warpStars.visible = warpIntensity > 0.02
    }

    camera.lookAt(0, 0, 0)

    // 阶段事件（驱动外层阶段提示）
    const stage = stageFromP(p)
    if (stage !== lastStage) {
      lastStage = stage
      emit('stage', stage)
    }

    prevCamPos.copy(camera.position)

    if (p >= 1) {
      introDone = true
      controls.enabled = props.interactive
      spawnLandingRipple() // 落地扩散波纹
      emit('ready')
    }
  } else if (props.intro && warpStars) {
    // 抵达近地轨道：拖尾星光淡出
    warpIntensity = Math.max(0, warpIntensity - dt * 1.5)
    warpStars.material.uniforms.uWarp.value = warpIntensity
    warpStars.visible = warpIntensity > 0.02
  }

  // ---- 开场过渡元素淡出（按路径位置 e）----
  if (!props.background) {
    // 星云粒子：深空阶段可见，进入 warp 后淡出
    if (nebulaGroup) {
      const nf = 1 - smoothstep((e - 0.08) / 0.4)
      nebulaGroup.visible = nf > 0.02
      nebulaGroup.children.forEach((s) => {
        s.material.opacity = (s.userData.baseOp ?? 0.06) * nf
      })
    }
    // 太阳：旋转进入段可见（e≈0.55 在弧线中央），穿越行星段（e>0.72）后淡出
    if (sunGroup) {
      const sf = 1 - smoothstep((e - 0.72) / 0.14)
      sunGroup.visible = sf > 0.02
      sunGroup.traverse((obj) => {
        if (obj.material && obj.userData.baseOp != null) {
          obj.material.opacity = obj.userData.baseOp * sf
        }
      })
    }
    // 行星（木星/火星/金星/水星）：按接近顺序依次掠过并淡出
    for (const it of planetItems) {
      const f = 1 - smoothstep((e - it.fadeStart) / (it.fadeEnd - it.fadeStart))
      it.group.visible = f > 0.02
      for (const part of it.parts) part.mat.opacity = part.baseOp * f
      it.mesh.rotation.y += 0.003
    }
  }

  // ---- 抵达后地球自转（拖拽暂停）----
  const isSettled = settled()
  if (isSettled) {
    if (!autoPaused) {
      earthGroup.rotation.y += props.autoRotateSpeed * 0.0016
    }
    if (cloudMesh) cloudMesh.rotation.y += 0.0005 // 高空薄云较快
    if (cloudLoMesh) cloudLoMesh.rotation.y += 0.0002 // 低空厚云较慢
    if (auroraMesh) auroraMesh.material.uniforms.uTime.value = t

    // 自动漫游（大屏无人值守）：无操作 10s 后缓慢自转 + 随机点位镜头飞行
    if (props.autoPlay && !autoPaused && pointItems.length) {
      idleTimer += dt
      if (idleTimer > 10) {
        if (autoPlayTarget == null) {
          autoPlayTarget = Math.floor(Math.random() * pointItems.length)
          const p = pointItems[autoPlayTarget]
          p.group.getWorldPosition(_world)
          const dir = _world.clone().normalize()
          // 镜头飞到该点位正前方
          const target = dir.multiplyScalar(6.2)
          controls && (controls.target.set(0, 0, 0))
          camera.position.lerp(target, Math.min(1, dt * 0.6))
        } else {
          // 3s 后切换下一个点位
          if (idleTimer > 13) {
            autoPlayTarget = null
            idleTimer = 10
          }
        }
      }
    }
  }

  // 太阳核心脉动（光球亮度随时间周期性起伏，日冕同步轻微缩放）
  if (sunCoreMesh) {
    const pulse = 1 + Math.sin(t * 1.6) * 0.04
    sunCoreMesh.scale.setScalar(pulse)
  }

  // 背景群星：极轻微整体呼吸（稳定不闪，仅呈现“活着”的星空）
  if (starMats.length) {
    const breathe = 0.92 + Math.sin(t * 0.35) * 0.08
    for (let i = 0; i < starMats.length; i++) starMats[i].opacity = breathe
  }

  // 后期 Pass 按模式动态开关
  if (afterimagePass) {
    // 高速穿越段开启运动模糊（damp 随速度），其余时段关闭
    const wantBlur = warpIntensity > 0.25
    afterimagePass.enabled = wantBlur
    afterimagePass.uniforms.damp.value = wantBlur ? 0.82 : 0.0
  }
  if (bokehPass) {
    // 抵达地球后开启景深聚焦主体，开场旅程段关闭（避免景深干扰穿越感）
    bokehPass.enabled = isSettled
    bokehPass.uniforms.focus.value = camera.position.distanceTo(new THREE.Vector3(0, 0, 0)) || 4.78
  }

  // 行星公转微光轨迹：仅在太阳系/穿越行星段显示，随 e 淡出
  if (!props.background && orbitTrails.length) {
    const tf = 1 - smoothstep((e - 0.72) / 0.16)
    for (const tr of orbitTrails) {
      tr.line.visible = tf > 0.02
      tr.mat.opacity = tr.baseOp * tf
    }
  }

  // 落地扩散波纹：向外放大并淡出
  if (landingRipple && landingRippleT > 0) {
    landingRippleT -= dt
    const k = 1 - landingRippleT / 1.2
    const s = 1 + k * 26
    landingRipple.scale.setScalar(s)
    landingRipple.material.opacity = Math.max(0, 0.6 * (1 - k))
    landingRipple.position.copy(camera.position).add(
      new THREE.Vector3(0, 0, -3).applyQuaternion(camera.quaternion),
    )
    landingRipple.quaternion.copy(camera.quaternion)
    if (landingRippleT <= 0) {
      scene.remove(landingRipple)
      landingRipple.geometry.dispose()
      landingRipple.material.dispose()
      landingRipple = null
    }
  }

  // ---- 地球渐显：穿越段（前约 6.3s 光粒）完全不可见，之后才开始逐渐清晰 ----
  const reveal = props.background || !props.intro ? 1 : smoothstep((p - 0.45) / 0.5)

  // 地球昼夜 Shader：opacity + 时间 + 城市灯光呼吸
  if (earthMesh) {
    earthMesh.material.uniforms.opacity.value = reveal
    earthMesh.material.uniforms.uTime.value = t
    // 城市灯光呼吸（夜间轻微明暗起伏）
    earthMesh.material.uniforms.cityPulse.value = 0.85 + Math.sin(t * 0.8) * 0.15
  }
  if (cloudMesh) cloudMesh.material.opacity = 0.3 * reveal
  if (cloudLoMesh) cloudLoMesh.material.opacity = 0.18 * reveal
  if (auroraMesh) auroraMesh.material.uniforms.opacity.value = 0.9 * reveal
  for (const m of atmoMeshes) {
    m.material.uniforms.intensity.value = (m.userData.baseI ?? 1.8) * reveal
  }
  for (const pt of pointItems) {
    pt.core.material.opacity = 0.95 * reveal
  }

  // 新闻点位：中心发光圆点稳定发光（轻微明暗呼吸），无发散涟漪
  for (const pt of pointItems) {
    const wave = Math.sin(t * 1.8 + pt.phase) * 0.5 + 0.5
    pt.core.material.opacity = (0.88 + wave * 0.12) * reveal
    pt.halo.material.opacity = (0.16 + wave * 0.1) * reveal
  }

  // 垂直光柱：随 reveal 渐显，强度随新闻数；hover 同区时增强
  for (const b of beamItems) {
    b.mesh.visible = props.showBeams && reveal > 0.02
    const hoverBoost = hoveredIndex >= 0 && pointItems[hoveredIndex] && pointItems[hoveredIndex].intensity === b.intensity ? 1.6 : 1
    b.mat.opacity = b.baseOp * reveal * hoverBoost
  }

  // 全球飞线：随 reveal 渐显，hover 点位时高亮同大类、其余淡化
  const hoverCat = hoveredIndex >= 0 ? flyColorFor(pointItems[hoveredIndex].data.region || pointItems[hoveredIndex].data) : null
  for (const f of flightLines) {
    f.line.visible = props.showFlights && reveal > 0.02
    let op = f.baseOp * reveal * 0.6
    if (hoverCat) op = f.category === hoverCat ? f.baseOp * reveal : f.baseOp * reveal * 0.15
    f.mat.opacity = op
  }

  // 高斯热力层：随 reveal 渐显（默认关闭，由控制面板开启）
  if (heatmapMesh) {
    heatmapMesh.visible = props.showHeatmap && reveal > 0.02
    heatmapMesh.material.opacity = 0.55 * reveal
  }

  controls.update()
  updateHover()
  composer.render()
}

/** 外部调用：强制跳过开场旅程（立即抵达地球终点状态） */
function skipIntro() {
  if (introDone || disposed || !renderer) return
  introDone = true
  camera.position.copy(FINAL_CAM)
  camera.lookAt(0, 0, 0)
  prevCamPos.copy(camera.position)
  if (controls) controls.enabled = props.interactive
  warpIntensity = 0
  if (warpStars) {
    warpStars.material.uniforms.uWarp.value = 0
    warpStars.visible = false
  }
  if (nebulaGroup) nebulaGroup.visible = false
  if (sunGroup) sunGroup.visible = false
  for (const it of planetItems) it.group.visible = false
  spawnLandingRipple()
  // 地球立即全显
  const reveal = 1
  if (earthMesh) { earthMesh.material.uniforms.opacity.value = reveal; earthMesh.material.uniforms.uTime.value = clock.getElapsedTime() }
  if (cloudMesh) cloudMesh.material.opacity = 0.3 * reveal
  if (cloudLoMesh) cloudLoMesh.material.opacity = 0.18 * reveal
  if (auroraMesh) auroraMesh.material.uniforms.opacity.value = 0.9 * reveal
  for (const m of atmoMeshes) m.material.uniforms.intensity.value = (m.userData.baseI ?? 1.8) * reveal
  for (const pt of pointItems) { pt.core.material.opacity = 0.95 * reveal; pt.halo.material.opacity = 0.22 * reveal }
  emit('ready')
}

defineExpose({ skipIntro })

onMounted(() => {
  introDone = false
  buildScene()
  animate()
})

watch(
  () => props.points,
  () => {
    rebuildPoints()
    rebuildFlightLines()
    rebuildHeatmap()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  disposed = true
  cancelAnimationFrame(raf)
  clearTimeout(resumeTimer)
  if (lastClick) clearTimeout(lastClick.timer)

  // 1) 先把 canvas 从 DOM 移除（最先做，确保即使后面任何释放抛错，也不会残留黑屏遮罩）
  try {
    if (renderer && renderer.domElement && renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
  } catch (e) {
    console.error('[GlobeScene] remove canvas failed', e)
  }

  // 2) 解绑事件 + 断开观察器
  try {
    if (resizeObserver) resizeObserver.disconnect()
    if (renderer && renderer.domElement) {
      renderer.domElement.removeEventListener('pointerdown', onPointerDown)
      renderer.domElement.removeEventListener('pointerup', onPointerUp)
      renderer.domElement.removeEventListener('pointermove', onPointerMove)
      renderer.domElement.removeEventListener('pointerleave', onPointerLeave)
      renderer.domElement.removeEventListener('dblclick', onDblClick)
    }
  } catch (e) {
    console.error('[GlobeScene] unbind failed', e)
  }

  // 3) 释放控制器 / 后期管线 / 渲染器（逐项 try，互不阻断）
  try { if (controls) controls.dispose() } catch (e) { console.error(e) }
  try { if (composer) composer.dispose() } catch (e) { console.error(e) }
  try { if (renderer) renderer.dispose() } catch (e) { console.error(e) }

  // 4) 释放场景几何与材质（跳过无 material 的 Group，避免 undefined.dispose 抛错）
  try {
    if (scene) {
      scene.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose()
        const mat = obj.material
        if (mat) {
          const mats = Array.isArray(mat) ? mat : [mat]
          mats.forEach((m) => {
            if (!m) return
            // 自定义 Shader 的纹理在 uniforms 里，单独释放避免显存泄漏
            if (m.uniforms) {
              for (const k in m.uniforms) {
                const v = m.uniforms[k] && m.uniforms[k].value
                if (v && v.isTexture) v.dispose()
              }
            }
            if (m.map) m.map.dispose()
            m.dispose()
          })
        }
      })
    }
  } catch (e) {
    console.error('[GlobeScene] scene dispose failed', e)
  }
})
</script>

<style scoped>
.globe-scene {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.globe-scene :deep(canvas) {
  display: block;
}
</style>
