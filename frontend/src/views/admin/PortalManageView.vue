<template>
  <div class="portal-admin">
    <h1 class="page-title">门户设置</h1>

    <!-- 首页轮播配置 -->
    <section class="panel">
      <div class="panel__head">
        <h2>首页轮播图</h2>
        <el-switch v-model="bannerModule.enabled" active-text="启用" @change="saveModule('banner')" />
      </div>
      <p class="panel__tip">从已发布文稿中选取展示在首页顶部的轮播图（仅带封面的文稿可选），顺序即展示顺序；也可一键随机选取 5 篇带封面文稿。</p>

      <div class="banner-editor">
        <div v-for="(slide, i) in bannerSlides" :key="slide.article_id || i" class="banner-editor__row">
          <img v-if="slide.image" :src="slide.image" :alt="slide.title" class="banner-editor__thumb" />
          <span v-else class="banner-editor__thumb banner-editor__thumb--empty">无图</span>
          <div class="banner-editor__info">
            <span class="banner-editor__title">{{ slide.title }}</span>
            <span class="banner-editor__link">{{ slide.link }}</span>
          </div>
          <el-button type="danger" plain @click="removeSlide(i)">移除</el-button>
        </div>
        <el-empty
          v-if="!bannerSlides.length"
          description="尚未配置轮播，点击下方按钮从文稿中选取"
          :image-size="60"
        />
        <div class="banner-editor__actions">
          <el-button type="success" plain :loading="randomizingBanner" @click="randomizeBanner">
            <el-icon><Refresh /></el-icon>
            随机选 5 篇
          </el-button>
          <el-button type="primary" @click="openArticlePicker">
            <el-icon><Document /></el-icon>
            从文稿中选取
          </el-button>
        </div>
      </div>
      <div class="panel__actions">
        <el-button type="primary" :loading="savingBanner" @click="saveModule('banner')">保存轮播配置</el-button>
      </div>
    </section>

    <!-- 选择轮播文稿弹窗 -->
    <el-dialog v-model="pickerVisible" title="选择轮播文稿" width="760px" top="6vh" append-to-body>
      <div class="picker__toolbar">
        <el-input
          v-model="pickerKeyword"
          placeholder="搜索文稿标题"
          clearable
          style="width: 240px"
          @keyup.enter="loadPicker(1)"
          @clear="loadPicker(1)"
        />
        <el-button type="primary" @click="loadPicker(1)">搜索</el-button>
        <el-button
          type="success"
          :disabled="!pickedArticles.length"
          @click="confirmPick"
        >
          添加选中（{{ pickedArticles.length }}）
        </el-button>
      </div>

      <div v-loading="pickerLoading" class="picker__grid">
        <label
          v-for="a in pickerArticles"
          :key="a.id"
          class="picker__item"
          :class="{ 'is-picked': pickedArticles.some((p) => p.id === a.id), 'is-disabled': !a.cover_url }"
        >
          <input
            type="checkbox"
            class="picker__checkbox"
            :checked="pickedArticles.some((p) => p.id === a.id)"
            :disabled="!a.cover_url"
            @change="togglePick(a, $event.target.checked)"
          />
          <img v-if="a.cover_url" :src="a.cover_url" :alt="a.title" loading="lazy" class="picker__thumb" />
          <span v-else class="picker__thumb picker__thumb--empty">无封面</span>
          <div class="picker__meta">
            <span class="picker__title">{{ a.title }}</span>
            <span class="picker__tag">{{ a.categories[0]?.name || '未分类' }}</span>
          </div>
        </label>
        <el-empty v-if="!pickerLoading && !pickerArticles.length" description="暂无已发布文稿" />
      </div>

      <div class="picker__pager">
        <el-pagination
          layout="total, prev, pager, next"
          :total="pickerTotal"
          :page-size="pickerPageSize"
          :current-page="pickerPage"
          @current-change="loadPicker"
        />
      </div>
    </el-dialog>

    <!-- 站内公告 -->
    <section class="panel">
      <div class="panel__head">
        <h2>站内公告</h2>
        <el-switch v-model="noticeModule.enabled" active-text="启用" @change="saveModule('notice')" />
      </div>
      <el-input
        v-model="noticeText"
        type="textarea"
        :rows="3"
        maxlength="200"
        show-word-limit
        placeholder="展示在门户首页顶部的公告文本"
      />
      <div class="panel__actions">
        <el-button type="primary" :loading="savingNotice" @click="saveModule('notice')">保存公告</el-button>
      </div>
    </section>

    <!-- 个性化推荐 -->
    <section class="panel">
      <div class="panel__head">
        <h2>个性化推荐</h2>
        <el-switch v-model="recommendModule.enabled" active-text="启用" @change="saveModule('recommend')" />
      </div>
      <p class="panel__tip">在门户首页展示"为你推荐"区块：登录且观看历史满 20 篇时基于向量召回推荐，
        其余用户展示热门通用推荐；关闭后前台不再展示该区块。</p>
      <div class="panel__actions">
        <el-button type="primary" :loading="savingRecommend" @click="saveModule('recommend')">保存推荐设置</el-button>
      </div>
    </section>

  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Refresh } from '@element-plus/icons-vue'
