<template>
  <!-- 门户文稿卡片（编辑风）：缩略图 + 栏目标签 + 衬线标题 + 摘要 + 作者/时间/浏览 -->
  <article class="article-card">
    <router-link
      v-if="article.cover_url"
      :to="detailLink"
      class="article-card__cover"
      :aria-label="`查看：${article.title}`"
    >
      <img :src="article.cover_url" :alt="article.title" loading="lazy" />
    </router-link>
    <router-link
      v-else
      :to="detailLink"
      class="article-card__cover article-card__cover--placeholder"
      :aria-label="`查看：${article.title}`"
    >
      {{ (article.categories[0]?.name || '文').slice(0, 1) }}
    </router-link>

    <div class="article-card__body">
      <div class="article-card__tags">
        <router-link
          v-for="cat in article.categories"
          :key="cat.id"
          :to="{ name: 'category', params: { slug: cat.slug } }"
          class="tag"
        >
          {{ cat.name }}
        </router-link>
      </div>
      <h3 class="article-card__title">
        <router-link :to="detailLink">{{ article.title }}</router-link>
      </h3>
      <p v-if="article.summary" class="article-card__summary">{{ article.summary }}</p>
      <div class="article-card__meta">
        <span>{{ article.author_name }}</span>
        <!-- 观看历史页优先展示最近观看日期，其余场景展示发布日期 -->
        <span>{{ (article.viewed_at || article.published_at || article.created_at || '').slice(0, 10) }}</span>
        <span aria-label="浏览量">{{ article.view_count }} 阅读</span>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  article: { type: Object, required: true },
})

const detailLink = computed(() => ({ name: 'article-detail', params: { id: props.article.id } }))
</script>

<style scoped>
/* Hallmark · genre: editorial · macrostructure: Catalogue · design-system: design.md · designed-as-app */
/* Hallmark · pre-emit critique: P4 H4 E4 S4 R4 V4 */
.article-card {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-4) 0;
  border-bottom: var(--rule) solid var(--color-rule);
}

.article-card:first-child {
  padding-top: var(--space-3);
}

.article-card__cover {
  flex: 0 0 168px;
  width: 168px;
  min-height: 104px;
  aspect-ratio: 16 / 10;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--color-primary-soft);
  align-self: flex-start;
}

.article-card__cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform var(--dur-base) var(--ease-out);
}

.article-card:hover .article-card__cover img {
  transform: scale(1.02);
}

.article-card__cover--placeholder {
  display: grid;
  place-items: center;
  font-family: var(--font-heading);
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-accent);
}

.article-card__body {
  flex: 1;
  min-width: 0;
}

.article-card__tags {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}

.tag {
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--color-accent);
  background: var(--color-primary-soft);
  padding: 2px 10px;
  border-radius: 2px;
}

.article-card__title {
  font-family: var(--font-heading);
  font-size: var(--text-xl);
  font-weight: 700;
  line-height: var(--leading-snug);
  margin-bottom: var(--space-2);
}

.article-card__title a {
  display: block;
  color: var(--color-ink);
  transition: color var(--dur-base) var(--ease-out);
}

.article-card__title a:hover {
  color: var(--color-accent);
}

.article-card__summary {
  color: var(--color-ink-2);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
  margin: 0 0 var(--space-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.article-card__meta {
  display: flex;
  gap: var(--space-3);
  font-size: var(--text-xs);
  color: var(--color-ink-3);
}

@media (max-width: 640px) {
  .article-card__cover {
    flex-basis: 120px;
    width: 120px;
    min-height: 76px;
  }

  .article-card__title {
    font-size: var(--text-lg);
  }
}
</style>
