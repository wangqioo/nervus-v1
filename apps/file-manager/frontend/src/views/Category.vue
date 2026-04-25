<template>
  <div class="page">
    <div class="page-bg"></div>
    <header class="app-hdr">
      <button class="app-back" @click="$router.back()">‹</button>
      <span class="app-hdr-ttl">文件分类</span>
      <span style="width:32px"></span>
    </header>

    <div class="app-body" :style="expanded ? 'padding-bottom: 80px' : ''">
      <div v-if="loading" class="center-tip">加载中...</div>
      <template v-else>

        <!-- Summary grid -->
        <div class="cat-grid">
          <div
            v-for="cat in categories" :key="cat.type"
            class="cat-tile"
            :class="[cat.type, { active: expanded === cat.type }]"
            @click="toggleCat(cat.type)"
          >
            <div class="tile-glow"></div>
            <div class="tile-ico"><component :is="cat.svg" /></div>
            <div class="tile-count">{{ cat.count }}</div>
            <div class="tile-label">{{ cat.label }}</div>
          </div>
        </div>

        <!-- Timeline -->
        <transition name="expand">
          <div v-if="expanded" class="timeline-block">
            <div class="tl-header">
              <component :is="expandedCat?.svg" class="tl-hdr-ico" />
              <span>{{ expandedCat?.label }}时间线</span>
              <button class="close-btn" @click="expanded = null">✕</button>
            </div>

            <div v-if="!timeline.length" class="center-tip small">暂无文件</div>

            <div v-for="year in timeline" :key="year.year" class="tl-year-group">
              <div class="tl-year-label">
                <span>{{ year.year }}年</span>
                <span class="tl-total">{{ year.total }} 个</span>
              </div>

              <div v-for="month in year.months" :key="month.key" class="tl-month-group">
                <div class="tl-month-label">{{ parseInt(month.month) }}月</div>

                <div
                  v-for="day in month.days" :key="day.date"
                  class="tl-day-row"
                  @click="goDay(day.date)"
                >
                  <div class="tl-dot"></div>
                  <span class="tl-day-num">{{ parseInt(day.day) }}日</span>
                  <span class="tl-day-count">{{ day.count }} 个文件</span>
                  <svg class="tl-arrow" viewBox="0 0 16 16" fill="none">
                    <path d="M6 4l4 4-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </div>
              </div>
            </div>
          </div>
        </transition>

      </template>
    </div>

    <!-- Bottom AI search bar -->
    <transition name="bar-slide">
      <div v-if="expanded" class="cat-search-bar">
        <div class="cat-search-inner">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" style="flex-shrink:0;color:var(--text3)">
            <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
          </svg>
          <input
            v-model="searchQ"
            class="cat-search-input"
            :placeholder="`搜索${expandedCat?.label || ''}文件...`"
            @keydown.enter="submitCatSearch"
          />
          <button class="cat-search-send" @click="submitCatSearch" :disabled="!searchQ.trim()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 2L11 13"/><path d="M22 2L15 22l-4-9-9-4 20-7z"/>
            </svg>
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { useRouter } from 'vue-router'
import { getStats, getFiles } from '../api/files'

const router = useRouter()
const searchQ = ref('')
const loading = ref(false)
const stats = ref(null)
const allFiles = ref([])
const expanded = ref(null)

function submitCatSearch() {
  const q = searchQ.value.trim()
  if (!q) return
  searchQ.value = ''
  router.push({ path: '/search', query: { q, type: expanded.value } })
}

