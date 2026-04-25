<template>
  <div class="chat-wrap">
    <div class="msgs" ref="msgEl">
      <div v-if="!messages.length" class="chat-empty">
        <div class="ai-av">🤖</div>
        <p v-if="date">搜索 {{ date }} 的文件</p>
        <p v-else>有什么文件需要找？</p>
      </div>
      <div v-for="(msg, i) in messages" :key="i" class="msg" :class="msg.role">
        <div v-if="msg.role === 'ai'" class="msg-av">🤖</div>
        <div class="msg-body">
          <div class="bubble" :class="msg.role">
            {{ msg.display }}
            <span v-if="msg.typing" class="cursor">|</span>
          </div>
          <div v-if="!msg.typing && msg.results?.length" class="results-list">
            <div v-for="r in msg.results" :key="r.id" class="result-card gc" @click="$emit('open-file', r.id)">
              <span class="r-icon">{{ typeIcon(r.type) }}</span>
              <div class="r-info">
                <div class="r-name">{{ r.original_filename }}</div>
                <div class="r-reason">{{ r.match_reason }}</div>
              </div>
              <div class="r-score">{{ scoreStars(r.match_score) }}</div>
            </div>
          </div>
        </div>
      </div>
      <div v-if="loading" class="msg ai">
        <div class="msg-av">🤖</div>
        <div class="bubble ai typing">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>

    <div class="chat-bar">
      <input
        v-model="input"
        class="chat-inp"
        :placeholder="date ? `搜索 ${date} 的文件...` : '搜索你的文件...'"
        @keydown.enter="send"
        :disabled="loading"
      />
      <button class="send-btn" @click="send" :disabled="!input.trim() || loading">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { searchFiles } from '../api/files'

const props = defineProps({
  date: { type: String, default: '' },
  fileType: { type: String, default: '' },
  initialQ: { type: String, default: '' },
})
defineEmits(['open-file'])

onMounted(() => {
  if (props.initialQ) { input.value = props.initialQ; send() }
})

const input = ref('')
const messages = ref([])
const loading = ref(false)
const msgEl = ref(null)

const TYPE_ICONS = { image:'🖼', video:'🎬', document:'📄', audio:'🎵', link:'🔗', other:'📦' }
const typeIcon = t => TYPE_ICONS[t] || '📦'

function scoreStars(score) {
  const s = Math.round((score || 0) * 5)
  return '★'.repeat(s) + '☆'.repeat(5 - s)
}

async function typewrite(msg, fullText) {
  msg.display = ''
  msg.typing = true
  const delay = Math.max(18, Math.min(40, 1200 / fullText.length))
  for (let i = 0; i <= fullText.length; i++) {
    msg.display = fullText.slice(0, i)
    await new Promise(r => setTimeout(r, delay))
    await scrollBottom()
  }
  msg.typing = false
}

function pick(arr) { return arr[Math.floor(Math.random() * arr.length)] }

function replyText(results) {
  const n = results.length
  if (n === 0) return pick([
    '翻遍了也没找到诶… 换个关键词试试？🔍',
    '没有找到完全匹配的，要不换个说法描述一下？',
    '暂时没有结果，可以告诉我更多细节，我再帮你找找~',
    '这次没找到，再给我一些线索？比如文件类型或者大概内容~',
    '嗯… 没有结果。你确定存过这个吗？哈哈，再试试别的词？',
    '找不到呢，不过没关系，换个角度描述一下，我再试试 💪',
  ])
  if (n === 1) return pick([
    '就找到这一个，感觉挺像你要的，看看吧 👇',
    '精准匹配！应该就是它了~',
    '只有一个结果，但我觉得八九不离十 ✨',
    '找到一个，命中率应该很高，看看对不对？',
    '就这一个，但感觉很准，你瞧 👇',
  ])
  if (n <= 3) return pick([
    `为你找到 ${n} 个，可能就是你想要的哦 👇`,
    `找到啦！下面这些应该是你要找的~`,
    `在库里翻到了 ${n} 个相关的，看看对不对？`,
    `给你找到 ${n} 个，感觉都挺相关的，选一下吧~`,
    `搜到 ${n} 个结果，应该有你要的 🎉`,
  ])
  // n > 3
  return pick([
    `找到 ${n} 个相关文件，有点多 😄 可以继续描述更多信息，我帮你缩小范围~`,
    `结果有 ${n} 个，如果不是你要的，告诉我更多细节，我再帮你找 🎯`,
    `为你找到下面这些，可能有你想要的！如果太多了，可以继续描述一下~`,
    `哇找到 ${n} 个，挺丰富的！如果觉得太多，可以加一些限定词让我帮你筛 🔎`,
    `翻出来 ${n} 个，仔细看看，如果不对就再告诉我更多信息~`,
    `${n} 个结果！如果下面文件有点多，可以继续描述更多的信息，我帮你找 💡`,
  ])
}

