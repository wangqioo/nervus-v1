<template>
  <div class="home" @paste.prevent="handlePaste"
    @touchstart.passive="onTouchStart"
    @touchend.passive="onTouchEnd"
    @mousedown="onMouseDown"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @mouseleave="onMouseUp">

    <div class="fm-bg"></div>

    <!-- Header -->
    <header class="fm-hdr">
      <div class="fm-av">🗂</div>
      <div>
        <div class="fm-ttl">文件传输助手</div>
        <div class="fm-sub">发送给自己的文件 · 链接 · 文字</div>
      </div>
      <button class="icon-btn" @click="showSettings = true">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>
    </header>

    <!-- Search bar -->
    <div class="fm-search-bar">
      <div class="fm-search-inner" @click="$router.push('/search')">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
          <circle cx="7" cy="7" r="5.5" stroke="var(--text3)" stroke-width="1.5"/>
          <path d="M11 11L14 14" stroke="var(--text3)" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <input readonly placeholder="搜索文件、链接或文字…" />
      </div>
    </div>

    <!-- Chat-style feed -->
    <main class="fm-feed" ref="feedEl">
      <!-- Loading -->
      <div v-if="loading && !files.length" class="feed-center">
        <div class="orb-mini"></div>
        <span>加载中…</span>
      </div>

      <!-- Empty -->
      <div v-else-if="!files.length" class="feed-center">
        <div style="font-size:44px;opacity:.25">🗂</div>
        <span>还没有文件，从底部发送吧</span>
      </div>

      <!-- Date-grouped chat feed -->
      <template v-else>
        <template v-for="group in dateGroups" :key="group.date">
          <!-- Date separator — tap to AI search -->
          <button class="fm-date-sep" @click="$router.push({ path:'/search', query:{ date: group.date } })">
            {{ group.label }}
            <span class="date-sep-hint">· AI 搜索</span>
          </button>

          <!-- Each file as a chat bubble row -->
          <div
            v-for="f in group.files"
            :key="f.id"
            class="fm-row"
            @touchstart.passive="onCardTS($event, f.id)"
            @touchmove.passive="onCardTM($event, f.id)"
            @touchend.passive="onCardTE(f.id)"
          >
            <div class="fm-row-inner">
              <!-- Image card -->
              <template v-if="f.type === 'image'">
                <div
                  class="fm-img-card"
                  :style="{ transform: `translateX(${swipe[f.id] || 0}px)` }"
                  @click="handleCardClick(f)"
                >
                  <div class="fm-img-inner" :class="imgBgClass(f)">
                    <img :src="`/api/files/${f.id}/download`" class="img-thumb" loading="lazy" @error="e => e.target.style.display='none'" />
                  </div>
                  <div class="fm-img-lbl">
                    <span class="img-lbl-name">{{ f.original_filename }}</span>
                    <span v-if="f.status === 'pending'" class="status-dot pending"></span>
                    <span v-else-if="f.status === 'ready'" class="status-dot ready"></span>
                    <span v-else-if="f.status === 'failed'" class="status-dot failed"></span>
                  </div>
                  <div v-if="f.summary" class="fm-summary-text">{{ f.summary }}</div>
                </div>
              </template>

              <!-- Link card -->
              <template v-else-if="f.type === 'link'">
                <div
                  class="fm-link-card"
                  :style="{ transform: `translateX(${swipe[f.id] || 0}px)` }"
                  @click="handleCardClick(f)"
                >
                  <div class="fm-link-preview" :class="linkBgClass(f)">
                    <img v-if="f.og_image" :src="imgUrl(f.og_image)" class="link-og-img" loading="lazy" @error="e => e.target.style.display='none'" />
                    <template v-else>
                      <img v-if="f.favicon_url" :src="f.favicon_url" class="link-fav-big" loading="lazy" @error="e => e.target.style.display='none'" />
                      <span v-else style="font-size:26px">🔗</span>
                    </template>
                  </div>
                  <div class="fm-link-info">
                    <div class="fm-link-title">{{ f.original_filename }}</div>
                    <div class="fm-link-url">
                      <img v-if="f.favicon_url" :src="f.favicon_url" class="link-fav-sm" @error="e => e.target.style.display='none'" />
                      {{ linkHost(f.original_filename) }}
                    </div>
                    <div v-if="f.summary" class="fm-link-summary">{{ f.summary }}</div>
                  </div>
                </div>
              </template>

              <!-- Text bubble -->
              <template v-else-if="f.type === 'text'">
                <div
                  class="fm-text-bubble"
                  :style="{ transform: `translateX(${swipe[f.id] || 0}px)` }"
                  @click="$router.push(`/file/${f.id}`)"
                >
                  {{ f.summary }}
                </div>
              </template>

              <!-- File card (doc / video / audio / other) -->
              <template v-else>
                <div
                  class="fm-file-card"
                  :style="{ transform: `translateX(${swipe[f.id] || 0}px)` }"
                  @click="handleCardClick(f)"
                >
                  <div class="fm-file-ico" :style="{ background: fileIconBg(f.type) }">
                    {{ fileIcon(f.type) }}
                  </div>
                  <div class="fm-file-body">
                    <div class="fm-file-name">{{ f.original_filename }}</div>
                    <div class="fm-file-meta">
                      <span>{{ fileLabel(f.type) }}</span>
                      <span v-if="f.file_size"> · {{ fmtSize(f.file_size) }}</span>
                      <span class="status-dot" :class="f.status" style="margin-left:4px"></span>
                    </div>
                    <div v-if="f.summary" class="fm-summary-text">{{ f.summary }}</div>
                  </div>
                  <button class="fm-file-open" @click.stop="$router.push(`/file/${f.id}`)">↗</button>
                </div>
              </template>

              <!-- Delete swipe action -->
              <button
                class="delete-action"
                :class="{ visible: (swipe[f.id] || 0) < -20 }"
                @click.stop="confirmDelete(f)"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/>
                </svg>
              </button>
            </div>
            <div class="fm-time">{{ timeStr(f.created_at) }}</div>
          </div>
        </template>
      </template>
    </main>

    <!-- Bottom input bar -->
    <div class="fm-inp">
      <button class="inp-icon" @click="triggerUpload()" title="上传文件">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
      </button>
      <input
        v-model="textInput"
        class="fm-inp-field"
        placeholder="粘贴链接或发送文字给自己…"
        @keydown.enter="submitText"
      />
      <button
        v-if="speechSupported"
        class="voice-btn"
        :class="{ recording: isRecording }"
        @click="toggleVoice"
      >
        <span v-if="!isRecording">🎤</span>
        <span v-else class="rec-wave"><i v-for="n in 5" :key="n"></i></span>
      </button>
      <button class="send-btn" @click="submitText">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>
        </svg>
      </button>
    </div>

    <!-- Hidden file input -->
    <input type="file" multiple ref="fileInputRef" style="display:none" @change="handleFileSelect" />

    <!-- Upload toast -->
    <transition name="toast-fade">
      <div v-if="uploadToast" class="upload-toast">
        <div class="toast-spinner" v-if="uploading"></div>
        <span>{{ uploadToast }}</span>
      </div>
    </transition>

    <!-- Delete confirm -->
    <transition name="sheet">
      <div v-if="deleteTarget" class="modal-mask" @click.self="deleteTarget = null">
        <div class="bottom-sheet">
          <div class="sheet-handle"></div>
          <div class="sheet-title">删除文件</div>
          <div class="sheet-body">确认删除「{{ deleteTarget.original_filename }}」？</div>
          <div class="sheet-actions">
            <button class="sheet-btn cancel" @click="deleteTarget = null">取消</button>
            <button class="sheet-btn danger" @click="doDelete">删除</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Settings -->
    <transition name="sheet">
      <div v-if="showSettings" class="modal-mask" @click.self="showSettings = false">
        <div class="bottom-sheet">
          <div class="sheet-handle"></div>
          <div class="sheet-title">设置</div>
          <div class="settings-list">
            <div class="setting-row">
              <div class="setting-label">
                <span>外观模式</span>
                <span class="setting-sub">{{ theme === 'dark' ? '深色' : '浅色' }}</span>
              </div>
              <button class="theme-btn" @click="toggleTheme">
                {{ theme === 'dark' ? '🌙 切换浅色' : '☀️ 切换深色' }}
              </button>
            </div>
            <div class="setting-row">
              <div class="setting-label">
                <span>上传后立即 AI 分析</span>
                <span class="setting-sub">关闭则后台队列处理</span>
              </div>
              <div class="toggle" :class="{ on: analyzeNow }" @click="analyzeNow = !analyzeNow">
                <div class="toggle-thumb"></div>
              </div>
            </div>
            <div class="setting-row" v-if="stats">
              <span class="setting-label">文件总数</span>
              <span class="setting-val">{{ stats.total }} 个</span>
            </div>
          </div>
        </div>
      </div>
    </transition>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { getFiles, uploadFile, uploadLink, uploadText, deleteFile, getStats, imgUrl } from '../api/files'
