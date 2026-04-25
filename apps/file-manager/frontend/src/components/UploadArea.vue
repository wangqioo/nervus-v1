<template>
  <div
    class="upload-zone"
    :class="{ dragging, uploading }"
    @dragover.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="handleDrop"
  >
    <template v-if="uploading">
      <div class="up-progress">
        <div class="up-bar"><div class="up-fill" :style="{ width: progress + '%' }"></div></div>
        <span class="up-text">{{ statusText }}</span>
      </div>
    </template>
    <template v-else>
      <label class="up-label">
        <span class="up-icon">📎</span>
        <span class="up-hint">拖拽 / 点击上传</span>
        <input type="file" multiple @change="handleInput" style="display:none" />
      </label>
    </template>
    <div v-if="error" class="up-error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { uploadFile } from '../api/files'

const emit = defineEmits(['uploaded'])
const dragging = ref(false)
const uploading = ref(false)
const progress = ref(0)
const statusText = ref('')
const error = ref('')

async function handleDrop(e) {
  dragging.value = false
  const files = [...e.dataTransfer.files]
  if (files.length) await doUpload(files)
}
async function handleInput(e) {
  const files = [...e.target.files]
  if (files.length) await doUpload(files)
  e.target.value = ''
}

async function doUpload(files) {
  uploading.value = true
  error.value = ''
  const total = files.length
  let done = 0
  for (const f of files) {
    try {
      statusText.value = f.name
      progress.value = Math.round((done / total) * 80)
      const result = await uploadFile(f)
      done++
      progress.value = Math.round((done / total) * 100)
      emit('uploaded', result)
    } catch (e) {
      error.value = `上传失败: ${e.response?.data?.detail || e.message}`
    }
  }
  setTimeout(() => { uploading.value = false; progress.value = 0 }, 700)
}

defineExpose({ doUpload })
</script>

<style scoped>
.upload-zone {
  border: 1.5px dashed var(--border2);
  border-radius: var(--radius);
  padding: 14px 20px;
  display: flex; align-items: center; justify-content: center;
  flex-direction: column; gap: 6px;
  background: var(--s1);
  transition: border-color .2s, background .2s;
  min-height: 60px;
}
.upload-zone.dragging { border-color: var(--accent); background: var(--accent-s); }
.upload-zone.uploading { border-style: solid; border-color: var(--accent); }

.up-label {
  display: flex; align-items: center; gap: 8px;
  cursor: pointer; color: var(--text2); font-size: 13px;
}
.up-icon { font-size: 18px; }

.up-progress { width: 100%; display: flex; flex-direction: column; gap: 6px; }
.up-bar { height: 3px; background: var(--s3); border-radius: 2px; overflow: hidden; }
.up-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--teal)); transition: width .3s; }
.up-text { font-size: 11px; color: var(--text3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.up-error { font-size: 11px; color: var(--red); text-align: center; }
</style>
