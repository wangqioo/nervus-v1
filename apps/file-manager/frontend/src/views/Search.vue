<template>
  <div class="page">
    <div class="search-bg"></div>
    <header class="app-hdr">
      <button class="app-back" @click="$router.back()">‹</button>
      <div class="hdr-body">
        <span class="app-hdr-ttl">AI 语义搜索</span>
        <span v-if="date" class="hdr-date">{{ date }}</span>
        <span v-if="typeLabel" class="hdr-date" style="background:var(--s2)">{{ typeLabel }}</span>
      </div>
      <span style="width:32px"></span>
    </header>
    <div class="chat-container">
      <ChatBox :date="date" :file-type="fileType" :initial-q="initialQ" @open-file="id => $router.push(`/file/${id}`)" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import ChatBox from '../components/ChatBox.vue'

const route = useRoute()
const date = computed(() => route.query.date || '')
const fileType = computed(() => route.query.type || '')
const initialQ = computed(() => route.query.q || '')

const TYPE_LABELS = { image:'图片', video:'视频', document:'文档', audio:'音频', link:'链接', other:'其他' }
const typeLabel = computed(() => TYPE_LABELS[fileType.value] || '')
</script>

<style scoped>
.page { display: flex; flex-direction: column; height: 100%; background: var(--bg); }
.search-bg {
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
.hdr-body { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.app-hdr-ttl { font-size: 17px; font-weight: 700; color: var(--text); }
.hdr-date {
  font-size: 11px; color: var(--accent); font-weight: 500;
  background: var(--accent-s); border: 1px solid rgba(139,114,255,.2);
  border-radius: 6px; padding: 1px 7px; align-self: flex-start;
}
.chat-container { flex: 1; overflow: hidden; display: flex; flex-direction: column; position: relative; z-index: 1; }
</style>
