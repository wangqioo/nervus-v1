<template>
  <div class="page">
    <div class="page-bg"></div>
    <header class="app-hdr">
      <button class="app-back" @click="$router.back()">‹</button>
      <div class="hdr-body">
        <span class="app-hdr-ttl">{{ dateLabel }}</span>
        <span v-if="typeLabel" class="hdr-badge">{{ typeLabel }}</span>
      </div>
      <span style="width:32px"></span>
    </header>

    <main class="day-feed">
      <div v-if="loading" class="feed-center">
        <div class="orb-mini"></div>
        <span>加载中…</span>
      </div>
      <div v-else-if="!dayFiles.length" class="feed-center">
        <div style="font-size:40px;opacity:.2">🗂</div>
        <span>这天没有{{ typeLabel }}文件</span>
      </div>
      <template v-else>
        <div class="file-count-tip">共 {{ dayFiles.length }} 个文件</div>
        <div
          v-for="f in dayFiles" :key="f.id"
          class="day-card gc"
          @click="$router.push(`/file/${f.id}`)"
        >
          <!-- Image -->
          <template v-if="f.type === 'image'">
            <div class="dc-img-wrap">
              <img :src="`/api/files/${f.id}/download`" class="dc-img" loading="lazy" @error="e => e.target.style.display='none'" />
            </div>
          </template>
          <!-- Link -->
          <template v-else-if="f.type === 'link'">
            <div class="dc-link-cover">
              <img v-if="f.og_image" :src="imgUrl(f.og_image)" class="dc-img" loading="lazy" @error="e => e.target.style.display='none'" />
              <template v-else>
                <img v-if="f.favicon_url" :src="f.favicon_url" class="dc-fav" loading="lazy" @error="e => e.target.style.display='none'" />
                <span v-else class="dc-icon">🔗</span>
              </template>
            </div>
          </template>
          <!-- Other file types -->
          <template v-else>
            <div class="dc-file-ico" :style="{ background: iconBg(f.type) }">{{ fileIcon(f.type) }}</div>
          </template>

          <div class="dc-body">
            <div class="dc-name">{{ f.original_filename }}</div>
            <div class="dc-meta">
              <span>{{ fileLabel(f.type) }}</span>
              <span v-if="f.file_size"> · {{ fmtSize(f.file_size) }}</span>
              <span class="dc-time"> · {{ timeStr(f.created_at) }}</span>
            </div>
            <div v-if="f.summary" class="dc-summary">{{ f.summary }}</div>
          </div>

          <div class="dc-status">
            <span class="status-dot" :class="f.status"></span>
          </div>
        </div>
      </template>
    </main>

    <!-- Bottom AI search bar -->
    <div class="day-search-bar">
      <div class="day-search-inner">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" style="flex-shrink:0;color:var(--text3)">
          <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
        </svg>
        <input
          v-model="searchQ"
          class="day-search-input"
          :placeholder="searchPlaceholder"
          @keydown.enter="submitSearch"
        />
        <button class="day-search-send" @click="submitSearch" :disabled="!searchQ.trim()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 2L11 13"/><path d="M22 2L15 22l-4-9-9-4 20-7z"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getFiles, imgUrl } from '../api/files'

const route = useRoute()
const router = useRouter()

const date = computed(() => route.query.date || '')
const fileType = computed(() => route.query.type || '')
const searchQ = ref('')
const loading = ref(false)
const allFiles = ref([])

const TYPE_LABELS = { image:'图片', video:'视频', document:'文档', audio:'音频', link:'链接', other:'其他' }
const FILE_ICONS  = { image:'🖼', video:'🎬', document:'📄', audio:'🎵', link:'🔗', other:'📦' }
const FILE_BG = {
  image:'rgba(139,114,255,.15)', video:'rgba(255,110,122,.15)',
  document:'rgba(94,234,181,.15)', audio:'rgba(255,170,92,.15)',
  link:'rgba(100,170,255,.15)', other:'rgba(255,255,255,.08)',
}
const typeLabel  = computed(() => TYPE_LABELS[fileType.value] || '')
const fileIcon   = t => FILE_ICONS[t]  || '📦'
const fileLabel  = t => TYPE_LABELS[t] || '其他'
const iconBg     = t => FILE_BG[t]     || FILE_BG.other

const dateLabel = computed(() => {
  if (!date.value) return ''
  const [y, m, d] = date.value.split('-')
  return `${y}年${parseInt(m)}月${parseInt(d)}日`
})

const searchPlaceholder = computed(() =>
  typeLabel.value
    ? `在${dateLabel.value}的${typeLabel.value}中 AI 搜索…`
    : `在${dateLabel.value}中 AI 搜索…`
)

