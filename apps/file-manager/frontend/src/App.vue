<template>
  <!-- Embedded (iframe) mode: no phone shell, fill the iframe directly -->
  <template v-if="isIframe">
    <div class="embed-root"
      @touchstart.passive="onTouchStart"
      @touchend.passive="onTouchEnd"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
    >
      <router-view v-slot="{ Component }">
        <transition :name="transitionName" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>
  </template>

  <!-- Standalone mode: full phone frame -->
  <template v-else>
    <div class="stage">
      <div class="phone" id="phone">
        <div class="di"></div>
        <div class="sb">
          <span class="sb-time">{{ timeStr }}</span>
          <div class="sb-icons">
            <svg width="17" height="12" viewBox="0 0 17 12"><rect x="0" y="3" width="3" height="9" rx="1" fill="currentColor" opacity=".4"/><rect x="4.5" y="2" width="3" height="10" rx="1" fill="currentColor" opacity=".6"/><rect x="9" y="0" width="3" height="12" rx="1" fill="currentColor"/><rect x="14" y="4" width="2.5" height="7" rx=".8" fill="currentColor" opacity=".3"/></svg>
            <svg width="16" height="12" viewBox="0 0 16 12"><path d="M8 2.5C10.5 2.5 12.7 3.5 14.2 5.2L15.5 3.8C13.6 1.7 11 .5 8 .5S2.4 1.7.5 3.8L1.8 5.2C3.3 3.5 5.5 2.5 8 2.5Z" fill="currentColor" opacity=".4"/><path d="M8 5.5C9.7 5.5 11.2 6.2 12.3 7.3L13.6 5.9C12.1 4.4 10.2 3.5 8 3.5S3.9 4.4 2.4 5.9L3.7 7.3C4.8 6.2 6.3 5.5 8 5.5Z" fill="currentColor" opacity=".7"/><circle cx="8" cy="10" r="1.8" fill="currentColor"/></svg>
            <svg width="25" height="12" viewBox="0 0 25 12"><rect x=".5" y=".5" width="21" height="11" rx="3.5" stroke="currentColor" stroke-opacity=".35" fill="none"/><rect x="22.5" y="4" width="2" height="4" rx="1" fill="currentColor" opacity=".4"/><rect x="2" y="2" width="16" height="8" rx="2" fill="currentColor"/></svg>
          </div>
        </div>
        <div class="viewport"
          @touchstart.passive="onTouchStart"
          @touchend.passive="onTouchEnd"
          @mousedown="onMouseDown"
          @mousemove="onMouseMove"
          @mouseup="onMouseUp"
          @mouseleave="onMouseUp"
        >
          <router-view v-slot="{ Component }">
            <transition :name="transitionName" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </div>
        <div class="home-indicator"></div>
      </div>
    </div>
  </template>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from './composables/useTheme'

useTheme()
const router = useRouter()
const route  = useRoute()

const isIframe = window.self !== window.top