import { useTheme } from '../composables/useTheme'

const { theme, toggle: toggleTheme } = useTheme()
const router = useRouter()

const files = ref([])
const loading = ref(false)
const uploading = ref(false)
const textInput = ref('')
const fileInputRef = ref(null)
const analyzeNow = ref(false)
const showSettings = ref(false)
const deleteTarget = ref(null)
const stats = ref(null)
const feedEl = ref(null)
const uploadToast = ref('')

// Per-card swipe state
const swipe = reactive({})
const swipeMeta = reactive({})

// ── Type helpers ──────────────────────────────────────────────
const FILE_ICONS  = { image:'🖼', video:'🎬', document:'📄', audio:'🎵', link:'🔗', other:'📦' }
const FILE_LABELS = { image:'图片', video:'视频', document:'文档', audio:'音频', link:'链接', other:'其他' }
const FILE_BG = {
  image:    'rgba(139,114,255,.15)',
  video:    'rgba(255,110,122,.15)',
  document: 'rgba(94,234,181,.15)',
  audio:    'rgba(255,170,92,.15)',
  link:     'rgba(100,170,255,.15)',
  other:    'rgba(255,255,255,.08)',
}
function fileIcon(t)  { return FILE_ICONS[t]  || '📦' }
function fileLabel(t) { return FILE_LABELS[t] || '其他' }
function fileIconBg(t){ return FILE_BG[t]     || FILE_BG.other }