/* ── SVG icon components ── */
const SvgImage = () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
  h('rect', { x: '3', y: '3', width: '18', height: '18', rx: '3' }),
  h('circle', { cx: '8.5', cy: '8.5', r: '1.5' }),
  h('path', { d: 'M21 15l-5-5L5 21' }),
])
const SvgVideo = () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
  h('rect', { x: '2', y: '4', width: '15', height: '16', rx: '3' }),
  h('path', { d: 'M17 8l5-2v12l-5-2V8z' }),
])
const SvgDoc = () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
  h('path', { d: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' }),
  h('polyline', { points: '14 2 14 8 20 8' }),
  h('line', { x1: '8', y1: '13', x2: '16', y2: '13' }),
  h('line', { x1: '8', y1: '17', x2: '14', y2: '17' }),
])
const SvgAudio = () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
  h('path', { d: 'M9 18V5l12-2v13' }),
  h('circle', { cx: '6', cy: '18', r: '3' }),
  h('circle', { cx: '18', cy: '16', r: '3' }),
])
const SvgLink = () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
  h('path', { d: 'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71' }),
  h('path', { d: 'M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71' }),
])
const SvgOther = () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
  h('rect', { x: '2', y: '7', width: '20', height: '14', rx: '2' }),
  h('path', { d: 'M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2' }),
  h('line', { x1: '12', y1: '12', x2: '12', y2: '16' }),
  h('line', { x1: '10', y1: '14', x2: '14', y2: '14' }),
])
const SvgText = () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
  h('path', { d: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z' }),
])

const CATS = [
  { type: 'image',    label: '图片', svg: SvgImage },
  { type: 'video',    label: '视频', svg: SvgVideo },
  { type: 'document', label: '文档', svg: SvgDoc   },
  { type: 'audio',    label: '音频', svg: SvgAudio },
  { type: 'link',     label: '链接', svg: SvgLink  },
  { type: 'text',     label: '文字', svg: SvgText  },
  { type: 'other',    label: '其他', svg: SvgOther },
]

const categories = computed(() =>
  CATS.map(c => ({ ...c, count: stats.value?.by_type?.[c.type] || 0 }))
    .filter(c => c.count > 0)
    .sort((a, b) => b.count - a.count)
)

const expandedCat = computed(() => CATS.find(c => c.type === expanded.value))

const catFiles = computed(() =>
  allFiles.value.filter(f => f.type === expanded.value)
)

/* Build year → month → day tree from catFiles */
const timeline = computed(() => {
  const byYear = {}
  for (const f of catFiles.value) {
    const date = f.created_at?.slice(0, 10)
    if (!date) continue
    const [y, m, d] = date.split('-')
    if (!byYear[y]) byYear[y] = {}
    if (!byYear[y][m]) byYear[y][m] = {}
    byYear[y][m][d] = (byYear[y][m][d] || 0) + 1
  }
  return Object.keys(byYear).sort((a, b) => b - a).map(year => {
    const months = Object.keys(byYear[year]).sort((a, b) => b - a).map(month => ({
      month,
      key: `${year}-${month}`,
      days: Object.keys(byYear[year][month]).sort((a, b) => b - a).map(day => ({
        date: `${year}-${month}-${day}`,
        day,
        count: byYear[year][month][day],
      })),
    }))
    const total = months.reduce((s, m) => s + m.days.reduce((s2, d) => s2 + d.count, 0), 0)
    return { year, total, months }
  })
})

function toggleCat(type) {
  expanded.value = expanded.value === type ? null : type
}

function goDay(date) {
  router.push({ path: '/day', query: { date, type: expanded.value } })
}

onMounted(async () => {
  loading.value = true
  try {
    ;[stats.value, allFiles.value] = await Promise.all([getStats(), getFiles({ limit: 200 })])
  } finally { loading.value = false }
})
</script>

<style scoped>
.page { position: relative; height: 100%; overflow: hidden; background: var(--bg); display: flex; flex-direction: column; }
.page-bg {
  position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(ellipse 300px 240px at 80% 10%, rgba(255,170,92,.07) 0%, transparent 65%), var(--bg);
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
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.app-hdr-ttl { font-size: 17px; font-weight: 700; color: var(--text); flex: 1; }

.app-body { flex: 1; overflow-y: auto; padding: 16px 16px 32px; position: relative; z-index: 1; }

.center-tip { text-align: center; color: var(--text3); font-size: 13px; padding: 28px; }
.center-tip.small { padding: 14px; }

/* ── Category tile grid ── */
.cat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }

.cat-tile {
  position: relative; overflow: hidden; border-radius: 20px; padding: 18px 12px 14px;
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  cursor: pointer; border: 1px solid var(--border);
  transition: transform .22s cubic-bezier(.32,.72,0,1), box-shadow .22s;
  background: var(--s2);
}
.cat-tile:active { transform: scale(.94); }
.cat-tile.active { box-shadow: 0 0 0 2px var(--accent); }

.cat-tile.image    { border-color: rgba(139,114,255,.22); }
.cat-tile.video    { border-color: rgba(255,110,122,.22); }
.cat-tile.document { border-color: rgba(94,234,181,.22);  }
.cat-tile.audio    { border-color: rgba(255,170,92,.22);  }
.cat-tile.link     { border-color: rgba(100,170,255,.22); }
.cat-tile.text     { border-color: rgba(139,114,255,.22); }
.cat-tile.other    { border-color: var(--border2);        }

.tile-glow {
  position: absolute; top: -20px; left: 50%; transform: translateX(-50%);
  width: 80px; height: 80px; border-radius: 50%; pointer-events: none; opacity: .55;
}
.cat-tile.image    .tile-glow { background: radial-gradient(circle, rgba(139,114,255,.4) 0%, transparent 70%); }
.cat-tile.video    .tile-glow { background: radial-gradient(circle, rgba(255,110,122,.4) 0%, transparent 70%); }
.cat-tile.document .tile-glow { background: radial-gradient(circle, rgba(94,234,181,.4)  0%, transparent 70%); }
.cat-tile.audio    .tile-glow { background: radial-gradient(circle, rgba(255,170,92,.4)  0%, transparent 70%); }
.cat-tile.link     .tile-glow { background: radial-gradient(circle, rgba(100,170,255,.4) 0%, transparent 70%); }
.cat-tile.text     .tile-glow { background: radial-gradient(circle, rgba(139,114,255,.4) 0%, transparent 70%); }
.cat-tile.other    .tile-glow { background: radial-gradient(circle, rgba(180,180,200,.3) 0%, transparent 70%); }