const timeStr = ref('')
function updateTime() {
  const d = new Date()
  timeStr.value = `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
}

function updateScale() {
  const PW = 390, PH = 844
  const s = Math.min(1, (window.innerHeight - 40) / PH, (window.innerWidth - 40) / PW)
  document.documentElement.style.setProperty('--phone-scale', s)
}

// ── Transition direction tracking ────────────────────────────
const transitionName = ref('slide-forward')
const routeHistory = ['/']

router.afterEach((to, from) => {
  const idx = routeHistory.lastIndexOf(to.path)
  if (idx >= 0 && idx < routeHistory.length - 1) {
    transitionName.value = 'slide-back'
    routeHistory.splice(idx + 1)
  } else {
    transitionName.value = 'slide-forward'
    if (routeHistory[routeHistory.length - 1] !== to.path) routeHistory.push(to.path)
  }
})

// ── Global right-swipe to go back ────────────────────────────
let txStart = 0, tyStart = 0
function onTouchStart(e) {
  txStart = e.touches[0].clientX
  tyStart = e.touches[0].clientY
}
function onTouchEnd(e) {
  const dx = e.changedTouches[0].clientX - txStart
  const dy = e.changedTouches[0].clientY - tyStart
  if (Math.abs(dx) <= Math.abs(dy) + 10) return
  if (dx > 60) {
    if (route.path !== '/') router.back()
    else if (isIframe) window.parent.postMessage({ type: 'nervus-nav', action: 'back' }, '*')
  }
}

let mouseDown = false, mxStart = 0, myStart = 0, mouseMoved = false
function onMouseDown(e) {
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
  mouseMoved = false
  const dx = e.clientX - mxStart
  const dy = e.clientY - myStart
  if (Math.abs(dx) <= Math.abs(dy) + 10) return
  if (dx > 60) {
    if (route.path !== '/') router.back()
    else if (isIframe) window.parent.postMessage({ type: 'nervus-nav', action: 'back' }, '*')
  }
}

let timer
onMounted(() => {
  updateTime(); timer = setInterval(updateTime, 10000)
  updateScale(); window.addEventListener('resize', updateScale)
})
onUnmounted(() => { clearInterval(timer); window.removeEventListener('resize', updateScale) })
</script>

<style>
*, *::before, *::after {
  box-sizing: border-box; margin: 0; padding: 0;
  -webkit-font-smoothing: antialiased;
  -webkit-tap-highlight-color: transparent;
}
* { scrollbar-width: none; }
*::-webkit-scrollbar { display: none; }

/* ── DARK ── */
:root, [data-theme="dark"] {
  --bg: #07070E;
  --bg-blur: rgba(7,7,14,.88);
  --s1: rgba(255,255,255,.04);
  --s2: rgba(255,255,255,.07);
  --s3: rgba(255,255,255,.12);
  --border: rgba(255,255,255,.07);
  --border2: rgba(255,255,255,.13);
  --text: #EEEEF8;
  --text2: rgba(238,238,248,.55);
  --text3: rgba(238,238,248,.28);
  --accent: #8B72FF;
  --accent-s: rgba(139,114,255,.13);
  --accent-g: rgba(139,114,255,.4);
  --teal: #5EEAB5;
  --teal-s: rgba(94,234,181,.13);
  --orange: #FFAA5C;
  --red: #FF6E7A;
  --card: #13132A;
  --radius: 16px;
  --header-h: 90px;
  --PW: 390px; --PH: 844px;
}

/* ── LIGHT ── */
[data-theme="light"] {
  --bg: #F2F2F7;
  --bg-blur: rgba(242,242,247,.92);
  --s1: rgba(0,0,0,.04);
  --s2: rgba(255,255,255,.82);
  --s3: rgba(0,0,0,.08);
  --border: rgba(0,0,0,.08);
  --border2: rgba(0,0,0,.13);
  --text: #1C1C1E;
  --text2: rgba(28,28,30,.60);
  --text3: rgba(28,28,30,.38);
  --accent: #6B52F0;
  --accent-s: rgba(107,82,240,.10);
  --accent-g: rgba(107,82,240,.28);
  --teal: #00C896;
  --teal-s: rgba(0,200,150,.12);
  --orange: #E0820A;
  --red: #E8344A;
  --card: #FFFFFF;
}

/* ── Iframe embed mode ── */
.embed-root {
  position: fixed;
  inset: 0;
  overflow: hidden;
  clip-path: inset(0);
  -webkit-clip-path: inset(0);
  background: var(--bg);
}

/* ── Page body / stage ── */
html, body { width: 100%; height: 100%; overflow: hidden; }

body {
  background: var(--bg);
  font-family: 'PingFang SC', -apple-system, 'Helvetica Neue', sans-serif;
  color: var(--text);
  display: flex; align-items: center; justify-content: center;
}

/* ── Phone shell ── */
.stage {
  display: flex; align-items: center; justify-content: center;
  width: 100vw; height: 100vh;
  /* scale phone to fit viewport, keeping a little breathing room */
  container-type: size;
}

.phone {
  width: var(--PW); height: var(--PH);
  transform-origin: center center;
  transform: scale(var(--phone-scale, 1));
  border-radius: 52px;
  background: var(--bg);
  position: relative; overflow: hidden;
  user-select: none;
  box-shadow:
    0 0 0 1px rgba(255,255,255,.15),
    0 0 0 9px #181828,
    0 0 0 10px rgba(255,255,255,.06),
    0 60px 120px rgba(0,0,0,.9),
    0 20px 40px rgba(0,0,0,.5);
  transition: background .3s;
}

[data-theme="light"] .phone {
  box-shadow:
    0 0 0 1px rgba(0,0,0,.12),
    0 0 0 9px #C8C8D8,
    0 0 0 10px rgba(0,0,0,.04),
    0 60px 120px rgba(0,0,0,.35),
    0 20px 40px rgba(0,0,0,.15);
}

/* Side buttons */
.phone::before {
  content: '';
  position: absolute; left: -12px; top: 120px;
  width: 4px; height: 60px;
  background: #1e1e30; border-radius: 3px 0 0 3px;
  box-shadow: 0 70px 0 #1e1e30;
}
.phone::after {
  content: '';
  position: absolute; right: -12px; top: 150px;
  width: 4px; height: 80px;
  background: #1e1e30; border-radius: 0 3px 3px 0;
}

/* Dynamic Island */
.di {
  position: absolute; top: 13px; left: 50%;
  transform: translateX(-50%);
  width: 126px; height: 36px;
  background: #000; border-radius: 20px;
  z-index: 200;
  box-shadow: 0 0 0 1px rgba(255,255,255,.08);
}

/* Status bar */
.sb {
  position: absolute; top: 0; left: 0; right: 0; height: 58px;
  display: flex; align-items: flex-end; justify-content: space-between;
  padding: 0 28px 10px; z-index: 150; pointer-events: none;
}
.sb-time {
  font-size: 15px; font-weight: 600; color: var(--text); letter-spacing: -.3px;
  font-variant-numeric: tabular-nums;
}
.sb-icons { display: flex; align-items: center; gap: 6px; }
.sb-icons svg { color: var(--text); }

/* Viewport (app content area) */
.viewport {
  position: absolute; inset: 0;
  border-radius: 52px;
  overflow: hidden;
  clip-path: inset(0);
  -webkit-clip-path: inset(0);
}

/* Home indicator */
.home-indicator {
  position: absolute; bottom: 8px; left: 50%;
  transform: translateX(-50%);
  width: 134px; height: 5px;
  background: var(--text); opacity: .25;
  border-radius: 3px; z-index: 200;
  pointer-events: none;
}

/* Page transitions — forward (push) */
.slide-forward-enter-active, .slide-forward-leave-active {
  transition: transform .36s cubic-bezier(.32,.72,0,1), opacity .28s;
}
.slide-forward-enter-from { transform: translateX(100%); opacity: 0; }
.slide-forward-leave-to   { transform: translateX(-30%); opacity: 0; }

/* Page transitions — back (swipe right) */
.slide-back-enter-active, .slide-back-leave-active {
  transition: transform .36s cubic-bezier(.32,.72,0,1), opacity .28s;
}
.slide-back-enter-from { transform: translateX(-100%); opacity: 0; }
.slide-back-leave-to   { transform: translateX(30%);  opacity: 0; }

/* Glass card shared class */
.gc {
  background: var(--s2);
  border: 1px solid var(--border2);
  border-radius: var(--radius);
  position: relative; overflow: hidden;
}
.gc::after {
  content: ''; position: absolute; inset: 0; border-radius: inherit;
  background: linear-gradient(135deg, rgba(255,255,255,.05) 0%, transparent 60%);
  pointer-events: none;
}
[data-theme="light"] .gc::after {
  background: linear-gradient(135deg, rgba(255,255,255,.7) 0%, transparent 55%);
}

/* Mobile: full screen (no phone frame) */
@media (max-width: 600px) {
  body { display: block; background: var(--bg) !important; background-image: none !important; }
  .stage { width: 100%; height: 100%; }
  .phone {
    width: 100%; height: 100dvh;
    border-radius: 0;
    box-shadow: none;
  }
  .phone::before, .phone::after { display: none; }
  .di { display: none; }
  .sb { display: none; }
  .viewport { border-radius: 0; }
  .home-indicator { display: none; }
}
</style>