const IMG_BG_CLASSES = ['img-bg-a', 'img-bg-b', 'img-bg-c']
function imgBgClass(f) { return IMG_BG_CLASSES[f.id.charCodeAt(0) % 3] }

const LINK_BG_CLASSES = ['link-bg-a', 'link-bg-b', 'link-bg-c']
function linkBgClass(f) { return LINK_BG_CLASSES[f.id.charCodeAt(0) % 3] }

function linkHost(url) {
  try { return new URL(url).hostname.replace('www.', '') } catch { return url }
}
function fmtSize(b) {
  if (!b) return ''
  if (b > 1024*1024) return `${(b/1024/1024).toFixed(1)} MB`
  return `${(b/1024).toFixed(0)} KB`
}
function timeStr(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
}

// ── Date groups ───────────────────────────────────────────────
const dateGroups = computed(() => {
  const map = {}
  for (const f of files.value) {
    const d = f.created_at ? f.created_at.slice(0, 10) : 'unknown'
    if (!map[d]) map[d] = []
    map[d].push(f)
  }
  const today = new Date().toISOString().slice(0, 10)
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10)

  return Object.keys(map).sort((a, b) => a.localeCompare(b)).map(date => ({
    date,
    label: date === today ? '今天' : date === yesterday ? '昨天' : date,
    files: map[date].sort((a, b) => a.created_at.localeCompare(b.created_at)),
  }))
})


// ── Swipe — touch (mobile) ────────────────────────────────────
let txStart = 0, tyStart = 0
function onTouchStart(e) { txStart = e.touches[0].clientX; tyStart = e.touches[0].clientY }
function onTouchEnd(e) {
  const dx = e.changedTouches[0].clientX - txStart
  const dy = e.changedTouches[0].clientY - tyStart
  if (Math.abs(dx) > Math.abs(dy) + 10 && dx < -60) router.push('/category')
}

