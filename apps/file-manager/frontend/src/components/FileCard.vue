<template>
  <div class="fm-card-wrap" @touchstart.passive="onTS" @touchmove.passive="onTM" @touchend.passive="onTE">
    <div
      class="fm-file-card gc"
      :class="{ 'no-pad': file.type === 'link' && file.og_image }"
      :style="{ transform: `translateX(${swipeX}px)` }"
      @click="handleClick"
    >
      <!-- Link card with OG image banner -->
      <template v-if="file.type === 'link' && file.og_image">
        <div class="fm-link-card">
          <img class="link-og" :src="file.og_image" loading="lazy" @error="e => e.target.style.display='none'" />
          <div class="link-body">
            <div class="link-title-row">
              <img v-if="file.favicon_url" class="link-favicon" :src="file.favicon_url" loading="lazy" @error="e => e.target.style.display='none'" />
              <span class="fm-file-name">{{ file.original_filename }}</span>
            </div>
            <div class="fm-file-meta">
              <span class="type-chip link">链接</span>
              <span class="status-dot" :class="file.status"></span>
              <span class="meta-time">{{ timeStr }}</span>
            </div>
            <div v-if="file.summary" class="fm-summary">{{ file.summary }}</div>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="fm-file-ico" :class="iconBg">
          <img v-if="file.type === 'link' && file.favicon_url" class="ico-favicon" :src="file.favicon_url" loading="lazy" @error="e => e.target.style.display='none'" />
          <span v-else>{{ typeIcon }}</span>
        </div>
        <div class="fm-file-body">
          <div class="fm-file-name">{{ file.original_filename }}</div>
          <div class="fm-file-meta">
            <span class="type-chip" :class="file.type">{{ typeLabel }}</span>
            <span class="status-dot" :class="file.status"></span>
            <span class="meta-time">{{ timeStr }}</span>
          </div>
          <div v-if="file.summary" class="fm-summary">{{ file.summary }}</div>
        </div>
      </template>
    </div>
    <!-- Delete action revealed on swipe-left -->
    <button class="delete-action" :class="{ visible: swipeX < -20 }" @click.stop="$emit('delete', file)">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/>
      </svg>
    </button>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({ file: Object })
const emit = defineEmits(['click', 'delete'])

const TYPE_ICONS  = { image:'🖼', video:'🎬', document:'📄', audio:'🎵', link:'🔗', other:'📦' }
const TYPE_LABELS = { image:'图片', video:'视频', document:'文档', audio:'音频', link:'链接', other:'其他' }
const ICON_BG     = { image:'ico-purple', video:'ico-red', document:'ico-teal', audio:'ico-orange', link:'ico-blue', other:'ico-gray' }

const typeIcon  = computed(() => TYPE_ICONS[props.file.type]  || '📦')
const typeLabel = computed(() => TYPE_LABELS[props.file.type] || '其他')
const iconBg    = computed(() => ICON_BG[props.file.type]     || 'ico-gray')

const timeStr = computed(() => {
  const d = new Date(props.file.created_at)
  return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
})

// Swipe-left to reveal delete
const swipeX = ref(0)
let tsX = 0, tsY = 0, swiping = false

function onTS(e) { tsX = e.touches[0].clientX; tsY = e.touches[0].clientY; swiping = false }
function onTM(e) {
  const dx = e.touches[0].clientX - tsX
  const dy = e.touches[0].clientY - tsY
  if (!swiping && Math.abs(dx) > Math.abs(dy) + 5) swiping = true
  if (!swiping) return
  swipeX.value = Math.max(-72, Math.min(0, dx))
}
function onTE() {
  if (swipeX.value < -36) swipeX.value = -64
  else swipeX.value = 0
  swiping = false
}
function handleClick() {
  if (swipeX.value < -10) { swipeX.value = 0; return }
  emit('click', props.file)
}

// Reset swipe when clicking outside (global touch)
</script>

<style scoped>
.fm-card-wrap {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
}

.fm-file-card {
  width: 100%;
  padding: 12px 14px;
  display: flex;
  gap: 12px;
  align-items: center;
  cursor: pointer;
  border-radius: 16px;
  transition: transform .3s cubic-bezier(.32,.72,0,1), background .15s, box-shadow .2s;
  position: relative; z-index: 1;
  /* card swipe handled by inline style */
}
.fm-file-card:active { background: var(--s3); transform: scale(.97); }

/* Delete button behind card */
.delete-action {
  position: absolute; right: 0; top: 0; bottom: 0;
  width: 64px;
  background: rgba(255,60,60,.85);
  border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: #fff; border-radius: 0 16px 16px 0;
  opacity: 0; transition: opacity .18s;
  z-index: 0;
}
.delete-action.visible { opacity: 1; }
.delete-action:active { background: var(--red); }

.fm-file-ico {
  width: 44px; height: 44px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; flex-shrink: 0;
}
.ico-purple { background: rgba(139,114,255,.15); box-shadow: 0 2px 10px rgba(139,114,255,.18); }
.ico-red    { background: rgba(255,110,122,.15); box-shadow: 0 2px 10px rgba(255,110,122,.18); }
.ico-teal   { background: rgba(94,234,181,.15);  box-shadow: 0 2px 10px rgba(94,234,181,.18);  }
.ico-orange { background: rgba(255,170,92,.15);  box-shadow: 0 2px 10px rgba(255,170,92,.18);  }
.ico-blue   { background: rgba(100,170,255,.15); box-shadow: 0 2px 10px rgba(100,170,255,.18); }
.ico-gray   { background: var(--s3); }

.fm-file-body { flex: 1; min-width: 0; }

.fm-file-name {
  font-size: 14px; font-weight: 600; color: var(--text);
  margin-bottom: 4px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.fm-file-meta {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; color: var(--text3);
}
.meta-time { color: var(--text3); }

.type-chip {
  font-size: 10px; font-weight: 600;
  padding: 2px 7px; border-radius: 6px;
}
.type-chip.image    { background: rgba(139,114,255,.15); color: var(--accent); }
.type-chip.video    { background: rgba(255,110,122,.15); color: var(--red); }
.type-chip.document { background: rgba(94,234,181,.15);  color: var(--teal); }
.type-chip.audio    { background: rgba(255,170,92,.15);  color: var(--orange); }
.type-chip.link     { background: rgba(100,170,255,.15); color: #64AAFF; }
.type-chip.other    { background: var(--s3);             color: var(--text3); }

.status-dot {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
}
.status-dot.pending { background: var(--orange); animation: pulse 1.4s infinite; }
.status-dot.ready   { background: var(--teal); }
.status-dot.failed  { background: var(--red); }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

.fm-file-card.no-pad { padding: 0; overflow: hidden; }

/* Link card with OG image */
.fm-link-card {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column;
}
.link-og {
  width: 100%; height: 110px;
  object-fit: cover;
  display: block;
}
.link-body {
  padding: 8px 12px 10px;
  display: flex; flex-direction: column; gap: 4px;
}
.link-title-row {
  display: flex; align-items: center; gap: 6px;
}
.link-favicon {
  width: 14px; height: 14px; border-radius: 3px; flex-shrink: 0;
  object-fit: contain;
}
.ico-favicon {
  width: 22px; height: 22px; border-radius: 5px; object-fit: contain;
}

.fm-summary {
  font-size: 11px; color: var(--text3);
  margin-top: 5px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}
</style>
