// 文本工具：HTML 正文 → 纯文本（与后端 services/text_utils.py 逻辑一致）
export function stripHtml(html) {
  if (!html) return ''
  const text = String(html)
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
  return text.replace(/\s+/g, ' ').trim()
}