async function send() {
  const q = input.value.trim()
  if (!q || loading.value) return
  messages.value.push({ role: 'user', text: q, display: q, typing: false })
  input.value = ''
  loading.value = true
  await scrollBottom()
  try {
    const data = await searchFiles(q, props.date, props.fileType)
    const results = data.results || []
    const fullText = replyText(results)
    messages.value.push({ role: 'ai', text: fullText, display: '', typing: false, results })
    const msg = messages.value[messages.value.length - 1]
    loading.value = false
    await scrollBottom()
    await typewrite(msg, fullText)
  } catch {
    const errText = pick([
      '出了点小问题，稍后再试试？🙏',
      '搜索好像出了点故障，再试一次吧~',
    ])
    messages.value.push({ role: 'ai', text: errText, display: '', typing: false, results: [] })
    const msg = messages.value[messages.value.length - 1]
    loading.value = false
    await typewrite(msg, errText)
  }
}

async function scrollBottom() {
  await nextTick()
  if (msgEl.value) msgEl.value.scrollTop = msgEl.value.scrollHeight
}
</script>

<style scoped>
.chat-wrap { display: flex; flex-direction: column; height: 100%; background: var(--bg); }

.msgs {
  flex: 1; overflow-y: auto;
  padding: 16px 16px 8px;
  display: flex; flex-direction: column; gap: 14px;
}

.chat-empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 10px; padding: 40px 0;
  color: var(--text3); font-size: 13px;
}
.chat-empty .ai-av {
  width: 44px; height: 44px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--teal));
  display: flex; align-items: center; justify-content: center; font-size: 20px;
  box-shadow: 0 0 16px var(--accent-g);
}

.msg { display: flex; gap: 8px; align-items: flex-start; }
.msg.user { flex-direction: row-reverse; }

.msg-av {
  width: 30px; height: 30px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--teal));
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; flex-shrink: 0;
  box-shadow: 0 0 10px var(--accent-g);
}

.msg-body { max-width: 82%; display: flex; flex-direction: column; gap: 6px; }

.bubble {
  padding: 9px 13px; border-radius: 18px;
  font-size: 13px; line-height: 1.55; color: var(--text);
}
.bubble.ai {
  background: var(--s3); border: 1px solid var(--border);
  border-bottom-left-radius: 5px;
}
.bubble.user {
  background: linear-gradient(135deg, var(--accent), #6B52F0);
  color: #fff; border-bottom-right-radius: 5px;
}

.cursor {
  display: inline-block; color: var(--accent); font-weight: 300;
  animation: blink-cur .6s step-end infinite;
}
@keyframes blink-cur { 0%,100%{opacity:1} 50%{opacity:0} }

.typing { display: flex; align-items: center; gap: 4px; min-height: 20px; }
.typing span {
  width: 6px; height: 6px;
  background: var(--text3); border-radius: 50%;
  animation: bounce 1.3s infinite;
}
.typing span:nth-child(2) { animation-delay: .18s; }
.typing span:nth-child(3) { animation-delay: .36s; }
@keyframes bounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-5px)} }

.results-list { display: flex; flex-direction: column; gap: 6px; }

.result-card {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 11px; border-radius: 14px;
  cursor: pointer;
  transition: transform .15s cubic-bezier(.32,.72,0,1), background .15s;
}
.result-card:active { transform: scale(.97); background: var(--s3); }

.r-icon { font-size: 20px; flex-shrink: 0; }
.r-info { flex: 1; min-width: 0; }
.r-name {
  font-size: 12px; font-weight: 600; color: var(--text);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.r-reason { font-size: 11px; color: var(--text3); margin-top: 2px; }
.r-score { font-size: 11px; color: var(--orange); flex-shrink: 0; }

.chat-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px 16px;
  background: var(--bg-blur); backdrop-filter: blur(20px);
  border-top: 1px solid var(--border);
}

.chat-inp {
  flex: 1; height: 40px;
  background: var(--s2); border: 1px solid var(--border);
  border-radius: 20px; padding: 0 16px;
  color: var(--text); font-size: 13px; font-family: inherit;
  outline: none; transition: border-color .2s;
}
.chat-inp:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-s); }
.chat-inp::placeholder { color: var(--text3); }

.send-btn {
  width: 38px; height: 38px; border-radius: 50%;
  background: var(--accent); border: none; color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0;
  box-shadow: 0 0 14px var(--accent-g);
  transition: transform .15s, box-shadow .15s;
}
.send-btn:not(:disabled):active { transform: scale(.9); }
.send-btn:disabled { background: var(--s3); box-shadow: none; cursor: not-allowed; }
</style>
