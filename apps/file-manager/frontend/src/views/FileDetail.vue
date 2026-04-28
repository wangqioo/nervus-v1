<template>
  <div class="page">
    <div class="detail-bg"></div>
    <header class="app-hdr">
      <button class="app-back" @click="$router.back()">‹</button>
      <span class="app-hdr-ttl">文件详情</span>
      <button class="app-hdr-act" @click="confirmDelete" title="删除">🗑</button>
    </header>

    <div class="app-body">
      <div v-if="loading" class="center-tip">加载中...</div>
      <div v-else-if="!file" class="center-tip">文件不存在</div>

      <template v-else>
        <!-- Hero -->
        <div class="hero gc" :class="{ 'hero-img': file.type === 'image' || (file.type === 'link' && file.og_image) }">
          <div class="hero-glow"></div>
          <!-- Image preview -->
          <template v-if="file.type === 'image'">
            <div class="hero-img-wrap">
              <img
                :src="`/api/files/${file.id}/download`"
                class="hero-img-el"
                loading="lazy"
                @error="e => e.target.closest('.hero-img-wrap').innerHTML = '<span style=\'font-size:52px\'>🖼</span>'"
              />
            </div>
          </template>
          <!-- Link cover image -->
          <template v-else-if="file.type === 'link' && file.og_image">
            <div class="hero-img-wrap">
              <img
                :src="imgUrl(file.og_image)"
                class="hero-img-el"
                loading="lazy"
                @error="e => e.target.closest('.hero-img-wrap').innerHTML = '<span style=\'font-size:52px\'>🔗</span>'"
              />
            </div>
          </template>
          <div v-else class="hero-icon">{{ typeIcon }}</div>
          <div class="hero-name">{{ file.type === 'link' ? (file.summary || file.original_filename) : file.original_filename }}</div>
          <div class="hero-badges">
            <span class="type-chip" :class="file.type">{{ typeLabel }}</span>
            <span class="status-chip" :class="file.status">{{ statusLabel }}</span>
          </div>
          <div class="hero-time">{{ timeStr }}</div>
        </div>

        <!-- AI Summary -->
        <div class="info-card gc">
          <div class="card-label">AI 简介</div>
          <div v-if="file.status === 'pending'" class="state-row">
            <div class="mini-orb"></div>
            <span>AI 分析中，请稍候...</span>
            <button class="action-link" @click="triggerAnalyze" :disabled="analyzing">立即分析</button>
          </div>
          <div v-else-if="file.status === 'failed'" class="state-row failed">
            <span>✕ {{ file.error || '分析失败' }}</span>
            <button class="action-link" @click="triggerAnalyze" :disabled="analyzing">重试</button>
          </div>
          <template v-else>
            <div v-if="file.type !== 'link'" class="summary-text">{{ file.summary || '暂无简介' }}</div>
            <div class="desc-text">{{ file.description || (file.type === 'link' ? file.summary : '') || '暂无简介' }}</div>
            <!-- WeChat read full article button -->
            <button v-if="isWechat" class="read-btn" @click="loadArticle" :disabled="extracting">
              <span v-if="extracting" class="read-btn-orb"></span>
              <span>{{ extracting ? '正在提取正文…' : '📖 查看原文' }}</span>
            </button>
          </template>
        </div>

        <!-- Article markdown reader overlay -->
        <transition name="slide-up">
          <div v-if="showArticle" class="article-overlay">
            <div class="article-hdr">
              <button class="article-close" @click="showArticle = false">✕</button>
              <span class="article-hdr-ttl">原文</span>
              <span style="width:32px"></span>
            </div>
            <div class="article-meta" v-if="articleMeta">
              <div class="article-title">{{ articleMeta.title }}</div>
              <div class="article-byline">
                <span v-if="articleMeta.author">{{ articleMeta.author }}</span>
                <span v-if="articleMeta.pub_time">· {{ articleMeta.pub_time }}</span>
              </div>
            </div>
            <div class="article-body md-content" v-html="renderedMd"></div>
          </div>
        </transition>

        <!-- Highlights -->
        <div v-if="file.highlights?.length" class="info-card gc">
          <div class="card-label">亮点</div>
          <ul class="highlight-list">
            <li v-for="h in file.highlights" :key="h">{{ h }}</li>
          </ul>
        </div>

        <!-- Link -->
        <div v-if="file.url && !isWechat" class="info-card gc">
          <div class="card-label">原始链接</div>
          <a :href="file.url" target="_blank" class="link-url">{{ file.url }}</a>
        </div>

        <!-- Actions -->
        <div class="actions">
          <a v-if="file.type !== 'link'"
            :href="`/api/files/${file.id}/download`"
            class="btn-primary" download>
            ⬇ 下载文件
          </a>
          <a v-if="file.url" :href="file.url" target="_blank" class="btn-primary">
            🔗 打开链接
          </a>
          <button v-if="file.status !== 'ready'"
            class="btn-secondary" @click="triggerAnalyze" :disabled="analyzing">
            {{ analyzing ? '分析中...' : '🤖 AI 分析' }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'
import { getFile, analyzeFile, deleteFile, extractContent, imgUrl } from '../api/files'

const route = useRoute()
const router = useRouter()
const file = ref(null)
const loading = ref(true)
const analyzing = ref(false)
const articleMd = ref('')
const articleMeta = ref(null)
const extracting = ref(false)
const showArticle = ref(false)

marked.setOptions({ breaks: true, gfm: true })

const isWechat = computed(() => {
  const url = file.value?.url || ''
  return file.value?.type === 'link' && (url.includes('mp.weixin.qq.com') || url.includes('weixin.qq.com'))
})

const renderedMd = computed(() => articleMd.value ? marked.parse(articleMd.value) : '')

async function loadArticle() {
  if (articleMd.value) { showArticle.value = true; return }
  extracting.value = true
  try {
    const res = await extractContent(file.value.id)
    articleMeta.value = res
    articleMd.value = res.markdown
    showArticle.value = true
  } catch (e) {
    alert(e.response?.data?.detail || '提取失败，请稍后重试')
  } finally {
    extracting.value = false
  }
}

const ICONS  = { image:'🖼', video:'🎬', document:'📄', audio:'🎵', link:'🔗', text:'💬', other:'📦' }
const LABELS = { image:'图片', video:'视频', document:'文档', audio:'音频', link:'链接', text:'文字', other:'其他' }
const SLABELS = { pending:'分析中', ready:'已完成', failed:'分析失败' }

const typeIcon   = computed(() => ICONS[file.value?.type]   || '📦')
const typeLabel  = computed(() => LABELS[file.value?.type]  || '其他')
const statusLabel = computed(() => SLABELS[file.value?.status] || '')

const timeStr = computed(() => {
  if (!file.value?.created_at) return ''
  return new Date(file.value.created_at)
    .toLocaleString('zh-CN', { year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })
})

async function load() {
  loading.value = true
  try { file.value = await getFile(route.params.id) }
  finally { loading.value = false }
}

async function triggerAnalyze() {
  analyzing.value = true
  try { await analyzeFile(file.value.id); await load() }
  finally { analyzing.value = false }
}

async function confirmDelete() {
  if (!confirm(`删除「${file.value?.original_filename}」？`)) return
  await deleteFile(file.value.id)
  router.back()
}

onMounted(load)
</script>

<style scoped>
.page { position: relative; height: 100%; background: var(--bg); display: flex; flex-direction: column; overflow: hidden; }
.detail-bg {
  position: absolute; inset: 0; pointer-events: none;
  background: var(--bg);
}

.app-hdr {
  position: relative; z-index: 10; height: 90px;
  display: flex; align-items: flex-end; padding: 0 16px 14px; gap: 8px;
  background: var(--bg-blur); backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.app-back {
  width: 32px; height: 32px; border: none; background: none;
  color: var(--accent); font-size: 26px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.app-hdr-ttl { font-size: 17px; font-weight: 700; color: var(--text); flex: 1; }
.app-hdr-act {
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--s2); border: 1px solid var(--border);
  color: var(--text2); font-size: 16px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s;
}
.app-hdr-act:hover { background: rgba(255,110,122,.15); color: var(--red); }

.app-body {
  flex: 1; overflow-y: auto;
  padding: 14px 16px 48px;
  display: flex; flex-direction: column; gap: 10px;
  position: relative; z-index: 1;
}

.center-tip { text-align: center; color: var(--text3); font-size: 13px; padding: 40px; }

/* Hero card */
.hero {
  padding: 24px 18px; text-align: center;
  border-radius: var(--radius);
  background: var(--s2); border: 1px solid var(--border2);
}
.hero.hero-img { padding: 0 0 16px; overflow: hidden; }
.hero.hero-img .hero-name,
.hero.hero-img .hero-badges,
.hero.hero-img .hero-time { padding: 0 18px; }
.hero.hero-img .hero-name { margin-top: 12px; }
.hero-glow {
  position: absolute; top: -40px; right: -40px;
  width: 140px; height: 140px;
  background: radial-gradient(circle, var(--accent-g) 0%, transparent 70%);
  pointer-events: none;
}
.hero-icon { font-size: 52px; margin-bottom: 10px; }
.hero-img-wrap {
  width: 100%; max-height: 260px;
  overflow: hidden; border-radius: var(--radius) var(--radius) 0 0;
  background: var(--s3);
  display: flex; align-items: center; justify-content: center;
}
.hero-img-el {
  width: 100%; height: 100%; object-fit: cover; display: block;
  max-height: 260px;
}
.hero-name {
  font-size: 15px; font-weight: 700; color: var(--text);
  word-break: break-all; margin-bottom: 10px;
}
.hero-badges { display: flex; gap: 8px; justify-content: center; margin-bottom: 8px; }
.hero-time { font-size: 11px; color: var(--text3); }

.type-chip {
  font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 8px;
}
.type-chip.image    { background: rgba(139,114,255,.15); color: var(--accent); }
.type-chip.video    { background: rgba(255,110,122,.15); color: var(--red); }
.type-chip.document { background: rgba(94,234,181,.15);  color: var(--teal); }
.type-chip.audio    { background: rgba(255,170,92,.15);  color: var(--orange); }
.type-chip.link     { background: rgba(100,170,255,.15); color: #64AAFF; }
.type-chip.other    { background: var(--s3);             color: var(--text3); }

.status-chip { font-size: 11px; padding: 3px 9px; border-radius: 8px; }
.status-chip.pending { background: rgba(255,170,92,.15); color: var(--orange); }
.status-chip.ready   { background: rgba(94,234,181,.15); color: var(--teal); }
.status-chip.failed  { background: rgba(255,110,122,.15); color: var(--red); }

/* Info cards */
.info-card {
  padding: 14px 16px; border-radius: var(--radius);
  background: var(--s2); border: 1px solid var(--border);
}
.card-label {
  font-size: 10px; font-weight: 600; color: var(--text3);
  letter-spacing: .08em; text-transform: uppercase; margin-bottom: 9px;
}

.state-row {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: var(--text2);
}
.state-row.failed { color: var(--red); }
.mini-orb {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid rgba(139,114,255,.3);
  border-top-color: var(--accent);
  animation: spin .8s linear infinite; flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
.action-link {
  margin-left: auto; background: none; border: none;
  color: var(--accent); font-size: 12px; font-weight: 600;
  cursor: pointer; padding: 4px 10px;
  border: 1px solid rgba(139,114,255,.3); border-radius: 10px;
}
.action-link:disabled { opacity: .4; cursor: not-allowed; }

.summary-text { font-size: 15px; font-weight: 600; color: var(--text); line-height: 1.5; }
.desc-text { font-size: 13px; color: var(--text2); margin-top: 6px; line-height: 1.65; }

.kw-row { display: flex; flex-wrap: wrap; gap: 6px; }
.kw-tag {
  padding: 4px 11px; border-radius: 20px;
  background: var(--s1); border: 1px solid var(--border2);
  font-size: 12px; color: var(--text2);
}

.highlight-list { list-style: none; display: flex; flex-direction: column; gap: 7px; }
.highlight-list li {
  font-size: 13px; color: var(--text2); line-height: 1.6;
  padding-left: 16px; position: relative;
}
.highlight-list li::before {
  content: '✓'; position: absolute; left: 0;
  color: var(--teal); font-weight: 700;
}

.link-url {
  font-size: 13px; color: var(--accent); word-break: break-all; text-decoration: none;
}
.link-url:hover { text-decoration: underline; }

/* Actions */
.actions { display: flex; flex-direction: column; gap: 8px; padding-top: 4px; }
.btn-primary {
  display: flex; align-items: center; justify-content: center;
  height: 48px; border-radius: 14px; border: none;
  background: var(--accent); color: #fff;
  font-size: 15px; font-weight: 700; font-family: inherit;
  cursor: pointer; text-decoration: none;
  box-shadow: 0 4px 18px var(--accent-g);
  transition: transform .15s, box-shadow .15s;
}
.btn-primary:active { transform: scale(.97); }

.btn-secondary {
  height: 48px; border-radius: 14px;
  background: var(--accent-s); border: 1.5px solid rgba(139,114,255,.25);
  color: var(--accent); font-size: 15px; font-weight: 700;
  font-family: inherit; cursor: pointer;
  transition: transform .15s;
}
.btn-secondary:active { transform: scale(.97); }
.btn-secondary:disabled { opacity: .4; cursor: not-allowed; }

/* Read article button */
.read-btn {
  margin-top: 12px; width: 100%; height: 40px; border-radius: 12px;
  background: var(--accent-s); border: 1.5px solid rgba(139,114,255,.3);
  color: var(--accent); font-size: 14px; font-weight: 600;
  font-family: inherit; cursor: pointer; display: flex; align-items: center;
  justify-content: center; gap: 6px;
  transition: transform .15s, background .15s;
}
.read-btn:active { transform: scale(.97); }
.read-btn:disabled { opacity: .5; cursor: not-allowed; }
.read-btn-orb {
  width: 12px; height: 12px; border-radius: 50%;
  border: 2px solid rgba(139,114,255,.3);
  border-top-color: var(--accent);
  animation: spin .8s linear infinite; flex-shrink: 0;
}

/* Article overlay */
.article-overlay {
  position: absolute; inset: 0; z-index: 100;
  background: var(--bg); display: flex; flex-direction: column;
  overflow: hidden;
}
.article-hdr {
  flex-shrink: 0; height: 52px;
  display: flex; align-items: center; padding: 0 16px; gap: 8px;
  background: var(--bg-blur); backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
}
.article-close {
  width: 32px; height: 32px; border: none; background: none;
  color: var(--text2); font-size: 18px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.article-hdr-ttl { flex: 1; text-align: center; font-size: 15px; font-weight: 700; color: var(--text); }
.article-meta {
  flex-shrink: 0; padding: 16px 18px 12px;
  border-bottom: 1px solid var(--border);
}
.article-title { font-size: 18px; font-weight: 800; color: var(--text); line-height: 1.4; margin-bottom: 8px; }
.article-byline { font-size: 12px; color: var(--text3); display: flex; gap: 6px; }
.article-body { flex: 1; overflow-y: auto; padding: 16px 18px 40px; }

/* Markdown content styles */
.md-content { color: var(--text); font-size: 15px; line-height: 1.8; }
.md-content :deep(h1) { font-size: 20px; font-weight: 800; margin: 20px 0 10px; color: var(--text); }
.md-content :deep(h2) { font-size: 17px; font-weight: 700; margin: 18px 0 8px; color: var(--text); }
.md-content :deep(h3) { font-size: 15px; font-weight: 700; margin: 14px 0 6px; color: var(--text); }
.md-content :deep(p) { margin: 0 0 12px; color: var(--text2); }
.md-content :deep(strong) { color: var(--text); font-weight: 700; }
.md-content :deep(em) { color: var(--text2); }
.md-content :deep(a) { color: var(--accent); text-decoration: none; }
.md-content :deep(a:hover) { text-decoration: underline; }
.md-content :deep(img) { max-width: 100%; border-radius: 8px; margin: 10px 0; display: block; }
.md-content :deep(blockquote) {
  border-left: 3px solid var(--accent); padding: 6px 12px;
  margin: 12px 0; background: var(--s2); border-radius: 0 8px 8px 0;
  color: var(--text2); font-size: 14px;
}
.md-content :deep(ul), .md-content :deep(ol) { padding-left: 20px; margin: 8px 0; }
.md-content :deep(li) { margin: 4px 0; color: var(--text2); }
.md-content :deep(code) {
  background: var(--s3); border-radius: 4px; padding: 1px 5px;
  font-family: monospace; font-size: 13px; color: var(--teal);
}
.md-content :deep(pre) {
  background: var(--s3); border-radius: 8px; padding: 12px;
  overflow-x: auto; margin: 12px 0;
}
.md-content :deep(pre code) { background: none; padding: 0; color: var(--text2); }
.md-content :deep(hr) { border: none; border-top: 1px solid var(--border); margin: 20px 0; }

/* Slide up transition */
.slide-up-enter-active, .slide-up-leave-active { transition: transform .35s cubic-bezier(.32,.72,0,1); }
.slide-up-enter-from, .slide-up-leave-to { transform: translateY(100%); }
</style>