// ── Swipe — mouse (desktop preview) ──────────────────────────
let mouseDown = false, mxStart = 0, myStart = 0, mouseMoved = false
function onMouseDown(e) {
  // only left button, ignore clicks on interactive elements
  if (e.button !== 0) return
  mouseDown = true; mouseMoved = false
  mxStart = e.clientX; myStart = e.clientY
}
function onMouseMove(e) {
  if (!mouseDown) return
  if (Math.abs(e.clientX - mxStart) > 5) mouseMoved = true
}
function onMouseUp(e) {
  if (!mouseDown) return
  mouseDown = false
  if (!mouseMoved) return
  const dx = e.clientX - mxStart
  const dy = e.clientY - myStart
  if (Math.abs(dx) > Math.abs(dy) + 10 && dx < -60) router.push('/category')
}

// ── Swipe — per-card (reveal delete) ─────────────────────────
function onCardTS(e, id) {
  swipeMeta[id] = { sx: e.touches[0].clientX, sy: e.touches[0].clientY, moving: false }
}
function onCardTM(e, id) {
  const m = swipeMeta[id]; if (!m) return
  const dx = e.touches[0].clientX - m.sx
  const dy = e.touches[0].clientY - m.sy
  if (!m.moving && Math.abs(dx) > Math.abs(dy) + 5) m.moving = true
  if (!m.moving) return
  swipe[id] = Math.max(-72, Math.min(0, dx))
}
function onCardTE(id) {
  swipe[id] = (swipe[id] || 0) < -36 ? -64 : 0
  if (swipeMeta[id]) swipeMeta[id].moving = false
}
function handleCardClick(f) {
  if ((swipe[f.id] || 0) < -10) { swipe[f.id] = 0; return }
  router.push(`/file/${f.id}`)
}

// ── Voice ─────────────────────────────────────────────────────
const isRecording = ref(false)
const speechSupported = ref(false)
let recognition = null

// ── SSE ───────────────────────────────────────────────────────
let evtSource = null
function startSSE() {
  if (evtSource) return
  evtSource = new EventSource('/api/files/events')
  evtSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (data.type === 'file_updated') {
        const idx = files.value.findIndex(f => f.id === data.id)
        if (idx !== -1) {
          files.value[idx] = {
            ...files.value[idx],
            status: data.status,
            summary: data.summary || files.value[idx].summary,
            og_image: data.og_image ?? files.value[idx].og_image,
            favicon_url: data.favicon_url ?? files.value[idx].favicon_url,
          }
        }
      }
    } catch {}
  }
  evtSource.onerror = () => { evtSource?.close(); evtSource = null; setTimeout(startSSE, 5000) }
}

onMounted(() => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (SR) {
    speechSupported.value = true
    recognition = new SR()
    recognition.lang = 'zh-CN'
    recognition.continuous = false
    recognition.interimResults = false
    recognition.onresult = e => { textInput.value = e.results[0][0].transcript; isRecording.value = false }
    recognition.onerror = () => { isRecording.value = false }
    recognition.onend = () => { isRecording.value = false }
  }
  loadFiles()
})
onUnmounted(() => { recognition?.abort(); evtSource?.close(); evtSource = null })

function toggleVoice() {
  if (!recognition) return
  if (isRecording.value) { recognition.stop(); isRecording.value = false }
  else { recognition.start(); isRecording.value = true }
}

async function loadFiles() {
  loading.value = true
  try {
    ;[files.value, stats.value] = await Promise.all([getFiles({ limit: 200 }), getStats()])
    startSSE()
    await nextTick()
    feedEl.value?.scrollTo({ top: feedEl.value.scrollHeight })
  } finally { loading.value = false }
}

function triggerUpload() {
  fileInputRef.value?.click()
}

async function handleFileSelect(e) {
  const list = [...e.target.files]; e.target.value = ''
  for (const f of list) await doUpload(f, null)
}

async function handlePaste(e) {
  const items = [...(e.clipboardData?.items || [])]
  for (const item of items) {
    if (item.kind === 'file') {
      const f = item.getAsFile(); if (f) await doUpload(f, null)
    } else if (item.kind === 'string' && item.type === 'text/plain') {
      item.getAsString(async text => {
        const t = text.trim()
        if (t.startsWith('http://') || t.startsWith('https://')) await doUpload(null, t)
      })
    }
  }
}

