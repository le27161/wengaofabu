<template>
  <div class="container home">
    <!-- 页面唯一主标题（屏幕阅读器） -->
    <h1 class="sr-only">文稿发布首页</h1>

    <!-- 站内公告 -->
    <div v-if="notice" class="notice" role="status">
      <span class="notice__label">公告</span>
      <span class="notice__text">{{ notice }}</span>
    </div>

    <!-- 同城搜索状态提示 -->
    <div v-if="cityStore.active" class="city-banner" role="status">
      <span class="city-banner__label">同城</span>
      <span class="city-banner__text">当前正在浏览「{{ cityStore.label }}」本地内容，切换城市请使用顶部导航栏「同城搜索」</span>
      <button class="city-banner__clear" type="button" @click="clearCity">切回全站</button>
    </div>

    <!-- 头条：优先管理员配置的轮播，未配置则展示热门文稿 -->
    <section class="lead" aria-label="头条区域">
      <el-carousel v-if="bannerItems.length" height="380px" class="lead__carousel" :interval="5000">
        <el-carousel-item v-for="(item, i) in bannerItems" :key="i">
          <a :href="item.link || '#'" class="lead__slide">
            <img :src="item.image" :alt="item.title" />
            <div class="lead__mask">
              <h2>{{ item.title }}</h2>
            </div>
          </a>
        </el-carousel-item>
      </el-carousel>

      <article v-else-if="hotArticles[0]" class="lead__story">
        <router-link
          :to="{ name: 'article-detail', params: { id: hotArticles[0].id } }"
          class="lead__link"
        >
          <div class="lead__text">
            <span class="lead__kicker">头条</span>
            <h2 class="lead__title">{{ hotArticles[0].title }}</h2>
            <p v-if="hotArticles[0].summary" class="lead__summary">{{ hotArticles[0].summary }}</p>
            <p class="lead__meta">
              <span>{{ hotArticles[0].author_name }}</span>
              <span>{{ (hotArticles[0].published_at || hotArticles[0].created_at || '').slice(0, 10) }}</span>
              <span>{{ hotArticles[0].view_count }} 阅读</span>
            </p>
          </div>
          <img
            v-if="hotArticles[0].cover_url"
            :src="hotArticles[0].cover_url"
            :alt="hotArticles[0].title"
            class="lead__cover"
          />
          <span v-else class="lead__cover lead__cover--placeholder">
            {{ (hotArticles[0].categories[0]?.name || '文').slice(0, 1) }}
          </span>
        </router-link>
      </article>
    </section>

    <div class="home__grid">
      <!-- 左侧：最新发布 -->
      <section class="index-section">
        <div class="index-section__head">
          <h2>最新发布</h2>
          <router-link to="/search" class="index-section__more">更多 ›</router-link>
        </div>
        <ul class="story-list">
          <li v-for="a in latestArticles" :key="a.id" class="story-list__item">
            <router-link
              :to="{ name: 'article-detail', params: { id: a.id } }"
              class="story-list__link"
            >
              <span v-if="a.categories[0]" class="story-list__tag">{{ a.categories[0].name }}</span>
              <span class="story-list__title">{{ a.title }}</span>
              <span class="story-list__time">{{ (a.published_at || a.created_at || '').slice(0, 10) }}</span>
            </router-link>
          </li>
        </ul>
      </section>

      <!-- 右侧：热门排行 -->
      <aside class="index-section">
        <div class="index-section__head">
          <h2>热门排行</h2>
        </div>
        <ol class="rank-list">
          <li v-for="(a, i) in hotArticles" :key="a.id">
            <router-link :to="{ name: 'article-detail', params: { id: a.id } }">
              <span class="rank-list__no" :class="{ 'rank-list__no--top': i < 3 }">
                {{ String(i + 1).padStart(2, '0') }}
              </span>
              <span class="rank-list__title">{{ a.title }}</span>
              <span class="rank-list__views">{{ a.view_count }} 阅读</span>
            </router-link>
          </li>
        </ol>
      </aside>
    </div>

    <!-- 为你推荐：个性化推荐区块（后台门户设置可开关） -->
    <section v-if="recommendEnabled && recommendItems.length" class="recommend" aria-label="为你推荐">
      <div class="section__head">
        <div class="section__head-text">
          <h2>为你推荐</h2>
          <p class="section__desc">基于你的浏览偏好智能推荐</p>
        </div>
      </div>
      <div class="recommend__grid">
        <article v-for="a in recommendItems" :key="a.id" class="recommend-card">
          <router-link
            :to="{ name: 'article-detail', params: { id: a.id } }"
            class="recommend-card__cover"
            :aria-label="`查看：${a.title}`"
          >
            <img v-if="a.cover_url" :src="a.cover_url" :alt="a.title" loading="lazy" />
            <span v-else class="recommend-card__placeholder">
              {{ (a.categories[0]?.name || '文').slice(0, 1) }}
            </span>
          </router-link>
          <div class="recommend-card__body">
            <span v-if="a.categories[0]" class="tag">{{ a.categories[0].name }}</span>
            <h3 class="recommend-card__title">
              <router-link :to="{ name: 'article-detail', params: { id: a.id } }">
                {{ a.title }}
              </router-link>
            </h3>
            <p v-if="a.summary" class="recommend-card__summary">{{ a.summary }}</p>
          </div>
        </article>
      </div>
    </section>

    <!-- 栏目分区 -->
    <section v-for="cat in sectionCategories" :key="cat.id" class="section">
      <div class="section__head">
        <div class="section__head-text">
          <h2>{{ cat.name }}</h2>
          <p v-if="cat.description" class="section__desc">{{ cat.description }}</p>
        </div>
        <router-link :to="{ name: 'category', params: { slug: cat.slug } }" class="section__more">
          更多 ›
        </router-link>
      </div>
      <div class="section__grid">
        <ArticleCard v-for="a in sectionArticles[cat.id] || []" :key="a.id" :article="a" />
      </div>
      <div v-if="!(sectionArticles[cat.id] || []).length" class="empty">该栏目暂无已发布文稿</div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { articleApi, categoryApi, portalApi } from '../../api'
