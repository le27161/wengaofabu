<template>
  <section class="container ai-news-page">
    <header class="ai-news-page__head">
      <p class="ai-news-page__eyebrow">Knowledge Assistant</p>
      <h1>AI 新闻助手</h1>
      <p>基于已发布新闻回答问题，并提供可回溯的新闻来源。</p>
    </header>

    <div class="ai-news-page__card">
      <el-select v-model="category" clearable placeholder="全部栏目" class="ai-news-page__category">
        <el-option v-for="item in categories" :key="item.id" :label="item.name" :value="item.name" />
      </el-select>
      <el-input
        v-model="question"
        type="textarea"
        :rows="4"
        maxlength="2000"
        show-word-limit
        placeholder="例如：最近有哪些人工智能相关新闻？"
        @keydown.enter.exact.prevent="submit"
      />
      <div class="ai-news-page__actions">
        <span>答案只基于已发布新闻</span>
        <el-button type="primary" :loading="loading" :disabled="!question.trim()" @click="submit">
          {{ loading ? '查询中…' : '开始提问' }}
        </el-button>
      </div>
    </div>

    <article v-if="answer" class="ai-news-page__answer">
      <h2>回答</h2>
      <p>{{ answer }}</p>
      <div v-if="sources.length" class="ai-news-page__sources">
        <h3>参考新闻</h3>
        <a v-for="source in sources" :key="`${source.article_id}-${source.chunk_index}`" :href="source.url" class="ai-news-source">
          <span>{{ source.title || source.source }}</span>
          <small>{{ source.published_at ? source.published_at.slice(0, 10) : '已发布' }}</small>
        </a>
      </div>
    </article>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { aiNewsApi, categoryApi } from '../../api'

const question = ref('')
const category = ref('')
const categories = ref([])
const answer = ref('')
const sources = ref([])
const loading = ref(false)

onMounted(async () => {
  try {
    const response = await categoryApi.list()
    categories.value = response.items || []
  } catch {
    // 栏目加载失败不影响用户直接提问。
  }
})

async function submit() {
  const text = question.value.trim()
  if (!text || loading.value) return
  loading.value = true
  answer.value = ''
  sources.value = []
  try {
    const response = await aiNewsApi.chat({ question: text, category: category.value || undefined })
    const data = response.data || response
    answer.value = data.answer || '知识库中没有足够信息回答这个问题。'
    sources.value = data.sources || []
  } catch (error) {
    ElMessage.error(typeof error === 'string' ? error : 'AI 新闻助手暂时不可用，请稍后再试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.ai-news-page { max-width: 880px; padding: 56px 20px 80px; }
.ai-news-page__head { margin-bottom: 28px; }
.ai-news-page__eyebrow { color: var(--color-primary); font-size: 12px; letter-spacing: .14em; text-transform: uppercase; }
.ai-news-page h1 { margin: 8px 0; font-family: var(--font-heading); font-size: clamp(2rem, 5vw, 3.5rem); }
.ai-news-page__head p:last-child { color: var(--color-text-secondary); }
.ai-news-page__card, .ai-news-page__answer { padding: 24px; border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-surface); box-shadow: var(--shadow-card); }
.ai-news-page__category { width: 180px; margin-bottom: 14px; }
.ai-news-page__actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 14px; color: var(--color-text-muted); font-size: 13px; }
.ai-news-page__answer { margin-top: 24px; }
.ai-news-page__answer h2 { margin-top: 0; }
.ai-news-page__answer p { white-space: pre-wrap; line-height: 1.8; }
.ai-news-page__sources { margin-top: 28px; }
.ai-news-source { display: flex; justify-content: space-between; gap: 20px; padding: 14px 0; border-top: 1px solid var(--color-border); color: var(--color-text); text-decoration: none; }
.ai-news-source:hover { color: var(--color-primary); }
.ai-news-source small { color: var(--color-text-muted); white-space: nowrap; }
@media (max-width: 600px) { .ai-news-page { padding-top: 32px; } .ai-news-page__actions { align-items: stretch; flex-direction: column; } .ai-news-page__actions .el-button { width: 100%; } }
</style>