async function submitText() {
  const val = textInput.value.trim(); if (!val) return
  textInput.value = ''
  if (val.startsWith('http://') || val.startsWith('https://')) {
    await doUpload(null, val)
  } else {
    uploading.value = true
    uploadToast.value = '发送中…'
    try {
      await uploadText(val)
      await loadFiles()
      uploadToast.value = '✓ 发送成功'
      setTimeout(() => { feedEl.value?.scrollTo({ top: feedEl.value.scrollHeight, behavior: 'smooth' }) }, 100)
    } catch (e) {
      uploadToast.value = `✗ ${e.response?.data?.detail || e.message}`
    }
    uploading.value = false
    setTimeout(() => { uploadToast.value = '' }, 2200)
  }
}

async function doUpload(file, url) {
  uploading.value = true
  uploadToast.value = `上传中 ${file?.name || url || ''}…`
  try {
    if (file) await uploadFile(file, analyzeNow.value)
    else await uploadLink(url, analyzeNow.value)
    await loadFiles()
    uploadToast.value = '✓ 发送成功'
    // Scroll to bottom after upload
    setTimeout(() => { feedEl.value?.scrollTo({ top: feedEl.value.scrollHeight, behavior: 'smooth' }) }, 100)
  } catch (e) {
    uploadToast.value = `✗ ${e.response?.data?.detail || e.message}`
  }
  uploading.value = false
  setTimeout(() => { uploadToast.value = '' }, 2200)
}

function confirmDelete(f) { deleteTarget.value = f }
async function doDelete() {
  try {
    await deleteFile(deleteTarget.value.id)
    files.value = files.value.filter(f => f.id !== deleteTarget.value.id)
  } catch {}
  deleteTarget.value = null
}
</script>

<style scoped>
.home {
  position: relative;
  display: flex; flex-direction: column;
  height: 100%; background: var(--bg);
  overflow: hidden;
}

/* ── Backgrounds ── */
.fm-bg {
  position: absolute; inset: 0; pointer-events: none;
  background:
    radial-gradient(ellipse 260px 200px at 20% 8%, rgba(255,170,92,.07) 0%, transparent 65%),
    radial-gradient(ellipse 300px 220px at 85% 85%, rgba(139,114,255,.06) 0%, transparent 65%),
    var(--bg);
}

/* ── Header ── */
.fm-hdr {
  position: relative; z-index: 10;
  height: var(--header-h);
  background: var(--bg-blur); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: flex-end;
  padding: 0 20px 14px; gap: 12px; flex-shrink: 0;
}
.fm-av {
  width: 38px; height: 38px; border-radius: 12px; flex-shrink: 0;
  background: linear-gradient(135deg, rgba(255,170,92,.6), rgba(255,110,70,.5));
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; box-shadow: 0 0 12px rgba(255,150,70,.3);
}
.fm-ttl { font-size: 16px; font-weight: 700; color: var(--text); }
.fm-sub { font-size: 11px; color: var(--text3); margin-top: 1px; }
.icon-btn {
  width: 34px; height: 34px; border-radius: 50%;
  background: var(--s2); border: 1px solid var(--border);
  color: var(--text2); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s, transform .15s;
  margin-left: auto;
}
.icon-btn:active { background: var(--s3); transform: scale(.92); }

/* ── Search ── */
.fm-search-bar {
  position: relative; z-index: 9;
  padding: 10px 16px;
  background: var(--bg-blur); backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.fm-search-inner {
  display: flex; align-items: center; gap: 8px;
  background: var(--s2); border: 1px solid var(--border);
  border-radius: 10px; padding: 7px 12px; cursor: pointer;
  transition: background .15s;
}
.fm-search-inner:active { background: var(--s3); }
.fm-search-inner input {
  flex: 1; background: none; border: none;
  color: var(--text); font-size: 13px; font-family: inherit;
  outline: none; cursor: pointer;
}
.fm-search-inner input::placeholder { color: var(--text3); }

/* ── Feed ── */
.fm-feed {
  flex: 1; overflow-y: auto; overflow-x: hidden;
  padding: 12px 22px 12px 14px;
  display: flex; flex-direction: column; gap: 10px;
  position: relative; z-index: 1;
}
.feed-center {
  display: flex; flex-direction: column; align-items: center;
  gap: 10px; padding: 60px 0; color: var(--text3); font-size: 13px;
  margin: auto;
}
.orb-mini {
  width: 36px; height: 36px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--teal));
  animation: spin .9s linear infinite; opacity: .5;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Date separator ── */