.tile-ico { width: 50px; height: 50px; border-radius: 16px; display: flex; align-items: center; justify-content: center; position: relative; z-index: 1; }
.tile-ico svg { width: 24px; height: 24px; }
.cat-tile.image    .tile-ico { background: rgba(139,114,255,.15); color: #A98FFF; box-shadow: 0 4px 18px rgba(139,114,255,.25), inset 0 1px 0 rgba(139,114,255,.2); }
.cat-tile.video    .tile-ico { background: rgba(255,110,122,.15); color: #FF8A95; box-shadow: 0 4px 18px rgba(255,110,122,.25), inset 0 1px 0 rgba(255,110,122,.2); }
.cat-tile.document .tile-ico { background: rgba(94,234,181,.15);  color: #6EE9BE; box-shadow: 0 4px 18px rgba(94,234,181,.25),  inset 0 1px 0 rgba(94,234,181,.2);  }
.cat-tile.audio    .tile-ico { background: rgba(255,170,92,.15);  color: #FFB96A; box-shadow: 0 4px 18px rgba(255,170,92,.25),  inset 0 1px 0 rgba(255,170,92,.2);  }
.cat-tile.link     .tile-ico { background: rgba(100,170,255,.15); color: #7AB8FF; box-shadow: 0 4px 18px rgba(100,170,255,.25), inset 0 1px 0 rgba(100,170,255,.2); }
.cat-tile.other    .tile-ico { background: var(--s3);             color: var(--text2); box-shadow: 0 4px 14px rgba(0,0,0,.15); }

.tile-count { font-size: 22px; font-weight: 800; color: var(--text); line-height: 1; position: relative; z-index: 1; letter-spacing: -.5px; }
.tile-label { font-size: 11px; font-weight: 600; color: var(--text3); letter-spacing: .04em; position: relative; z-index: 1; }

/* ── Timeline ── */
.timeline-block { display: flex; flex-direction: column; gap: 0; }

.tl-header {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; margin-bottom: 12px;
  background: var(--s2); border: 1px solid var(--border2); border-radius: 14px;
}
.tl-hdr-ico { width: 16px; height: 16px; flex-shrink: 0; color: var(--accent); }
.tl-header span { flex: 1; font-size: 14px; font-weight: 700; color: var(--text); }
.close-btn {
  width: 24px; height: 24px; border-radius: 50%;
  background: var(--s3); border: none; color: var(--text3);
  font-size: 12px; cursor: pointer; display: flex; align-items: center; justify-content: center;
}

.tl-year-group { margin-bottom: 16px; }

.tl-year-label {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 15px; font-weight: 800; color: var(--text);
  padding: 0 4px 8px; border-bottom: 1px solid var(--border);
  margin-bottom: 10px;
}
.tl-total { font-size: 11px; color: var(--text3); font-weight: 400; }

.tl-month-group { padding-left: 8px; margin-bottom: 10px; }

.tl-month-label {
  font-size: 12px; font-weight: 600; color: var(--accent);
  margin-bottom: 4px; padding: 0 4px;
  letter-spacing: .04em;
}

.tl-day-row {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 12px 11px 16px; margin-bottom: 4px;
  background: var(--s2); border: 1px solid var(--border); border-radius: 12px;
  cursor: pointer; position: relative;
  transition: background .15s, transform .15s cubic-bezier(.32,.72,0,1);
}
.tl-day-row:active { background: var(--s3); transform: scale(.98); }

.tl-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--accent); flex-shrink: 0;
  box-shadow: 0 0 6px var(--accent-g);
}
.tl-day-num { font-size: 14px; font-weight: 600; color: var(--text); min-width: 32px; }
.tl-day-count { flex: 1; font-size: 12px; color: var(--text3); }
.tl-arrow { width: 16px; height: 16px; color: var(--text3); flex-shrink: 0; }

/* Expand transition */
.expand-enter-active { transition: opacity .25s, transform .3s cubic-bezier(.32,.72,0,1); }
.expand-leave-active { transition: opacity .2s; }
.expand-enter-from   { opacity: 0; transform: translateY(10px); }
.expand-leave-to     { opacity: 0; }

/* ── Bottom AI search bar ── */
.cat-search-bar {
  position: absolute; bottom: 0; left: 0; right: 0; z-index: 20;
  padding: 10px 14px 18px;
  background: var(--bg-blur); backdrop-filter: blur(20px);
  border-top: 1px solid var(--border);
}
.cat-search-inner {
  display: flex; align-items: center; gap: 8px;
  background: var(--s2); border: 1px solid var(--border2);
  border-radius: 22px; padding: 0 6px 0 14px; height: 44px;
}
.cat-search-input {
  flex: 1; background: none; border: none; outline: none;
  font-family: inherit; font-size: 13px; color: var(--text);
}
.cat-search-input::placeholder { color: var(--text3); }
.cat-search-send {
  width: 32px; height: 32px; border-radius: 50%; border: none;
  background: var(--accent); color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0;
  transition: transform .15s, opacity .15s;
}
.cat-search-send:disabled { opacity: .35; cursor: not-allowed; }
.cat-search-send:not(:disabled):active { transform: scale(.88); }

.bar-slide-enter-active { transition: transform .3s cubic-bezier(.32,.72,0,1), opacity .25s; }
.bar-slide-leave-active { transition: transform .25s cubic-bezier(.32,.72,0,1), opacity .2s; }
.bar-slide-enter-from, .bar-slide-leave-to { transform: translateY(100%); opacity: 0; }
</style>
