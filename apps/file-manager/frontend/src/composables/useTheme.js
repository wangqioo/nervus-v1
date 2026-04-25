import { ref, watch } from 'vue'

const stored = localStorage.getItem('theme')
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
const theme = ref(stored || (prefersDark ? 'dark' : 'light'))

function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t)
  localStorage.setItem('theme', t)
}

applyTheme(theme.value)
watch(theme, applyTheme)

export function useTheme() {
  function toggle() { theme.value = theme.value === 'dark' ? 'light' : 'dark' }
  return { theme, toggle }
}