.fm-date-sep {
  text-align: center; font-size: 11px; color: var(--text3);
  font-weight: 500; letter-spacing: .3px;
  background: none; border: none; font-family: inherit;
  cursor: pointer; padding: 2px 8px; border-radius: 8px;
  align-self: center;
  transition: background .2s, color .2s;
}
.fm-date-sep:active { background: var(--s2); }
.date-sep-hint {
  color: var(--accent); font-size: 10px; opacity: .7;
}

/* ── Row (right-aligned like WeChat sent messages) ── */
.fm-row {
  display: flex; flex-direction: column; align-items: flex-end; gap: 2px;
}
.fm-row-inner {
  position: relative; display: flex; align-items: stretch;
  overflow: hidden; border-radius: 16px;
}
.fm-time {
  font-size: 10px; color: var(--text3); padding: 0 2px;
  text-align: right;
}

/* ── Delete action ── */
.delete-action {
  position: absolute; right: 0; top: 0; bottom: 0; width: 64px;
  background: rgba(255,60,60,.85); border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: #fff; border-radius: 0 16px 16px 0;
  opacity: 0; transition: opacity .18s; z-index: 0;
}
.delete-action.visible { opacity: 1; }

/* ── Image card ── */
.fm-img-card {
  max-width: 185px; border-radius: 14px; overflow: hidden;
  border: 1px solid var(--border);
  background: var(--s2); cursor: pointer;
  position: relative; z-index: 1;
  transition: transform .3s cubic-bezier(.32,.72,0,1);
}
.fm-img-card:active { transform: scale(.97); }
.fm-img-inner {
  width: 185px; height: 120px;
  display: flex; align-items: center; justify-content: center;
  position: relative; overflow: hidden;
}
.img-thumb {
  width: 100%; height: 100%; object-fit: cover; display: block;
}
.img-bg-a { background: linear-gradient(135deg, rgba(139,114,255,.25), rgba(94,234,181,.15)); }
.img-bg-b { background: linear-gradient(135deg, rgba(255,170,92,.2), rgba(255,110,122,.15)); }
.img-bg-c { background: linear-gradient(135deg, rgba(100,170,255,.2), rgba(94,234,181,.12)); }
.fm-img-lbl {
  font-size: 11px; color: var(--text3); padding: 5px 10px 7px;
  background: var(--s2); display: flex; align-items: center; gap: 5px;
}
.img-lbl-name {
  flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ── Link card ── */
.fm-text-bubble {
  max-width: 248px; background: var(--accent);
  color: #fff; border-radius: 14px 14px 4px 14px;
  padding: 10px 14px; font-size: 14px; line-height: 1.55;
  white-space: pre-wrap; word-break: break-all;
  cursor: pointer; position: relative; z-index: 1;
  transition: transform .3s cubic-bezier(.32,.72,0,1);
}
.fm-text-bubble:active { transform: scale(.97); }
.fm-link-card {
  max-width: 248px; background: var(--s2);
  border: 1px solid var(--border); border-radius: 14px; overflow: hidden;
  cursor: pointer; position: relative; z-index: 1;
  transition: transform .3s cubic-bezier(.32,.72,0,1);
}
.fm-link-card:active { transform: scale(.97); }
.fm-link-preview {
  height: 72px; display: flex; align-items: center; justify-content: center;
  overflow: hidden; position: relative;
}
.link-og-img {
  width: 100%; height: 100%; object-fit: cover; display: block;
}
.link-fav-big { width: 32px; height: 32px; border-radius: 8px; object-fit: contain; }
.link-bg-a { background: linear-gradient(135deg, rgba(80,180,255,.18), rgba(40,120,200,.08)); }
.link-bg-b { background: linear-gradient(135deg, rgba(94,234,181,.15), rgba(40,160,120,.08)); }
.link-bg-c { background: linear-gradient(135deg, rgba(139,114,255,.18), rgba(80,60,180,.08)); }
.fm-link-info { padding: 8px 12px 10px; }
.fm-link-title {
  font-size: 13px; color: var(--text); font-weight: 500; margin-bottom: 3px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.fm-link-url {
  font-size: 11px; color: var(--accent);
  display: flex; align-items: center; gap: 4px;
}
.link-fav-sm { width: 12px; height: 12px; border-radius: 2px; object-fit: contain; }
.fm-link-summary {
  font-size: 11px; color: var(--text3); margin-top: 4px; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}

/* ── File card ── */
.fm-file-card {
  max-width: 255px; background: var(--s2);
  border: 1px solid var(--border); border-radius: 16px;
  padding: 12px 14px; display: flex; gap: 10px; align-items: center;
  cursor: pointer; position: relative; z-index: 1;
  transition: transform .3s cubic-bezier(.32,.72,0,1), background .15s;
}
.fm-file-card:active { transform: scale(.97); background: var(--s3); }
.fm-file-ico {
  width: 40px; height: 40px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 21px; flex-shrink: 0;
}
.fm-file-body { flex: 1; min-width: 0; }
.fm-file-name {
  font-size: 13px; color: var(--text); font-weight: 500; margin-bottom: 3px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.fm-file-meta {
  font-size: 11px; color: var(--text3);
  display: flex; align-items: center; gap: 3px;
}
.fm-file-open {
  width: 28px; height: 28px; border-radius: 8px;
  background: var(--s1); border: 1px solid var(--border);
  color: var(--text3); font-size: 13px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  transition: background .15s;
}
.fm-file-open:hover { background: var(--s3); }

/* AI summary line under any card */
.fm-summary-text {
  font-size: 11px; color: var(--text3); padding: 0 10px 8px;
  line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.fm-file-body .fm-summary-text { padding: 4px 0 0; }

/* Status dot */
.status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; display: inline-block; }
.status-dot.pending { background: var(--orange); animation: pulse 1.4s infinite; }
.status-dot.ready   { background: var(--teal); }
.status-dot.failed  { background: var(--red); }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

/* ── Bottom input ── */
.fm-inp {
  position: relative; z-index: 10;
  bottom: 16px; margin: 0 16px 16px;
  height: 50px;
  background: var(--s2); border: 1px solid var(--border2);
  border-radius: 25px;
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  display: flex; align-items: center;
  padding: 0 8px 0 10px; gap: 4px;
  box-shadow: 0 4px 20px rgba(0,0,0,.18), 0 0 0 1px rgba(139,114,255,.08);
  flex-shrink: 0;
}
.inp-icon {
  width: 34px; height: 34px; border-radius: 50%; border: none;
  background: none; font-size: 16px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; transition: background .15s, transform .15s;
}
.inp-icon:active { background: var(--s3); transform: scale(.88); }
.fm-inp-field {
  flex: 1; height: 34px; background: none; border: none;
  padding: 0 4px; color: var(--text); font-size: 13px;
  font-family: inherit; outline: none; min-width: 0;
}
.fm-inp-field::placeholder { color: var(--text3); }
.voice-btn {
  width: 34px; height: 34px; border-radius: 50%; border: none;
  background: var(--s2); border: 1px solid var(--border);
  color: var(--text2); font-size: 15px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0;
  transition: transform .15s, background .15s;
}
.voice-btn:active { transform: scale(.88); }
.voice-btn.recording {
  background: linear-gradient(135deg, var(--red), #FF4E7E);
  border-color: transparent; color: #fff;
  animation: vpulse 1.5s ease-in-out infinite;
}
@keyframes vpulse { 0%,100%{box-shadow:0 0 8px rgba(255,110,122,.3)} 50%{box-shadow:0 0 18px rgba(255,110,122,.6)} }
.rec-wave { display: flex; align-items: center; gap: 2px; height: 14px; }
.rec-wave i { width: 2px; border-radius: 1px; background: #fff; animation: wv .8s ease-in-out infinite; }
.rec-wave i:nth-child(1){height:4px} .rec-wave i:nth-child(2){height:10px;animation-delay:.1s}
.rec-wave i:nth-child(3){height:13px;animation-delay:.2s} .rec-wave i:nth-child(4){height:8px;animation-delay:.3s}
.rec-wave i:nth-child(5){height:4px;animation-delay:.4s}
@keyframes wv { 0%,100%{transform:scaleY(1)} 50%{transform:scaleY(.3)} }
.send-btn {
  width: 34px; height: 34px; border-radius: 50%; border: none;
  background: var(--accent); color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0;
  box-shadow: 0 0 12px var(--accent-g);
  transition: transform .15s, box-shadow .15s;
}
.send-btn:active { transform: scale(.88); box-shadow: none; }

/* ── Toast ── */
.upload-toast {
  position: absolute; bottom: 82px; left: 50%; transform: translateX(-50%);
  background: var(--bg-blur); border: 1px solid var(--border2);
  border-radius: 20px; padding: 8px 16px;
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--text2);
  backdrop-filter: blur(16px); white-space: nowrap; z-index: 500;
  box-shadow: 0 6px 24px rgba(0,0,0,.4); pointer-events: none;
}
.toast-spinner {
  width: 13px; height: 13px;
  border: 2px solid rgba(139,114,255,.3); border-top-color: var(--accent);
  border-radius: 50%; animation: spin .8s linear infinite;
}
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity .3s, transform .3s; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(8px); }

/* ── Modal / sheet ── */
.modal-mask {
  position: absolute; inset: 0; z-index: 300;
  background: rgba(0,0,0,.6); backdrop-filter: blur(4px);
  display: flex; align-items: flex-end; justify-content: center;
}
.bottom-sheet {
  width: 100%; background: var(--card);
  border: 1px solid var(--border2); border-radius: 26px 26px 0 0;
  padding: 14px 20px 36px;
}
.sheet-handle { width: 38px; height: 4px; border-radius: 2px; background: var(--border2); margin: 0 auto 18px; }
.sheet-title { font-size: 16px; font-weight: 700; color: var(--text); margin-bottom: 8px; }
.sheet-body { font-size: 13px; color: var(--text2); margin-bottom: 22px; line-height: 1.6; }
.sheet-actions { display: flex; gap: 10px; }
.sheet-btn {
  flex: 1; height: 46px; border-radius: 14px; border: none;
  font-size: 14px; font-weight: 700; font-family: inherit; cursor: pointer;
  transition: transform .15s;
}
.sheet-btn:active { transform: scale(.97); }
.sheet-btn.cancel { background: var(--s2); border: 1px solid var(--border2); color: var(--text); }
.sheet-btn.danger { background: rgba(255,110,122,.15); border: 1.5px solid rgba(255,110,122,.3); color: var(--red); }

/* ── Settings ── */
.settings-list { display: flex; flex-direction: column; }
.setting-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 0; border-bottom: 1px solid var(--border);
}
.setting-row:last-child { border-bottom: none; }
.setting-label { font-size: 14px; color: var(--text); display: flex; flex-direction: column; gap: 2px; }
.setting-sub { font-size: 11px; color: var(--text3); }
.setting-val { font-size: 14px; color: var(--text2); }
.toggle { width: 44px; height: 26px; border-radius: 13px; background: var(--s3); position: relative; cursor: pointer; transition: background .2s; }
.toggle.on { background: var(--teal); }
.toggle-thumb { position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; background: #fff; border-radius: 50%; transition: left .2s; box-shadow: 0 1px 4px rgba(0,0,0,.3); }
.toggle.on .toggle-thumb { left: 21px; }
.theme-btn {
  padding: 7px 14px; border-radius: 20px;
  background: var(--accent-s); border: 1px solid rgba(139,114,255,.25);
  color: var(--accent); font-size: 13px; font-weight: 600; font-family: inherit;
  cursor: pointer; transition: transform .15s;
}
.theme-btn:active { transform: scale(.95); }

/* ── Sheet transitions ── */
.sheet-enter-active, .sheet-leave-active { transition: opacity .3s; }
.sheet-enter-active .bottom-sheet, .sheet-leave-active .bottom-sheet { transition: transform .36s cubic-bezier(.32,.72,0,1); }
.sheet-enter-from, .sheet-leave-to { opacity: 0; }
.sheet-enter-from .bottom-sheet, .sheet-leave-to .bottom-sheet { transform: translateY(100%); }

</style>