import { articleApi, portalApi } from '../../api'

const bannerModule = ref({ module_key: 'banner', title: '', content: [], enabled: true })
const noticeModule = ref({ module_key: 'notice', title: '', content: '', enabled: true })
const recommendModule = ref({ module_key: 'recommend', title: '个性化推荐', content: {}, enabled: true })
const bannerSlides = ref([])
const noticeText = ref('')
const savingBanner = ref(false)
const savingNotice = ref(false)
const savingRecommend = ref(false)
const randomizingBanner = ref(false)
// 文稿选取弹窗
const pickerVisible = ref(false)
const pickerKeyword = ref('')
const pickerArticles = ref([])
const pickerTotal = ref(0)
const pickerPage = ref(1)
const pickerPageSize = 12
const pickerLoading = ref(false)
const pickedArticles = ref([])

onMounted(async () => {
  try {
    // 读取全量模块（含已禁用），保证关闭过的模块开关在设置页仍可见、可重新开启
    const res = await portalApi.allModules()
    const banner = res.items.find((m) => m.module_key === 'banner')
    const notice = res.items.find((m) => m.module_key === 'notice')
    const recommend = res.items.find((m) => m.module_key === 'recommend')
    if (banner) {
      bannerModule.value = banner
      bannerSlides.value = Array.isArray(banner.content) ? [...banner.content] : []
    }
    if (notice) {
      noticeModule.value = notice
      noticeText.value = typeof notice.content === 'string' ? notice.content : ''
    }
    if (recommend) {
      recommendModule.value = recommend
    }
  } catch (e) {
    ElMessage.error(String(e))
  }
})

function removeSlide(i) {
  bannerSlides.value.splice(i, 1)
}

async function openArticlePicker() {
  pickerVisible.value = true
  pickedArticles.value = []
  loadPicker(1)
}

async function loadPicker(p) {
  if (p) pickerPage.value = p
  pickerLoading.value = true
  try {
    const res = await articleApi.list({
      keyword: pickerKeyword.value || undefined,
      page: pickerPage.value,
      page_size: pickerPageSize,
    })
    pickerArticles.value = res.items
    pickerTotal.value = res.total
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    pickerLoading.value = false
  }
}

function togglePick(article, checked) {
  if (checked) {
    pickedArticles.value.push(article)
  } else {
    pickedArticles.value = pickedArticles.value.filter((p) => p.id !== article.id)
  }
}

function confirmPick() {
  const existing = new Set(bannerSlides.value.map((s) => s.article_id).filter(Boolean))
  let added = 0
  for (const a of pickedArticles.value) {
    if (existing.has(a.id)) continue
    bannerSlides.value.push({
      article_id: a.id,
      title: a.title,
      image: a.cover_url,
      link: `/article/${a.id}`,
    })
    existing.add(a.id)
    added++
  }
  if (added) {
    ElMessage.success(`已添加 ${added} 张轮播`)
  } else {
    ElMessage.info('所选文稿已在轮播中')
  }
  pickerVisible.value = false
}

