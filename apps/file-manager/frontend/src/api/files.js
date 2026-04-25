import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export async function uploadFile(file, analyzeNow = false) {
  const form = new FormData()
  form.append('file', file)
  form.append('analyze_now', analyzeNow ? 'true' : 'false')
  const { data } = await api.post('/files/upload', form)
  return data
}

export async function uploadLink(url, analyzeNow = false) {
  const form = new FormData()
  form.append('url', url)
  form.append('analyze_now', analyzeNow ? 'true' : 'false')
  const { data } = await api.post('/files/upload', form)
  return data
}

export async function uploadText(text) {
  const form = new FormData()
  form.append('text', text)
  const { data } = await api.post('/files/upload', form)
  return data
}

export async function getFiles(params = {}) {
  const { data } = await api.get('/files', { params })
  return data
}

export async function getFile(id) {
  const { data } = await api.get(`/files/${id}`)
  return data
}

export async function deleteFile(id) {
  const { data } = await api.delete(`/files/${id}`)
  return data
}

export async function analyzeFile(id) {
  const { data } = await api.post(`/files/${id}/analyze`)
  return data
}

export async function extractContent(id) {
  const { data } = await api.get(`/files/${id}/extract`)
  return data
}

export async function searchFiles(q, date = '', type = '') {
  const params = { q }
  if (date) params.date = date
  if (type) params.type = type
  const { data } = await api.get('/files/search', { params })
  return data
}

export async function getStats() {
  const { data } = await api.get('/files/stats')
  return data
}

export async function getFilesByDate(date) {
  const { data } = await api.get(`/files/by-date/${date}`)
  return data
}

export function downloadUrl(id) {
  return `/api/files/${id}/download`
}

// Proxy WeChat CDN images through backend to bypass hotlink protection
export function imgUrl(url) {
  if (!url) return ''
  if (url.startsWith('/api/')) return url
  const needsProxy = ['qpic.cn', 'mmbiz', 'weixin'].some(k => url.includes(k))
  return needsProxy ? `/api/image-proxy?url=${encodeURIComponent(url)}` : url
}