const dayFiles = computed(() =>
  allFiles.value.filter(f => {
    const fDate = f.created_at?.slice(0, 10)
    const typeMatch = !fileType.value || f.type === fileType.value
    return fDate === date.value && typeMatch
  }).sort((a, b) => a.created_at.localeCompare(b.created_at))
)

function fmtSize(b) {
  if (!b) return ''
  if (b > 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`
  return `${(b / 1024).toFixed(0)} KB`
}
function timeStr(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
}

function submitSearch() {
  const q = searchQ.value.trim()
  if (!q) return
  searchQ.value = ''
  router.push({ path: '/search', query: { q, date: date.value, type: fileType.value } })
}

onMounted(async () => {
  loading.value = true
  try {
    allFiles.value = await getFiles({ limit: 200 })
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page { position: relative; height: 100%; display: flex; flex-direction: column; background: var(--bg); overflow: hidden; }
.page-bg {
  position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(ellipse 280px 200px at 80% 10%, rgba(139,114,255,.06) 0%, transparent 65%), var(--bg);
}

/* Header */
.app-hdr {
  position: relative; z-index: 10; height: 90px;
  display: flex; align-items: flex-end; padding: 0 16px 14px; gap: 10px;
  background: var(--bg-blur); backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.app-back {
  width: 32px; height: 32px; border: none; background: none;
  color: var(--accent); font-size: 26px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.hdr-body { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.app-hdr-ttl { font-size: 17px; font-weight: 700; color: var(--text); }
.hdr-badge {
  font-size: 11px; color: var(--accent); font-weight: 500;
  background: var(--accent-s); border: 1px solid rgba(139,114,255,.2);
  border-radius: 6px; padding: 1px 7px; align-self: flex-start;
}

/* Feed */
.day-feed {
  flex: 1; overflow-y: auto; padding: 12px 16px 16px;
  display: flex; flex-direction: column; gap: 8px;
  position: relative; z-index: 1;
}
.feed-center {
  display: flex; flex-direction: column; align-items: center;
  gap: 10px; padding: 60px 0; color: var(--text3); font-size: 13px; margin: auto;
}
.orb-mini {
  width: 32px; height: 32px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--teal));
  animation: spin .9s linear infinite; opacity: .5;
}
@keyframes spin { to { transform: rotate(360deg); } }

.file-count-tip {
  font-size: 11px; color: var(--text3); text-align: center; padding: 2px 0 4px;
}

/* Day card */
.day-card {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; border-radius: 16px;
  cursor: pointer;
  transition: transform .15s cubic-bezier(.32,.72,0,1), background .15s;
}
.day-card:active { transform: scale(.98); background: var(--s3); }

.dc-img-wrap, .dc-link-cover {
  width: 50px; height: 50px; border-radius: 10px;
  overflow: hidden; flex-shrink: 0;
  background: var(--s3);
  display: flex; align-items: center; justify-content: center;
}
.dc-img { width: 100%; height: 100%; object-fit: cover; }
.dc-fav { width: 28px; height: 28px; border-radius: 6px; object-fit: contain; }
.dc-icon { font-size: 24px; }
.dc-file-ico {
  width: 50px; height: 50px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 24px;
}

.dc-body { flex: 1; min-width: 0; }
.dc-name {
  font-size: 13px; font-weight: 500; color: var(--text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 3px;
}
.dc-meta { font-size: 11px; color: var(--text3); }
.dc-time { color: var(--text3); }
.dc-summary {
  font-size: 11px; color: var(--text3); margin-top: 3px; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}

.dc-status { flex-shrink: 0; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; display: block; }
.status-dot.pending { background: var(--orange); animation: pulse 1.4s infinite; }
.status-dot.ready   { background: var(--teal); }
.status-dot.failed  { background: var(--red); }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

/* Bottom search bar */
.day-search-bar {
  position: relative; z-index: 10;
  padding: 10px 14px 18px;
  background: var(--bg-blur); backdrop-filter: blur(20px);
  border-top: 1px solid var(--border); flex-shrink: 0;
}
.day-search-inner {
  display: flex; align-items: center; gap: 8px;
  background: var(--s2); border: 1px solid var(--border2);
  border-radius: 22px; padding: 0 6px 0 14px; height: 44px;
}
.day-search-input {
  flex: 1; background: none; border: none; outline: none;
  font-family: inherit; font-size: 13px; color: var(--text);
}
.day-search-input::placeholder { color: var(--text3); }
.day-search-send {
  width: 32px; height: 32px; border-radius: 50%; border: none;
  background: var(--accent); color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0;
  box-shadow: 0 0 10px var(--accent-g);
  transition: transform .15s, opacity .15s;
}
.day-search-send:disabled { opacity: .35; cursor: not-allowed; box-shadow: none; }
.day-search-send:not(:disabled):active { transform: scale(.88); }
</style>