async function randomizeBanner() {
  randomizingBanner.value = true
  try {
    const res = await portalApi.bannerRandom(5)
    const candidates = res.items || []
    if (!candidates.length) {
      ElMessage.info('暂无带封面的已发布文稿，请先发布带封面文稿')
      return
    }
    const existing = new Set(bannerSlides.value.map((s) => s.article_id).filter(Boolean))
    let added = 0
    for (const a of candidates) {
      if (existing.has(a.id)) continue
      bannerSlides.value.push({
        article_id: a.id,
        title: a.title,
        image: a.cover_url,
        link: a.link || `/article/${a.id}`,
      })
      existing.add(a.id)
      added++
    }
    const skipped = candidates.length - added
    if (added) {
      ElMessage.success(`已随机添加 ${added} 张轮播${skipped ? `（跳过已在轮播中的 ${skipped} 张）` : ''}`)
    } else {
      ElMessage.info('随机选中的文稿均已在轮播中')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '随机选取失败')
  } finally {
    randomizingBanner.value = false
  }
}

async function saveModule(key) {
  const fn = { banner: savingBanner, notice: savingNotice, recommend: savingRecommend }[key]
  fn.value = true
  try {
    if (key === 'banner') {
      const data = {
        module_key: 'banner',
        title: bannerModule.value.title,
        content: bannerSlides.value.filter((s) => s.image),
        enabled: bannerModule.value.enabled,
      }
      await portalApi.update('banner', data)
    } else if (key === 'notice') {
      const data = {
        module_key: 'notice',
        title: noticeModule.value.title,
        content: noticeText.value,
        enabled: noticeModule.value.enabled,
      }
      await portalApi.update('notice', data)
    } else if (key === 'recommend') {
      const data = {
        module_key: 'recommend',
        title: recommendModule.value.title,
        content: {},
        enabled: recommendModule.value.enabled,
      }
      await portalApi.update('recommend', data)
    }
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    fn.value = false
  }
}

</script>

<style scoped>
.page-title {
  font-size: 24px;
  margin-bottom: 16px;
}

.panel {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--shadow-card);
  margin-bottom: 20px;
}

.panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: 10px;
  margin-bottom: 12px;
}

.panel__head h2 {
  font-size: 18px;
}

.panel__tip {
  color: var(--color-text-muted);
  font-size: 13px;
  margin: 0 0 14px;
}

.panel__actions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}

.banner-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}

.banner-editor__row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-bg);
}

.banner-editor__thumb {
  width: 120px;
  height: 68px;
  object-fit: cover;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  flex-shrink: 0;
}

.banner-editor__thumb--empty {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-paper-2);
  color: var(--color-text-muted);
  font-size: 12px;
}

.banner-editor__info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1;
}

.banner-editor__title {
  min-width: 0;
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.banner-editor__link {
  min-width: 0;
  font-size: 12px;
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.banner-editor__actions {
  display: flex;
  justify-content: flex-end;
}

/* ---- 文稿选取弹窗 ---- */
.picker__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.picker__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  min-height: 140px;
}

.picker__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  min-width: 0;
  border: 2px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: border-color 150ms cubic-bezier(0.16, 1, 0.3, 1),
    background-color 150ms cubic-bezier(0.16, 1, 0.3, 1);
}

.picker__item:hover {
  border-color: var(--color-primary);
}

.picker__item.is-picked {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.picker__item.is-disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.picker__checkbox {
  flex-shrink: 0;
}

.picker__thumb {
  width: 96px;
  height: 54px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid var(--color-border);
  flex-shrink: 0;
}

.picker__thumb--empty {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-paper-2);
  color: var(--color-text-muted);
  font-size: 12px;
}

.picker__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.picker__title {
  min-width: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.picker__tag {
  min-width: 0;
  font-size: 12px;
  color: var(--color-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.picker__pager {
  display: flex;
  justify-content: center;
  margin-top: 14px;
}

.panel__actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .banner-editor__row {
    flex-wrap: wrap;
  }
}
</style>