import { useCityStore } from '../../stores/city'
import ArticleCard from '../../components/ArticleCard.vue'

const route = useRoute()
const cityStore = useCityStore()
const modules = ref([])
const latestArticles = ref([])
const hotArticles = ref([])
const recommendItems = ref([])
const categories = ref([])
const sectionArticles = ref({})

const notice = computed(() => {
  const m = modules.value.find((x) => x.module_key === 'notice')
  return m && typeof m.content === 'string' ? m.content : ''
})

const bannerItems = computed(() => {
  const m = modules.value.find((x) => x.module_key === 'banner')
  return Array.isArray(m?.content) ? m.content : []
})

// 个性化推荐开关：模块存在且启用（后台门户设置控制，关闭后前台接口不再返回该模块）
const recommendEnabled = computed(() => {
  const m = modules.value.find((x) => x.module_key === 'recommend')
  return !!m && m.enabled !== false
})

const sectionCategories = computed(() => categories.value.slice(0, 4))

// 同城搜索：组装城市参数（空串表示全站，不传 city）
function cityParam() {
  return cityStore.city ? { city: cityStore.city } : {}
}

async function load() {
  try {
    const [moduleRes, latestRes, hotRes, catRes] = await Promise.all([
      portalApi.modules(),
      articleApi.list({ sort: 'latest', page_size: 8, ...cityParam() }),
      articleApi.list({ sort: 'hot', page_size: 6, ...cityParam() }),
      categoryApi.list(),
    ])
    modules.value = moduleRes.items
    latestArticles.value = latestRes.items
    hotArticles.value = hotRes.items
    categories.value = catRes.items

    // 推荐区块：开关开启时请求个性化推荐（未登录返回通用推荐），失败静默不展示
    if (recommendEnabled.value) {
      articleApi
        .portalRecommend({ limit: 8 })
        .then((res) => {
          recommendItems.value = res.items || []
        })
        .catch(() => {
          recommendItems.value = []
        })
    }

    // 并行加载每个栏目分区的最新文稿（同城模式下栏目分区同样按城市过滤）
    const sections = await Promise.all(
      sectionCategories.value.map(async (cat) => {
        const res = await articleApi.list({ category_id: cat.id, sort: 'latest', page_size: 4, ...cityParam() })
        return [cat.id, res.items]
      }),
    )
    sectionArticles.value = Object.fromEntries(sections)
  } catch (e) {
    ElMessage.error(String(e))
  }
}

// 切回全站：清空城市选择
function clearCity() {
  cityStore.setCity('')
}

// 城市变化（导航条选择/清除）→ 重新加载首页所有列表
watch(() => cityStore.city, () => {
  if (route.name === 'home') load()
})

onMounted(load)
</script>

