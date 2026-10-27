<template>
  <div class="task-detail-page">
    <div class="page-head">
      <div>
        <AdminBackLink :to="{ name: 'admin-smart-collect' }" label="返回任务列表" />
        <h1 class="page-title">采编任务 #{{ task?.id || route.params.id }}</h1>
      </div>
      <el-button :loading="loading" @click="loadTask">重新加载</el-button>
    </div>

    <div v-if="task" class="workflow-steps" aria-label="采编流程进度">
      <div
        v-for="step in workflowSteps"
        :key="step.key"
        class="workflow-step"
        :class="{ 'is-done': step.done, 'is-current': step.current }"
      >
        <span class="workflow-step__num">{{ step.index }}</span>
        <div>
          <strong>{{ step.label }}</strong>
          <small>{{ step.hint }}</small>
        </div>
      </div>
    </div>

    <el-card v-loading="loading" shadow="never" class="task-card">
      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="false"
      />
      <template v-if="task">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="新闻主题" :span="2">{{ task.query }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusMeta[task.status]?.type || 'info'">
              {{ statusMeta[task.status]?.label || task.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建人">{{ task.creator_name }}</el-descriptions-item>
          <el-descriptions-item label="时间范围">{{ timeRangeText[task.time_range] }}</el-descriptions-item>
          <el-descriptions-item label="最大结果数">{{ task.max_results }}</el-descriptions-item>
          <el-descriptions-item label="保存线索数">{{ task.result_count }}</el-descriptions-item>
          <el-descriptions-item label="Credits">{{ task.credits_used }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(task.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ formatDate(task.finished_at) }}</el-descriptions-item>
          <el-descriptions-item v-if="task.error_message" label="失败原因" :span="3">
            <span class="error-text">{{ task.error_message }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-card>

    <el-card v-if="task" v-loading="eventsLoading" shadow="never" class="events-card">
      <template #header>
        <div class="events-head">
          <div>
            <strong>事件分组</strong>
            <p>由编辑人工确认新闻线索所属事件；相似度分析只作为判断参考。</p>
          </div>
          <span>{{ eventGrouping.events.length }} 个事件</span>
        </div>
      </template>
      <el-alert
        v-if="eventsError"
        :title="eventsError"
        type="error"
        show-icon
        :closable="false"
      />

      <section class="events-section">
        <h2>已有事件</h2>
        <el-empty
          v-if="!eventGrouping.events.length"
          description="尚未创建人工事件"
          :image-size="72"
        />
        <div v-else class="event-list">
          <article v-for="event in eventGrouping.events" :key="event.id" class="event-item">
            <div class="event-item__head">
              <div>
                <h3>{{ event.title }}</h3>
                <span>
                  事件 #{{ event.id }} · 来源：{{ event.clue_count }} 篇 ·
                  来源材料：{{ eventCompletedCount(event) }} / {{ event.clue_count }} 获取成功
                </span>
                <el-tag v-if="event.clue_count === 1" size="small" type="warning">
                  单来源事件
                </el-tag>
              </div>
              <div class="event-actions">
                <el-button
                  size="small"
                  type="primary"
                  :loading="preparingEventId === event.id"
                  :disabled="preparingEventId !== null && preparingEventId !== event.id"
                  @click="prepareEventContent(event)"
                >
                  准备事件材料
                </el-button>
                <el-button
                  size="small"
                  :loading="evidenceLoadingEventId === event.id"
                  :disabled="evidenceLoadingEventId !== null && evidenceLoadingEventId !== event.id"
                  @click="viewEventEvidence(event)"
                >
                  查看事件证据
                </el-button>
                <el-button
                  size="small"
                  type="success"
                  :loading="synthesizingEventId === event.id"
                  :disabled="synthesizingEventId !== null && synthesizingEventId !== event.id"
                  @click="synthesizeEvent(event)"
                >
                  AI整理事件
                </el-button>
                <el-button size="small" @click="openRenameEvent(event)">修改标题</el-button>
                <el-button
                  size="small"
                  :disabled="!eventGrouping.ungrouped_clues.length"
                  @click="openAddClues(event)"
                >
                  增加线索
                </el-button>
                <el-button size="small" type="danger" plain @click="deleteEvent(event)">
                  删除事件
                </el-button>
              </div>
            </div>
            <el-empty
              v-if="!event.clues.length"
              description="该事件暂无线索，可继续增加或删除事件"
              :image-size="56"
            />
            <div v-else class="event-clue-list">
              <div v-for="clue in event.clues" :key="clue.clue_id" class="event-clue-item">
                <div>
                  <span>#{{ clue.rank }} · {{ clue.source }}</span>
                  <strong>{{ clue.title }}</strong>
                  <small>
                    Tavily {{ formatScore(clue.search_score) }} ·
                    语义 {{ formatSemanticScore(clue.semantic_score) }} ·
                    人工 {{ relevanceText(clue.relevance_label) }}
                  </small>
                  <small
                    class="content-state"
                    :class="`content-state--${clue.content_status || 'none'}`"
                    :title="clue.content_status === 'failed' ? '可再次点击准备事件材料重试' : ''"
                  >
                    正文状态：{{ contentStatusText(clue.content_status) }}
                    <template v-if="clue.content_status === 'completed'">
                      · 正文：{{ clue.content_length }}字
                    </template>
                  </small>
                </div>
                <div class="event-clue-actions">
                  <el-button
                    v-if="clue.content_status === 'completed'"
                    link
                    type="primary"
                    @click="viewContent(clue)"
                  >
                    查看正文
                  </el-button>
                  <el-button
                    link
                    type="danger"
                    :disabled="eventActionLoading"
                    @click="removeEventClue(event, clue)"
                  >
                    移出事件
                  </el-button>
                </div>
              </div>
            </div>
            <section class="synthesis-history">
              <div class="synthesis-history__head">
                <strong>AI整理历史</strong>
                <span>{{ synthesisHistories[event.id]?.length || 0 }} 个版本</span>
              </div>
              <p v-if="!synthesisHistories[event.id]?.length" class="synthesis-history__empty">
                尚无已保存版本。生成结果通过结构与来源校验后会自动保存。
              </p>
              <div v-else class="synthesis-history__items">
                <button
                  v-for="item in synthesisHistories[event.id]"
                  :key="item.id"
                  type="button"
                  class="synthesis-version"
                  :class="{ 'is-active': synthesisResults[event.id]?.id === item.id }"
                  @click="viewSynthesisVersion(event, item.id)"
                >
                  <strong>v{{ item.version }}</strong>
                  <el-tag :type="synthesisStatusType(item.status)" size="small">
                    {{ synthesisStatusText(item.status) }}
                  </el-tag>
                  <span>{{ item.actual_model }}</span>
                  <small>
                    {{ formatDate(item.created_at) }}
                    <template v-if="item.article"> · 文稿 #{{ item.article.id }}</template>
                  </small>
                </button>
              </div>
            </section>
            <section v-if="synthesisResults[event.id]" class="synthesis-result">
              <div class="synthesis-result__head">
                <div>
                  <strong>AI事件整理 v{{ synthesisResults[event.id].version }}</strong>
                  <el-tag
                    :type="synthesisStatusType(synthesisResults[event.id].status)"
                    size="small"
                  >
                    {{ synthesisStatusText(synthesisResults[event.id].status) }}
                  </el-tag>
                </div>
                <span>
                  实际模型 {{ synthesisResults[event.id].actual_model }} ·
                  {{ synthesisResults[event.id].duration_ms }} ms ·
                  {{ synthesisResults[event.id].source_count }} 个SOURCE ·
                  输入正文 {{ synthesisResults[event.id].total_content_length }} 字 ·
                  输出 {{ synthesisResults[event.id].output_content_length }} 字
                  <template v-if="synthesisResults[event.id].total_tokens !== null">
                    · Token {{ synthesisResults[event.id].input_tokens }} +
                    {{ synthesisResults[event.id].output_tokens }} =
                    {{ synthesisResults[event.id].total_tokens }}
                  </template>
                </span>
              </div>
              <div class="synthesis-review-actions">
                <el-button
                  v-if="synthesisResults[event.id].status === 'generated'"
                  size="small"
                  type="success"
                  :loading="synthesisActionId === synthesisResults[event.id].id"
                  @click="reviewSynthesis(event, 'approve')"
                >
                  确认采用
                </el-button>
                <el-button
                  v-if="['generated', 'approved'].includes(synthesisResults[event.id].status)"
                  size="small"
                  type="danger"
                  plain
                  :loading="synthesisActionId === synthesisResults[event.id].id"
                  @click="reviewSynthesis(event, 'reject')"
                >
                  {{ synthesisResults[event.id].status === 'approved' ? '废弃已确认版本' : '弃用' }}
                </el-button>
                <el-button
                  v-if="synthesisResults[event.id].status === 'approved' && !synthesisResults[event.id].article"
                  size="small"
                  type="primary"
                  :loading="articleCreatingId === synthesisResults[event.id].id"
                  @click="createArticleFromSynthesis(event)"
                >
                  创建正式文稿
                </el-button>
                <template v-if="synthesisResults[event.id].article">
                  <el-tag type="success" size="small">
                    已创建文稿 #{{ synthesisResults[event.id].article.id }}
                  </el-tag>
                  <el-button
                    size="small"
                    type="primary"
                    plain
                    @click="openArticleEditor(synthesisResults[event.id].article.id)"
                  >
                    进入文稿编辑
                  </el-button>
                </template>
                <span>
                  生成于 {{ formatDate(synthesisResults[event.id].created_at) }}
                  <template v-if="synthesisResults[event.id].reviewed_at">
                    · 审核于 {{ formatDate(synthesisResults[event.id].reviewed_at) }}
                  </template>
                </span>
              </div>
              <p class="synthesis-summary">{{ synthesisResults[event.id].result.summary }}</p>

              <div class="synthesis-section">
                <h4>核心事实</h4>
                <el-empty
                  v-if="!synthesisResults[event.id].result.core_facts.length"
                  description="模型未提取核心事实"
                  :image-size="48"
                />
                <ol v-else>
                  <li
                    v-for="(fact, index) in synthesisResults[event.id].result.core_facts"
                    :key="`${event.id}-fact-${index}`"
                  >
                    <span>{{ fact.text }}</span>
                    <span class="source-links">
                      <el-button
                        v-for="clueId in fact.source_clue_ids"
                        :key="clueId"
                        link
                        type="primary"
                        @click="viewContent({ clue_id: clueId })"
                      >
                        SOURCE[{{ clueId }}]
                      </el-button>
                    </span>
                  </li>
                </ol>
              </div>

              <div class="synthesis-columns">
                <div class="synthesis-section">
                  <h4>涉及主体</h4>
                  <p>{{ listText(synthesisResults[event.id].result.entities) }}</p>
                </div>
                <div class="synthesis-section">
                  <h4>时间信息</h4>
                  <p>{{ listText(synthesisResults[event.id].result.time_info) }}</p>
                </div>
              </div>

              <div class="synthesis-section">
                <h4>来源冲突</h4>
                <p v-if="!synthesisResults[event.id].result.conflicts.length">未识别到明确冲突。</p>
                <ul v-else>
                  <li
                    v-for="(conflict, index) in synthesisResults[event.id].result.conflicts"
                    :key="`${event.id}-conflict-${index}`"
                  >
                    {{ conflict.description }}
                    <span class="source-links">
                      <el-button
                        v-for="clueId in conflict.source_clue_ids"
                        :key="clueId"
                        link
                        type="primary"
                        @click="viewContent({ clue_id: clueId })"
                      >
                        SOURCE[{{ clueId }}]
                      </el-button>
                    </span>
                  </li>
                </ul>
              </div>

              <div class="synthesis-section">
                <h4>证据不足</h4>
                <p>{{ listText(synthesisResults[event.id].result.insufficient_evidence) }}</p>
              </div>
              <div class="synthesis-section synthesis-snapshot">
                <h4>生成证据快照</h4>
                <div
                  v-for="source in synthesisResults[event.id].evidence_snapshot"
                  :key="`${synthesisResults[event.id].id}-${source.clue_id}`"
                  class="synthesis-snapshot__item"
                >
                  <span>
                    SOURCE[{{ source.clue_id }}] · 生成时哈希 {{ shortHash(source.content_hash) }} ·
                    当前哈希 {{ shortHash(source.current_content_hash) }}
                  </span>
                  <el-tag v-if="source.content_changed" type="warning" size="small">
                    来源正文在本次AI整理后发生过变化
                  </el-tag>
                  <el-button link type="primary" @click="viewContent({ clue_id: source.clue_id })">
                    查看当前正文
                  </el-button>
                </div>
              </div>
              <el-alert
                title="AI整理结果需要编辑审核，来源引用表示模型声明其依据该材料，不等同于系统已经证明该事实绝对正确。"
                type="warning"
                show-icon
                :closable="false"
              />
            </section>
          </article>
        </div>
      </section>

      <el-divider />

      <section class="events-section">
        <div class="ungrouped-head">
          <div>
            <h2>未分组线索</h2>
            <span>{{ eventGrouping.ungrouped_clues.length }} 条</span>
          </div>
          <el-button
            type="primary"
            :disabled="selectedUngroupedClueIds.length === 0"
            @click="openCreateEvent"
          >
            创建事件（已选 {{ selectedUngroupedClueIds.length }} 条）
          </el-button>
        </div>
        <el-empty
          v-if="!eventGrouping.ungrouped_clues.length"
          description="当前任务的全部线索都已分组"
          :image-size="72"
        />
        <el-checkbox-group v-else v-model="selectedUngroupedClueIds" class="ungrouped-list">
          <el-checkbox
            v-for="clue in eventGrouping.ungrouped_clues"
            :key="clue.clue_id"
            :value="clue.clue_id"
            class="ungrouped-item"
          >
            <span class="ungrouped-rank">#{{ clue.rank }}</span>
            <span class="ungrouped-title">{{ clue.title }}</span>
            <span class="ungrouped-source">{{ clue.source }}</span>
          </el-checkbox>
        </el-checkbox-group>
      </section>
    </el-card>

    <el-card v-if="task" shadow="never" class="similarity-card">
      <template #header>
        <div class="similarity-head">
          <div>
            <strong>相似线索分析</strong>
            <p>该分数表示两条新闻文本的语义相似程度，不代表已经确认属于同一个新闻事件。</p>
          </div>
          <el-button type="primary" :loading="similarityLoading" @click="analyzeSimilarity">
            分析新闻相似度
          </el-button>
        </div>
      </template>
      <el-alert
        v-if="similarityError"
        :title="similarityError"
        type="error"
        show-icon
        :closable="false"
      />
      <template v-if="similarityResult">
        <p class="similarity-summary">
          {{ similarityResult.clue_count }} 条线索共 {{ similarityResult.pair_count }} 个pair，
          当前展示相似度最高的 {{ similarityResult.items.length }} 组。
        </p>
        <el-empty
          v-if="!similarityResult.items.length"
          description="当前任务不足两条新闻，没有可分析的线索对"
          :image-size="80"
        />
        <div v-else class="similarity-list">
          <article
            v-for="(pair, index) in similarityResult.items"
            :key="`${pair.left.clue_id}-${pair.right.clue_id}`"
            class="similarity-item"
          >
            <div class="similarity-score">
              <span>Top {{ index + 1 }}</span>
              <strong>相似度：{{ formatSimilarityScore(pair.similarity_score) }}</strong>
            </div>
            <div class="similarity-clues">
              <div>
                <span>新闻 A · #{{ pair.left.rank }} · {{ pair.left.source }}</span>
                <h3>{{ pair.left.title }}</h3>
              </div>
              <div>
                <span>新闻 B · #{{ pair.right.rank }} · {{ pair.right.source }}</span>
                <h3>{{ pair.right.title }}</h3>
              </div>
            </div>
          </article>
        </div>
      </template>
      <el-empty v-else description="点击按钮后计算当前任务的新闻文本相似度" :image-size="80" />
    </el-card>

    <el-card v-if="task" shadow="never">
      <template #header>
        <div class="result-card-head">
          <strong>已保存新闻线索（{{ task.items.length }}）</strong>
          <span>人工标注：{{ labeledCount }} / {{ task.items.length }}</span>
        </div>
      </template>
      <el-empty v-if="!task.items.length" description="本次任务没有搜索到新闻线索" />
      <div v-else class="result-list">
        <article v-for="item in task.items" :key="item.clue_id" class="result-item">
          <div class="result-item__head">
            <div class="title-line">
              <span class="rank">#{{ item.rank }}</span>
              <h2>{{ item.title }}</h2>
            </div>
            <el-tag size="small" type="info">{{ item.source }}</el-tag>
          </div>
          <p class="result-snippet">{{ item.snippet || '该搜索结果没有提供内容片段。' }}</p>
          <div class="relevance-row">
            <span class="relevance-label">人工判断：</span>
            <el-button-group>
              <el-button
                v-for="option in relevanceOptions"
                :key="option.value"
                size="small"
                :type="item.relevance_label === option.value ? 'primary' : undefined"
                :plain="item.relevance_label !== option.value"
                :disabled="savingClueId === item.clue_id"
                :aria-pressed="item.relevance_label === option.value"
                @click="saveRelevance(item, option.value)"
              >
                {{ option.label }}
              </el-button>
            </el-button-group>
            <el-button
              v-if="item.relevance_label !== null && item.relevance_label !== undefined"
              link
              type="primary"
              size="small"
              :disabled="savingClueId === item.clue_id"
              @click="saveRelevance(item, null)"
            >
              恢复未标注
            </el-button>
            <span v-else class="unlabeled-text">未标注</span>
          </div>
          <div class="result-meta">
            <div class="score-list">
              <span>Tavily 搜索相关度：{{ formatScore(item.search_score) }}</span>
              <span>语义相关度：{{ formatSemanticScore(item.semantic_score) }}</span>
            </div>
            <el-link :href="item.url" target="_blank" rel="noopener noreferrer" type="primary">
              查看原文
            </el-link>
          </div>
        </article>
      </div>
    </el-card>

    <el-dialog v-model="createEventDialog.visible" title="创建人工事件" width="520px">
      <p class="dialog-hint">将选中的 {{ selectedUngroupedClueIds.length }} 条线索加入新事件。</p>
      <el-input
        v-model="createEventDialog.title"
        maxlength="200"
        show-word-limit
        placeholder="请手工填写事件标题"
        @keyup.enter="submitCreateEvent"
      />
      <template #footer>
        <el-button @click="createEventDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="eventActionLoading" @click="submitCreateEvent">
          创建事件
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="renameEventDialog.visible" title="修改事件标题" width="520px">
      <el-input
        v-model="renameEventDialog.title"
        maxlength="200"
        show-word-limit
        placeholder="请手工填写事件标题"
        @keyup.enter="submitRenameEvent"
      />
      <template #footer>
        <el-button @click="renameEventDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="eventActionLoading" @click="submitRenameEvent">
          保存标题
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="addCluesDialog.visible" title="向事件增加线索" width="680px">
      <p class="dialog-hint">事件：{{ addCluesDialog.eventTitle }}</p>
      <el-checkbox-group v-model="addCluesDialog.clueIds" class="dialog-clue-list">
        <el-checkbox
          v-for="clue in eventGrouping.ungrouped_clues"
          :key="clue.clue_id"
          :value="clue.clue_id"
          class="ungrouped-item"
        >
          <span class="ungrouped-rank">#{{ clue.rank }}</span>
          <span class="ungrouped-title">{{ clue.title }}</span>
          <span class="ungrouped-source">{{ clue.source }}</span>
        </el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="addCluesDialog.visible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="eventActionLoading"
          :disabled="!addCluesDialog.clueIds.length"
          @click="submitAddClues"
        >
          加入事件
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="evidenceDialog.visible"
      title="事件证据包"
      width="880px"
      top="5vh"
    >
      <div v-loading="evidenceDialog.loading" class="evidence-dialog-body">
        <template v-if="evidenceDialog.detail">
          <h3>{{ evidenceDialog.detail.event_title }}</h3>
          <p class="evidence-summary">
            来源材料：{{ evidenceDialog.detail.completed_source_count }} /
            {{ evidenceDialog.detail.source_count }} ·
            正文总长度：{{ evidenceDialog.detail.total_content_length }} 字
          </p>
          <el-alert
            title="这里只展示未来模型允许读取的事件证据，没有调用LLM，也没有生成摘要。"
            type="info"
            show-icon
            :closable="false"
          />
          <el-empty
            v-if="!evidenceDialog.detail.sources.length"
            description="当前事件没有有效的已完成正文"
            :image-size="72"
          />
          <div v-else class="evidence-source-list">
            <article
              v-for="source in evidenceDialog.detail.sources"
              :key="source.clue_id"
              class="evidence-source-item"
            >
              <div class="evidence-source-head">
                <div>
                  <span>SOURCE[{{ source.clue_id }}] · #{{ source.rank }} · {{ source.source }}</span>
                  <h4>{{ source.title }}</h4>
                  <small>
                    正文 {{ source.content_length }} 字 · SHA-256 {{ shortHash(source.content_hash) }}
                  </small>
                </div>
                <el-button link type="primary" @click="toggleEvidenceSource(source.clue_id)">
                  {{ isEvidenceSourceExpanded(source.clue_id) ? '收起正文' : '查看正文' }}
                </el-button>
              </div>
              <div
                v-if="isEvidenceSourceExpanded(source.clue_id)"
                class="evidence-source-content"
              >
                {{ source.content }}
              </div>
            </article>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="evidenceDialog.visible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="contentDialog.visible"
      title="清洗后的新闻正文"
      width="820px"
      top="5vh"
    >
      <div v-loading="contentDialog.loading" class="content-dialog-body">
        <template v-if="contentDialog.detail">
          <h3>{{ contentDialog.detail.title }}</h3>
          <p class="content-dialog-meta">
            {{ contentDialog.detail.source }} · 正文 {{ contentDialog.detail.content_length }} 字 ·
            获取时间 {{ formatDate(contentDialog.detail.fetched_at) }}
          </p>
          <div class="content-text">{{ contentDialog.detail.content }}</div>
        </template>
      </div>
      <template #footer>
        <el-button @click="contentDialog.visible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { smartCollectApi } from '../../api'
import AdminBackLink from '../../components/AdminBackLink.vue'

const route = useRoute()
const router = useRouter()
const task = ref(null)
const loading = ref(false)
const errorMessage = ref('')
const savingClueId = ref(null)
const similarityLoading = ref(false)
const similarityError = ref('')
const similarityResult = ref(null)
const eventsLoading = ref(false)
const eventsError = ref('')
const eventActionLoading = ref(false)
const preparingEventId = ref(null)
const evidenceLoadingEventId = ref(null)
const synthesizingEventId = ref(null)
const synthesisActionId = ref(null)
const articleCreatingId = ref(null)
const synthesisResults = ref({})
const synthesisHistories = ref({})
const eventGrouping = ref({ events: [], ungrouped_clues: [] })
const selectedUngroupedClueIds = ref([])
const createEventDialog = ref({ visible: false, title: '' })
const renameEventDialog = ref({ visible: false, eventId: null, title: '' })
const addCluesDialog = ref({ visible: false, eventId: null, eventTitle: '', clueIds: [] })
const contentDialog = ref({ visible: false, loading: false, detail: null })
const evidenceDialog = ref({
  visible: false,
  loading: false,
  detail: null,
  expandedClueIds: [],
})

const relevanceOptions = [
  { label: '明显相关', value: 2 },
  { label: '一般相关', value: 1 },
  { label: '明显偏题', value: 0 },
]
const labeledCount = computed(() => (
  task.value?.items.filter(
    (item) => item.relevance_label !== null && item.relevance_label !== undefined,
  ).length || 0
))

const workflowSteps = computed(() => {
  const eventCount = eventGrouping.value.events.length
  const hasPrepared = eventGrouping.value.events.some((event) =>
    event.clues.some((clue) => clue.content_status === 'completed'),
  )
  const historyVersions = Object.values(synthesisHistories.value)
  const hasSynthesis = historyVersions.some((items) => Array.isArray(items) && items.length > 0)
  const results = Object.values(synthesisResults.value)
  const hasApproved = results.some((result) => result && result.status === 'approved')
  const hasArticle = results.some((result) => result && result.article)
  const steps = [
    {
      key: 'search',
      label: '创建搜索任务',
      hint: '后台完成Tavily搜索',
      done: task.value?.status === 'completed',
    },
    {
      key: 'event',
      label: '选择线索创建事件',
      hint: '从未分组线索中多选分组',
      done: eventCount > 0,
    },
    {
      key: 'prepare',
      label: '准备事件材料',
      hint: '先准备材料才能查询证据/AI整理',
      done: hasPrepared,
    },
    {
      key: 'synthesis',
      label: 'AI整理事件',
      hint: '生成事件整理版本',
      done: hasSynthesis,
    },
    {
      key: 'approve',
      label: '确认采用并创建文稿',
      hint: '确认版本后生成正式文稿',
      done: hasApproved || hasArticle,
    },
  ]
  const firstUndone = steps.findIndex((step) => !step.done)
  return steps.map((step, index) => ({
    ...step,
    index: index + 1,
    current: index === firstUndone,
  }))
})

const timeRangeText = { day: '最近一天', week: '最近一周', month: '最近一月', year: '最近一年' }
const statusMeta = {
  running: { label: '进行中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'danger' },
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
}

function formatScore(score) {
  return Number.isFinite(Number(score)) ? Number(score).toFixed(2) : '0.00'
}

function formatSemanticScore(score) {
  if (score === null || score === undefined || score === '') return '未计算'
  return Number.isFinite(Number(score)) ? Number(score).toFixed(3) : '未计算'
}

function formatSimilarityScore(score) {
  return Number.isFinite(Number(score)) ? Number(score).toFixed(3) : '—'
}

function relevanceText(label) {
  return ({ 0: '明显偏题', 1: '一般相关', 2: '明显相关' })[label] || '未标注'
}

function contentStatusText(status) {
  return ({ pending: '获取中', completed: '已获取', failed: '获取失败' })[status] || '未获取'
}

function synthesisStatusText(status) {
  return ({ generated: '待确认', approved: '已确认', rejected: '已弃用' })[status] || status
}

function synthesisStatusType(status) {
  return ({ generated: 'warning', approved: 'success', rejected: 'info' })[status] || 'info'
}

function eventCompletedCount(event) {
  return event.clues.filter((clue) => clue.content_status === 'completed').length
}

function listText(items) {
  return Array.isArray(items) && items.length ? items.join('；') : '未提供。'
}

function shortHash(value) {
  return typeof value === 'string' && value.length >= 8 ? value.slice(0, 8) : '—'
}

function isEvidenceSourceExpanded(clueId) {
  return evidenceDialog.value.expandedClueIds.includes(clueId)
}

function toggleEvidenceSource(clueId) {
  const current = evidenceDialog.value.expandedClueIds
  evidenceDialog.value.expandedClueIds = current.includes(clueId)
    ? current.filter((id) => id !== clueId)
    : [...current, clueId]
}

async function viewEventEvidence(event) {
  if (evidenceLoadingEventId.value !== null) return
  evidenceLoadingEventId.value = event.id
  evidenceDialog.value = {
    visible: true,
    loading: true,
    detail: null,
    expandedClueIds: [],
  }
  try {
    evidenceDialog.value.detail = await smartCollectApi.getEventEvidence(task.value.id, event.id)
  } catch (error) {
    evidenceDialog.value.visible = false
    ElMessage.error(String(error || '事件证据读取失败'))
  } finally {
    evidenceDialog.value.loading = false
    evidenceLoadingEventId.value = null
  }
}

async function synthesizeEvent(event) {
  if (synthesizingEventId.value !== null) return
  synthesizingEventId.value = event.id
  try {
    const response = await smartCollectApi.synthesizeEvent(task.value.id, event.id)
    synthesisResults.value = { ...synthesisResults.value, [event.id]: response }
    await loadSynthesisHistory(event, false)
    ElMessage.success(`AI事件整理 v${response.version} 已保存，请编辑审核结果与来源引用`)
  } catch (error) {
    ElMessage.error(String(error || 'AI事件整理失败'))
  } finally {
    synthesizingEventId.value = null
  }
}

async function viewSynthesisVersion(event, synthesisId) {
  try {
    const detail = await smartCollectApi.getEventSynthesis(
      task.value.id,
      event.id,
      synthesisId,
    )
    synthesisResults.value = { ...synthesisResults.value, [event.id]: detail }
  } catch (error) {
    ElMessage.error(String(error || 'AI整理版本读取失败'))
  }
}

async function reviewSynthesis(event, action) {
  const current = synthesisResults.value[event.id]
  if (!current || synthesisActionId.value !== null) return
  const isApprove = action === 'approve'
  const message = isApprove
    ? `确认采用事件「${event.title}」的 v${current.version}？同一事件只能有一个已确认版本。`
    : `确定废弃事件「${event.title}」的 v${current.version}？该历史版本仍会保留。`
  try {
    await ElMessageBox.confirm(message, isApprove ? '确认采用AI版本' : '废弃AI版本', {
      type: isApprove ? 'success' : 'warning',
    })
  } catch {
    return
  }

  synthesisActionId.value = current.id
  try {
    const result = isApprove
      ? await smartCollectApi.approveEventSynthesis(task.value.id, event.id, current.id)
      : await smartCollectApi.rejectEventSynthesis(task.value.id, event.id, current.id)
    synthesisResults.value = { ...synthesisResults.value, [event.id]: result }
    await loadSynthesisHistory(event, false)
    ElMessage.success(isApprove ? '该AI整理版本已确认采用' : '该AI整理版本已弃用')
  } catch (error) {
    ElMessage.error(String(error || 'AI整理状态更新失败'))
  } finally {
    synthesisActionId.value = null
  }
}

async function createArticleFromSynthesis(event) {
  const current = synthesisResults.value[event.id]
  if (!current || current.status !== 'approved' || articleCreatingId.value !== null) return
  try {
    await ElMessageBox.confirm(
      `将事件「${event.title}」的 v${current.version} 转换为CMS草稿？创建后仍需编辑、选择栏目并提交审核。`,
      '创建正式文稿',
      { type: 'info' },
    )
  } catch {
    return
  }

  articleCreatingId.value = current.id
  try {
    const response = await smartCollectApi.createArticleFromSynthesis(
      task.value.id,
      event.id,
      current.id,
    )
    synthesisResults.value = {
      ...synthesisResults.value,
      [event.id]: { ...current, article: response.article },
    }
    await loadSynthesisHistory(event, false)
    ElMessage.success(`文稿 #${response.article.id} 已创建为草稿`)
  } catch (error) {
    ElMessage.error(String(error || 'CMS文稿草稿创建失败'))
  } finally {
    articleCreatingId.value = null
  }
}

function openArticleEditor(articleId) {
  router.push(`/admin/articles/${articleId}/edit`)
}

async function loadSynthesisHistory(event, selectLatest = true) {
  const history = await smartCollectApi.listEventSyntheses(task.value.id, event.id)
  synthesisHistories.value = {
    ...synthesisHistories.value,
    [event.id]: history.items,
  }
  const selected = synthesisResults.value[event.id]
  const selectedStillExists = selected && history.items.some((item) => item.id === selected.id)
  if (selectLatest && history.items.length && !selectedStillExists) {
    await viewSynthesisVersion(event, history.items[0].id)
  }
}

async function prepareEventContent(event) {
  if (preparingEventId.value !== null) return
  preparingEventId.value = event.id
  try {
    const result = await smartCollectApi.prepareEventContent(task.value.id, event.id)
    await loadEvents()
    if (result.failed) {
      ElMessage.warning(
        `事件材料准备完成：${result.completed}/${result.total} 成功，${result.failed} 条失败`,
      )
    } else {
      ElMessage.success(`事件材料准备完成：${result.completed}/${result.total} 获取成功`)
    }
  } catch (error) {
    ElMessage.error(String(error || '事件材料准备失败'))
  } finally {
    preparingEventId.value = null
  }
}

async function viewContent(clue) {
  contentDialog.value = { visible: true, loading: true, detail: null }
  try {
    contentDialog.value.detail = await smartCollectApi.getClueContent(clue.clue_id)
  } catch (error) {
    contentDialog.value.visible = false
    ElMessage.error(String(error || '正文读取失败'))
  } finally {
    contentDialog.value.loading = false
  }
}

async function loadEvents() {
  if (!task.value) return
  eventsLoading.value = true
  eventsError.value = ''
  try {
    eventGrouping.value = await smartCollectApi.listEvents(task.value.id)
    await Promise.all(
      eventGrouping.value.events.map((event) => loadSynthesisHistory(event, true)),
    )
    const ungroupedIds = new Set(
      eventGrouping.value.ungrouped_clues.map((clue) => clue.clue_id),
    )
    selectedUngroupedClueIds.value = selectedUngroupedClueIds.value.filter(
      (clueId) => ungroupedIds.has(clueId),
    )
  } catch (error) {
    eventsError.value = String(error || '人工事件加载失败')
  } finally {
    eventsLoading.value = false
  }
}

function openCreateEvent() {
  if (selectedUngroupedClueIds.value.length === 0) {
    ElMessage.warning('请至少选择1条未分组线索')
    return
  }
  createEventDialog.value = { visible: true, title: '' }
}

async function submitCreateEvent() {
  const title = createEventDialog.value.title.trim()
  if (!title) {
    ElMessage.warning('事件标题不能为空')
    return
  }
  if (selectedUngroupedClueIds.value.length === 0 || eventActionLoading.value) return
  const clueCount = selectedUngroupedClueIds.value.length
  eventActionLoading.value = true
  try {
    await smartCollectApi.createEvent(task.value.id, {
      title,
      clue_ids: [...selectedUngroupedClueIds.value],
    })
    createEventDialog.value.visible = false
    selectedUngroupedClueIds.value = []
    await loadEvents()
    ElMessage.success(clueCount === 1 ? '人工事件已创建（单来源事件）' : '人工事件已创建')
  } catch (error) {
    ElMessage.error(String(error || '人工事件创建失败'))
  } finally {
    eventActionLoading.value = false
  }
}

function openRenameEvent(event) {
  renameEventDialog.value = { visible: true, eventId: event.id, title: event.title }
}

async function submitRenameEvent() {
  const title = renameEventDialog.value.title.trim()
  if (!title) {
    ElMessage.warning('事件标题不能为空')
    return
  }
  if (eventActionLoading.value) return
  eventActionLoading.value = true
  try {
    await smartCollectApi.updateEvent(
      task.value.id,
      renameEventDialog.value.eventId,
      { title },
    )
    renameEventDialog.value.visible = false
    await loadEvents()
    ElMessage.success('事件标题已更新')
  } catch (error) {
    ElMessage.error(String(error || '事件标题保存失败'))
  } finally {
    eventActionLoading.value = false
  }
}

function openAddClues(event) {
  if (!eventGrouping.value.ungrouped_clues.length) {
    ElMessage.info('当前没有可加入的未分组线索')
    return
  }
  addCluesDialog.value = {
    visible: true,
    eventId: event.id,
    eventTitle: event.title,
    clueIds: [],
  }
}

async function submitAddClues() {
  if (!addCluesDialog.value.clueIds.length || eventActionLoading.value) return
  eventActionLoading.value = true
  try {
    await smartCollectApi.addEventClues(
      task.value.id,
      addCluesDialog.value.eventId,
      { clue_ids: [...addCluesDialog.value.clueIds] },
    )
    addCluesDialog.value.visible = false
    await loadEvents()
    ElMessage.success('线索已加入事件')
  } catch (error) {
    ElMessage.error(String(error || '线索加入事件失败'))
  } finally {
    eventActionLoading.value = false
  }
}

async function removeEventClue(event, clue) {
  if (eventActionLoading.value) return
  eventActionLoading.value = true
  try {
    await smartCollectApi.removeEventClue(task.value.id, event.id, clue.clue_id)
    await loadEvents()
    ElMessage.success('线索已移回未分组区域')
  } catch (error) {
    ElMessage.error(String(error || '线索移出事件失败'))
  } finally {
    eventActionLoading.value = false
  }
}

async function deleteEvent(event) {
  try {
    await ElMessageBox.confirm(
      `确定删除事件「${event.title}」？只会删除事件及分组关系，不会删除新闻线索。`,
      '删除人工事件',
      { type: 'warning' },
    )
  } catch {
    return
  }
  if (eventActionLoading.value) return
  eventActionLoading.value = true
  try {
    await smartCollectApi.deleteEvent(task.value.id, event.id)
    await loadEvents()
    ElMessage.success('人工事件已删除，新闻线索保持不变')
  } catch (error) {
    ElMessage.error(String(error || '人工事件删除失败'))
  } finally {
    eventActionLoading.value = false
  }
}

async function analyzeSimilarity() {
  if (similarityLoading.value) return
  similarityLoading.value = true
  similarityError.value = ''
  try {
    similarityResult.value = await smartCollectApi.similarityPairs(task.value.id, { limit: 10 })
  } catch (error) {
    similarityError.value = String(error || '新闻相似度分析失败')
    ElMessage.error(similarityError.value)
  } finally {
    similarityLoading.value = false
  }
}

async function saveRelevance(item, relevanceLabel) {
  if (savingClueId.value !== null) return
  savingClueId.value = item.clue_id
  try {
    const result = await smartCollectApi.updateRelevance(task.value.id, item.clue_id, {
      relevance_label: relevanceLabel,
    })
    item.relevance_label = result.relevance_label
    ElMessage.success(relevanceLabel === null ? '已恢复为未标注' : '人工判断已保存')
  } catch (error) {
    ElMessage.error(String(error || '人工判断保存失败'))
  } finally {
    savingClueId.value = null
  }
}

async function loadTask() {
  loading.value = true
  errorMessage.value = ''
  try {
    task.value = await smartCollectApi.getTask(route.params.id)
    similarityResult.value = null
    similarityError.value = ''
    synthesisResults.value = {}
    synthesisHistories.value = {}
    await loadEvents()
  } catch (error) {
    errorMessage.value = String(error || '任务详情加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadTask)
</script>

<style scoped>
.page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.page-title { margin: 8px 0 0; font-size: 24px; }
.task-card { margin-bottom: 16px; }
.events-card { margin-bottom: 16px; }
.events-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.events-head p { margin: 6px 0 0; color: var(--color-text-muted); font-size: 13px; line-height: 1.6; }
.events-head > span { color: var(--color-text-muted); font-size: 13px; }
.events-section h2 { margin: 0; color: var(--color-text); font-size: 16px; }
.event-list { display: grid; gap: 12px; margin-top: 12px; }
.event-item { padding: 14px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg); }
.event-item__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.event-item__head h3 { margin: 0 0 5px; color: var(--color-text); font-size: 16px; }
.event-item__head span { color: var(--color-text-muted); font-size: 12px; }
.event-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }
.event-clue-list { display: grid; gap: 8px; margin-top: 12px; }
.event-clue-item { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 10px 12px; border-radius: var(--radius-sm); background: var(--color-surface); }
.event-clue-item > div { display: grid; min-width: 0; gap: 4px; }
.event-clue-item span, .event-clue-item small { color: var(--color-text-muted); font-size: 12px; }
.event-clue-item strong { color: var(--color-text); font-size: 14px; line-height: 1.5; }
.event-clue-actions { display: flex; flex: none; align-items: center; gap: 4px; }
.synthesis-history { display: grid; gap: 10px; margin-top: 14px; padding-top: 14px; border-top: 1px dashed var(--color-border); }
.synthesis-history__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.synthesis-history__head strong { color: var(--color-text); font-size: 14px; }
.synthesis-history__head span, .synthesis-history__empty { margin: 0; color: var(--color-text-muted); font-size: 12px; }
.synthesis-history__items { display: flex; flex-wrap: wrap; gap: 8px; }
.synthesis-version { display: grid; grid-template-columns: auto auto; align-items: center; gap: 4px 8px; min-width: 170px; padding: 9px 11px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); color: var(--color-text); text-align: left; cursor: pointer; }
.synthesis-version:hover, .synthesis-version.is-active { border-color: var(--el-color-primary); box-shadow: 0 0 0 1px var(--el-color-primary-light-7); }
.synthesis-version > span, .synthesis-version > small { grid-column: 1 / -1; overflow: hidden; color: var(--color-text-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.synthesis-result { display: grid; gap: 14px; margin-top: 14px; padding: 14px; border: 1px solid var(--el-color-success-light-5); border-radius: var(--radius-sm); background: var(--color-surface); }
.synthesis-result__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.synthesis-result__head > div { display: flex; align-items: center; gap: 8px; }
.synthesis-result__head strong { color: var(--color-text); font-size: 16px; }
.synthesis-result__head span { color: var(--color-text-muted); font-size: 12px; text-align: right; }
.synthesis-review-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.synthesis-review-actions > span { margin-left: auto; color: var(--color-text-muted); font-size: 12px; }
.synthesis-summary { margin: 0; color: var(--color-text); font-size: 15px; line-height: 1.8; }
.synthesis-section h4 { margin: 0 0 7px; color: var(--color-text); font-size: 14px; }
.synthesis-section p, .synthesis-section ol, .synthesis-section ul { margin: 0; color: var(--color-text-secondary); font-size: 13px; line-height: 1.8; }
.synthesis-section li + li { margin-top: 6px; }
.synthesis-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.source-links { display: inline-flex; flex-wrap: wrap; margin-left: 5px; }
.synthesis-snapshot { display: grid; gap: 7px; }
.synthesis-snapshot__item { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; padding: 7px 9px; border-radius: var(--radius-sm); background: var(--color-bg); }
.synthesis-snapshot__item > span { color: var(--color-text-secondary); font-size: 12px; }
.content-state--completed { color: var(--el-color-success) !important; }
.content-state--failed { color: var(--el-color-danger) !important; }
.content-state--pending { color: var(--el-color-warning) !important; }
.evidence-dialog-body { min-height: 180px; }
.evidence-dialog-body h3 { margin: 0; color: var(--color-text); font-size: 18px; }
.evidence-summary { margin: 8px 0 14px; color: var(--color-text-muted); font-size: 13px; }
.evidence-source-list { display: grid; gap: 10px; margin-top: 14px; }
.evidence-source-item { padding: 12px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); }
.evidence-source-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.evidence-source-head > div { min-width: 0; }
.evidence-source-head span, .evidence-source-head small { color: var(--color-text-muted); font-size: 12px; }
.evidence-source-head h4 { margin: 5px 0; color: var(--color-text); font-size: 14px; line-height: 1.5; }
.evidence-source-content { max-height: 42vh; margin-top: 10px; overflow-y: auto; padding: 12px; border-radius: var(--radius-sm); background: var(--color-bg); color: var(--color-text-secondary); font-size: 13px; line-height: 1.8; white-space: pre-wrap; }
.ungrouped-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.ungrouped-head > div { display: flex; align-items: baseline; gap: 8px; }
.ungrouped-head span { color: var(--color-text-muted); font-size: 13px; }
.ungrouped-list, .dialog-clue-list { display: grid; gap: 8px; margin-top: 12px; }
.dialog-clue-list { max-height: 360px; overflow-y: auto; }
.ungrouped-item { width: 100%; height: auto; margin: 0; padding: 10px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); }
.ungrouped-item :deep(.el-checkbox__label) { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; width: 100%; gap: 8px; white-space: normal; }
.ungrouped-rank, .ungrouped-source { color: var(--color-text-muted); font-size: 12px; }
.ungrouped-title { color: var(--color-text); font-size: 14px; line-height: 1.5; }
.dialog-hint { margin: 0 0 12px; color: var(--color-text-secondary); font-size: 13px; }
.content-dialog-body { min-height: 160px; }
.content-dialog-body h3 { margin: 0; color: var(--color-text); font-size: 18px; line-height: 1.5; }
.content-dialog-meta { margin: 8px 0 14px; color: var(--color-text-muted); font-size: 12px; }
.content-text { max-height: 58vh; overflow-y: auto; padding: 16px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg); color: var(--color-text-secondary); font-size: 14px; line-height: 1.8; white-space: pre-wrap; }
.similarity-card { margin-bottom: 16px; }
.similarity-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.similarity-head p { margin: 6px 0 0; color: var(--color-text-muted); font-size: 13px; line-height: 1.6; }
.similarity-summary { margin: 0 0 12px; color: var(--color-text-secondary); font-size: 13px; }
.similarity-list { display: grid; gap: 12px; }
.similarity-item { padding: 14px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); }
.similarity-score { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.similarity-score span { color: var(--color-text-muted); font-size: 12px; }
.similarity-score strong { color: var(--el-color-primary); font-size: 15px; }
.similarity-clues { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.similarity-clues > div { padding: 10px; border-radius: var(--radius-sm); background: var(--color-bg); }
.similarity-clues span { color: var(--color-text-muted); font-size: 12px; }
.similarity-clues h3 { margin: 5px 0 0; color: var(--color-text); font-size: 14px; line-height: 1.5; }
.result-card-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.result-card-head span { color: var(--color-text-muted); font-size: 13px; }
.error-text { color: var(--el-color-danger); }
.result-list { display: grid; gap: 12px; }
.result-item { padding: 16px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-surface); }
.result-item__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.title-line { display: flex; align-items: flex-start; gap: 8px; min-width: 0; }
.rank { flex: none; color: var(--color-text-muted); font-size: 13px; line-height: 25px; }
.result-item__head h2 { margin: 0; color: var(--color-text); font-size: 17px; line-height: 1.5; }
.result-snippet { margin: 10px 0; color: var(--color-text-secondary); font-size: 14px; line-height: 1.7; white-space: pre-wrap; }
.relevance-row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
.relevance-label { color: var(--color-text-secondary); font-size: 13px; }
.unlabeled-text { color: var(--color-text-muted); font-size: 13px; }
.result-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: var(--color-text-muted); font-size: 13px; }
.score-list { display: flex; flex-wrap: wrap; gap: 8px 16px; }
@media (max-width: 700px) {
  .page-head { align-items: flex-start; }
  .events-head, .event-item__head, .ungrouped-head { flex-direction: column; }
  .event-actions { justify-content: flex-start; }
  .event-clue-item { flex-direction: column; }
  .synthesis-result__head { flex-direction: column; }
  .synthesis-result__head span { text-align: left; }
  .synthesis-review-actions > span { width: 100%; margin-left: 0; }
  .synthesis-columns { grid-template-columns: 1fr; }
  .evidence-source-head { flex-direction: column; }
  .ungrouped-item :deep(.el-checkbox__label) { grid-template-columns: auto minmax(0, 1fr); }
  .ungrouped-source { grid-column: 2; }
  .similarity-head { flex-direction: column; }
  .similarity-clues { grid-template-columns: 1fr; }
  :deep(.el-descriptions) { overflow-x: auto; }
}

/* ============================================================
 * 智能采编工作台视觉升级（仅样式覆盖，业务逻辑不变）
 * ============================================================ */
.task-detail-page {
  display: grid;
  gap: var(--space-5);
}

.page-head {
  align-items: center;
  padding: var(--space-2) 0;
}

.page-title {
  margin: 0;
  color: var(--color-ink);
  font-family: var(--font-heading);
  font-size: var(--text-2xl);
  font-weight: 700;
  line-height: var(--leading-tight);
}

.workflow-steps {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-2);
}

.workflow-step {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  transition: border-color var(--dur-fast) var(--ease-out),
    background-color var(--dur-fast) var(--ease-out);
}

.workflow-step.is-done {
  border-color: color-mix(in srgb, var(--color-success) 45%, var(--color-rule));
  background: color-mix(in srgb, var(--color-success) 6%, var(--color-surface));
}

.workflow-step.is-current {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-soft);
}

.workflow-step__num {
  flex: none;
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border-radius: 50%;
  background: var(--color-paper-2);
  color: var(--color-ink-3);
  font-size: var(--text-xs);
  font-weight: 800;
}

.workflow-step.is-done .workflow-step__num {
  background: var(--color-success);
  color: #fff;
}

.workflow-step.is-current .workflow-step__num {
  background: var(--color-primary);
  color: #fff;
}

.workflow-step > div {
  min-width: 0;
}

.workflow-step strong,
.workflow-step small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workflow-step strong {
  color: var(--color-ink);
  font-size: var(--text-sm);
  font-weight: 700;
  line-height: var(--leading-tight);
}

.workflow-step small {
  margin-top: var(--space-1);
  color: var(--color-ink-3);
  font-size: 11px;
  line-height: 1.4;
}

.task-card,
.events-card,
.similarity-card {
  overflow: hidden;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}

.task-card :deep(.el-card__body),
.events-card :deep(.el-card__body),
.similarity-card :deep(.el-card__body) {
  padding: var(--space-5);
}

.task-card :deep(.el-descriptions) {
  --el-descriptions-table-border: 1px solid var(--color-rule);
  --el-descriptions-item-bordered-label-background: var(--color-paper-2);
}

.task-card :deep(.el-descriptions__label) {
  color: var(--color-ink-3);
  font-weight: 600;
}

.task-card :deep(.el-descriptions__content) {
  color: var(--color-ink);
}

.events-head,
.similarity-head,
.result-card-head {
  align-items: center;
}

.events-head strong,
.similarity-head strong,
.result-card-head strong {
  color: var(--color-ink);
  font-family: var(--font-heading);
  font-size: var(--text-lg);
  font-weight: 700;
}

.events-head p,
.similarity-head p {
  color: var(--color-ink-3);
  font-size: var(--text-xs);
  line-height: var(--leading-normal);
}

.events-head > span,
.result-card-head span {
  padding: var(--space-1) var(--space-3);
  background: var(--color-paper-2);
  border: 1px solid var(--color-rule);
  border-radius: 999px;
  color: var(--color-ink-3);
  font-size: var(--text-xs);
  font-weight: 700;
}

.events-section {
  margin-top: var(--space-4);
}

.events-section > h2 {
  color: var(--color-ink);
  font-size: var(--text-base);
  font-weight: 700;
}

.event-list {
  display: grid;
  gap: var(--space-4);
  margin-top: var(--space-4);
}

.event-item {
  overflow: hidden;
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-left: 3px solid var(--color-primary);
  border-radius: var(--radius-md);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.event-item__head {
  align-items: flex-start;
}

.event-item__head h3 {
  color: var(--color-ink);
  font-family: var(--font-heading);
  font-size: var(--text-lg);
  font-weight: 700;
  line-height: var(--leading-tight);
}

.event-item__head > div > span {
  color: var(--color-ink-3);
  font-size: var(--text-xs);
}

.event-actions {
  gap: var(--space-1);
}

.event-actions :deep(.el-button) {
  min-height: 32px;
  border-radius: var(--radius-sm);
}

.event-clue-list {
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.event-clue-item {
  padding: var(--space-3) var(--space-4);
  background: var(--color-paper-2);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-sm);
}

.event-clue-item strong {
  color: var(--color-ink);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
}

.event-clue-item small {
  color: var(--color-ink-3);
}

.synthesis-history {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
}

.synthesis-history__head strong {
  color: var(--color-ink);
  font-size: var(--text-sm);
  font-weight: 700;
}

.synthesis-version {
  border-color: var(--color-rule);
  background: var(--color-surface);
}

.synthesis-version:hover,
.synthesis-version.is-active {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-soft);
}

.synthesis-result {
  padding: var(--space-4);
  background: color-mix(in srgb, var(--color-primary-soft) 18%, var(--color-surface));
  border: 1px solid color-mix(in srgb, var(--color-primary) 28%, var(--color-rule));
  border-radius: var(--radius-md);
}

.synthesis-result__head strong {
  color: var(--color-ink);
  font-family: var(--font-heading);
  font-size: var(--text-base);
}

.synthesis-summary {
  color: var(--color-ink);
  font-size: var(--text-sm);
  line-height: var(--leading-loose);
}

.synthesis-section h4 {
  color: var(--color-ink);
  font-size: var(--text-sm);
  font-weight: 700;
}

.synthesis-section p,
.synthesis-section ol,
.synthesis-section ul {
  color: var(--color-ink-2);
  line-height: var(--leading-loose);
}

.ungrouped-head {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px dashed var(--color-rule-strong);
}

.ungrouped-head > div {
  align-items: baseline;
}

.ungrouped-head h2 {
  color: var(--color-ink);
  font-size: var(--text-base);
  font-weight: 700;
}

.ungrouped-list {
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.ungrouped-item {
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-sm);
  transition: border-color var(--dur-fast) var(--ease-out),
    background-color var(--dur-fast) var(--ease-out);
}

.ungrouped-item:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.similarity-item,
.result-item {
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-md);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.similarity-score strong {
  color: var(--color-primary);
}

.result-item__head h2 {
  color: var(--color-ink);
  font-family: var(--font-heading);
  font-size: var(--text-lg);
  line-height: var(--leading-snug);
}

.result-snippet {
  color: var(--color-ink-2);
  line-height: var(--leading-loose);
}

.content-state--completed {
  color: var(--color-success) !important;
}

.content-state--failed {
  color: var(--color-danger) !important;
}

.content-state--pending {
  color: var(--color-warning, #d97706) !important;
}

.error-text {
  color: var(--color-danger);
}

@media (max-width: 1100px) {
  .workflow-steps {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 700px) {
  .workflow-steps {
    grid-template-columns: 1fr;
  }

  .workflow-step strong,
  .workflow-step small {
    white-space: normal;
  }

  .task-card :deep(.el-card__body),
  .events-card :deep(.el-card__body),
  .similarity-card :deep(.el-card__body) {
    padding: var(--space-4);
  }
}

/* 缩放安全：小屏/浏览器缩放时不允许横向溢出 */
.task-detail-page {
  width: 100%;
  min-width: 0;
  overflow-x: hidden;
  box-sizing: border-box;
}

.page-head {
  flex-wrap: wrap;
  min-width: 0;
}

.page-head > div {
  min-width: 0;
}

.page-title {
  overflow-wrap: anywhere;
}

.workflow-steps {
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}

.workflow-step {
  min-width: 0;
}

.workflow-step strong,
.workflow-step small {
  white-space: normal;
  overflow-wrap: anywhere;
}

.task-card,
.events-card,
.similarity-card {
  width: 100%;
  min-width: 0;
}

.task-card :deep(.el-descriptions),
.events-card :deep(.el-table),
.similarity-card :deep(.el-table) {
  width: 100%;
  min-width: 0;
  overflow-x: auto;
}

.events-head,
.event-item__head,
.event-actions,
.synthesis-result__head,
.synthesis-review-actions,
.ungrouped-head,
.similarity-head,
.similarity-score,
.result-item__head,
.result-meta,
.result-card-head {
  flex-wrap: wrap;
  min-width: 0;
}

.event-item,
.event-clue-item,
.synthesis-version,
.synthesis-result,
.similarity-item,
.similarity-clues > div,
.result-item {
  min-width: 0;
}

.event-actions {
  width: 100%;
  justify-content: flex-start;
}

.event-clue-item {
  gap: var(--space-3);
}

.synthesis-result__head span {
  text-align: left;
}

.similarity-clues {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.result-list,
.similarity-list,
.event-list,
.ungrouped-list {
  min-width: 0;
}

.result-item__head .title-line {
  min-width: 0;
}

.result-item__head h2 {
  overflow-wrap: anywhere;
}

.result-snippet,
.synthesis-summary,
.content-text,
.evidence-source-content {
  overflow-wrap: anywhere;
}

:global(.el-dialog) {
  max-width: calc(100vw - 24px);
}

:global(.el-dialog .el-dialog__body) {
  overflow-x: auto;
}

@media (max-width: 640px) {
  .similarity-clues {
    grid-template-columns: 1fr;
  }

  .event-actions :deep(.el-button) {
    flex: 1 1 auto;
  }
}
</style>
