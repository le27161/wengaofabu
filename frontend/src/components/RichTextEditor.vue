<template>
  <div class="rich-editor">
    <Toolbar
      class="rich-editor__toolbar"
      :editor="editorRef"
      :defaultConfig="toolbarConfig"
      mode="default"
    />
    <Editor
      v-model="valueHtml"
      class="rich-editor__body"
      :defaultConfig="editorConfig"
      mode="default"
      @onCreated="handleCreated"
      @onChange="handleChange"
    />
  </div>
</template>

<script setup>
// wangEditor 5（MIT 开源）Vue3 封装：正文 HTML 双向绑定 + 纯文本回调
// 用法：<RichTextEditor v-model="form.content" @text-change="(t) => (form.content_source = t)" />
import { nextTick, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import '@wangeditor/editor/dist/css/style.css'
import { resourceApi } from '../api'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请输入正文内容…' },
  // 编辑区最小高度（px），默认 420
  minHeight: { type: Number, default: 420 },
})
const emit = defineEmits(['update:modelValue', 'text-change'])

const editorRef = shallowRef()
const valueHtml = ref(props.modelValue)

const toolbarConfig = {
  // 排除视频/全屏/代码块等暂不需要的菜单，保留常用排版工具
  excludeKeys: ['group-video', 'fullScreen', 'insertVideo', 'codeBlock', 'group-image'],
}

const editorConfig = {
  placeholder: props.placeholder,
  MENU_CONF: {
    uploadImage: {
      // 图片上传走项目资源库（/api/resources/upload），成功后插入正文
      async customUpload(file, insertFn) {
        const formData = new FormData()
        formData.append('file', file)
        try {
          const res = await resourceApi.upload(formData)
          const url = res.resource?.url
          if (!url) throw new Error('上传接口未返回图片地址')
          insertFn(url, file.name, url)
        } catch (e) {
          ElMessage.error(`图片上传失败：${String(e)}`)
        }
      },
    },
  },
}

function handleCreated(editor) {
  editorRef.value = editor
}

function handleChange(editor) {
  emit('update:modelValue', editor.getHtml())
  emit('text-change', editor.getText())
}

// 外部（如 AI 协作台另一个编辑器实例）更新 content 时，同步到本实例
watch(
  () => props.modelValue,
  async (val) => {
    // 先等 wangEditor 自身 v-model 同步完成，避免每次输入时 setHtml 重置光标
    await nextTick()
    if (editorRef.value && val !== editorRef.value.getHtml()) {
      editorRef.value.setHtml(val || '<p><br></p>')
    }
  },
)

onBeforeUnmount(() => {
  if (editorRef.value) {
    editorRef.value.destroy()
    editorRef.value = null
  }
})
</script>

<style scoped>
.rich-editor {
  border: 1px solid var(--color-rule, #e2e8f0);
  border-radius: var(--radius-sm, 6px);
  overflow: hidden;
  background: var(--color-paper, #fff);
}

.rich-editor__toolbar {
  border-bottom: 1px solid var(--color-rule, #e2e8f0);
  z-index: 2;
}

.rich-editor__body {
  /* 内容区高度由 wangEditor 内部样式控制，这里通过 :deep 设置最小高度 */
}

.rich-editor__body :deep(.w-e-text-container) {
  min-height: v-bind(minHeight + 'px');
  color: var(--color-ink, #1e293b);
  font-size: 15px;
  line-height: var(--leading-loose, 1.85);
  background: var(--color-paper, #fff);
}

.rich-editor__body :deep(.w-e-text-container [data-slate-editor]) {
  padding: var(--space-4, 16px);
}
</style>