<style scoped>
/* Hallmark · genre: editorial · macrostructure: Front Page · design-system: design.md · designed-as-app */
/* Hallmark · pre-emit critique: P4 H4 E4 S4 R4 V4 */
.home {
  padding-top: var(--space-5);
}

/* 同城搜索状态提示条 */
.city-banner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  border: var(--rule) solid var(--color-accent);
  border-left: 3px solid var(--color-accent);
  background: var(--color-primary-soft);
  padding: 8px var(--space-4);
  margin-bottom: var(--space-5);
  font-size: var(--text-sm);
}

.city-banner__label {
  flex-shrink: 0;
  background: var(--color-accent);
  color: #fff;
  font-size: var(--text-xs);
  padding: 2px 10px;
  border-radius: 2px;
  font-weight: 700;
}

.city-banner__text {
  flex: 1;
  min-width: 0;
  color: var(--color-ink-2);
}

.city-banner__clear {
  flex-shrink: 0;
  border: none;
  background: none;
  color: var(--color-accent);
  font-size: var(--text-xs);
  font-weight: 600;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  transition: background var(--dur-base) var(--ease-out);
}

.city-banner__clear:hover {
  background: var(--color-paper-2);
}

.notice {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  border: var(--rule) solid var(--color-rule);
  border-left: 3px solid var(--color-accent-2);
  background: var(--color-accent-2-soft);
  padding: 10px var(--space-4);
  margin-bottom: var(--space-5);
  font-size: var(--text-sm);
}

.notice__label {
  flex-shrink: 0;
  background: var(--color-accent-2);
  color: #fff;
  font-size: var(--text-xs);
  padding: 2px 10px;
  border-radius: 2px;
  font-weight: 600;
}

.lead {
  margin-bottom: var(--space-6);
}

.lead__carousel {
  border-radius: var(--radius-md);
  overflow: hidden;
  border: var(--rule) solid var(--color-rule);
}

.lead__slide {
  position: relative;
  display: block;
  height: 100%;
  /* contain 模式图片四周可能留白，用主题次级背景填充，避免留白刺眼 */
  background: var(--color-paper-2);
}

.lead__slide img {
  width: 100%;
  height: 100%;
  /* contain：完整显示图片、不裁切，解决封面图只显示局部的问题；
     若想恢复通栏铺满裁切效果可改回 cover */
  object-fit: contain;
}

.lead__mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: flex-end;
  padding: var(--space-6);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0) 35%, rgba(15, 23, 42, 0.82));
  color: #fff;
}

.lead__mask h2 {
  font-family: var(--font-heading);
  font-size: clamp(1.5rem, 3vw + 0.5rem, 2.25rem);
  line-height: var(--leading-tight);
}

.lead__story {
  border: var(--rule) solid var(--color-rule);
  background: var(--color-paper);
}

.lead__link {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: var(--space-6);
  padding: var(--space-6);
  align-items: stretch;
}

.lead__text {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
}

.lead__kicker {
  align-self: flex-start;
  font-size: var(--text-xs);
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--color-accent-2);
  border-bottom: 2px solid var(--color-accent-2);
  padding-bottom: 4px;
  margin-bottom: var(--space-4);
}

.lead__title {
  font-family: var(--font-heading);
  font-size: var(--text-display);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-tight);
  color: var(--color-ink);
  transition: color var(--dur-base) var(--ease-out);
}

.lead__link:hover .lead__title {
  color: var(--color-accent);
}

.lead__summary {
  color: var(--color-ink-2);
  font-size: var(--text-lg);
  line-height: var(--leading-normal);
  margin: var(--space-4) 0 0;
}

.lead__meta {
  display: flex;
  gap: var(--space-4);
  margin: var(--space-4) 0 0;
  font-size: var(--text-xs);
  color: var(--color-ink-3);
}

.lead__cover {
  width: 100%;
  height: 100%;
  min-height: 240px;
  object-fit: cover;
  border-radius: var(--radius-sm);
  align-self: center;
}

.lead__cover--placeholder {
  display: grid;
  place-items: center;
  font-family: var(--font-heading);
  font-size: 4rem;
  font-weight: 700;
  color: var(--color-accent);
  background: var(--color-primary-soft);
}

.home__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: var(--space-6);
  margin-bottom: var(--space-6);
}

.index-section__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  border-bottom: 2px solid var(--color-ink);
  padding-bottom: var(--space-2);
  margin-bottom: var(--space-3);
}

.index-section__head h2 {
  font-family: var(--font-heading);
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--color-ink);
}

.index-section__more {
  font-size: var(--text-xs);
  color: var(--color-ink-3);
  transition: color var(--dur-base) var(--ease-out);
}

.index-section__more:hover {
  color: var(--color-accent);
}

.story-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.story-list__item + .story-list__item {
  border-top: var(--rule) solid var(--color-rule);
}

.story-list__link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  color: var(--color-ink);
  font-size: var(--text-base);
}

.story-list__tag {
  flex-shrink: 0;
  font-size: var(--text-xs);
  color: var(--color-accent);
  background: var(--color-primary-soft);
  padding: 2px 8px;
  border-radius: 2px;
}

.story-list__title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-heading);
  font-weight: 600;
  transition: color var(--dur-base) var(--ease-out);
}

.story-list__link:hover .story-list__title {
  color: var(--color-accent);
}

.story-list__time {
  flex-shrink: 0;
  color: var(--color-ink-3);
  font-size: var(--text-xs);
}

.rank-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.rank-list li + li {
  border-top: var(--rule) solid var(--color-rule);
}

.rank-list a {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  color: var(--color-ink);
  font-size: var(--text-sm);
}

.rank-list__no {
  flex-shrink: 0;
  font-family: var(--font-heading);
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--color-rule-strong);
  line-height: 1;
  min-width: 34px;
}

.rank-list__no--top {
  color: var(--color-accent-2);
}

.rank-list__title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color var(--dur-base) var(--ease-out);
}

.rank-list a:hover .rank-list__title {
  color: var(--color-accent);
}

.rank-list__views {
  flex-shrink: 0;
  color: var(--color-ink-3);
  font-size: var(--text-xs);
}

.section {
  margin-bottom: var(--space-6);
}

.section__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  border-bottom: 2px solid var(--color-ink);
  padding-bottom: var(--space-2);
  margin-bottom: var(--space-3);
}

.section__head-text {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  min-width: 0;
}

.section__head h2 {
  font-family: var(--font-heading);
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--color-ink);
}

.section__desc {
  color: var(--color-ink-3);
  font-size: var(--text-xs);
  margin: 0;
}

.section__more {
  font-size: var(--text-xs);
  color: var(--color-ink-3);
  transition: color var(--dur-base) var(--ease-out);
}

.section__more:hover {
  color: var(--color-accent);
}

.section__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 var(--space-6);
}

/* ---- 为你推荐：竖排卡片网格（4→2→1 响应式） ---- */
.recommend {
  margin-bottom: var(--space-6);
}

.recommend__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-5) var(--space-6);
}

.recommend-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: var(--rule) solid var(--color-rule);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--color-paper);
  transition:
    transform var(--dur-base) var(--ease-out),
    box-shadow var(--dur-base) var(--ease-out);
}

.recommend-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
}

.recommend-card__cover {
  display: block;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: var(--color-primary-soft);
}

.recommend-card__cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform var(--dur-base) var(--ease-out);
}

.recommend-card:hover .recommend-card__cover img {
  transform: scale(1.03);
}

.recommend-card__placeholder {
  display: grid;
  place-items: center;
  height: 100%;
  font-family: var(--font-heading);
  font-size: 2.5rem;
  font-weight: 700;
  color: var(--color-accent);
}

.recommend-card__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-4);
}

.recommend-card__title {
  font-family: var(--font-heading);
  font-size: var(--text-base);
  font-weight: 700;
  line-height: var(--leading-snug);
}

.recommend-card__title a {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: var(--color-ink);
  transition: color var(--dur-base) var(--ease-out);
}

.recommend-card__title a:hover {
  color: var(--color-accent);
}

.recommend-card__summary {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin: 0;
  color: var(--color-ink-2);
  font-size: var(--text-xs);
  line-height: var(--leading-normal);
}

.empty {
  color: var(--color-ink-3);
  text-align: center;
  padding: var(--space-6) 0;
  font-size: var(--text-sm);
}

@media (max-width: 1024px) {
  .home__grid {
    grid-template-columns: 1fr;
  }

  .recommend__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .index-section__more,
  .section__more {
    min-width: var(--size-touch);
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
  }

  .lead__link {
    grid-template-columns: 1fr;
    gap: var(--space-4);
    padding: var(--space-4);
  }

  .lead__cover {
    min-height: 180px;
  }

  .section__grid {
    grid-template-columns: 1fr;
  }

  .recommend__grid {
    grid-template-columns: 1fr;
  }

  .lead__title {
    font-size: clamp(1.6rem, 8vw, 2.2rem);
  }
}
</style>
