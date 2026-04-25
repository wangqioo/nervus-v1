import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Category from '../views/Category.vue'
import Search from '../views/Search.vue'
import FileDetail from '../views/FileDetail.vue'
import DayFiles from '../views/DayFiles.vue'

const routes = [
  { path: '/', name: 'home', component: Home },
  { path: '/category', name: 'category', component: Category },
  { path: '/search', name: 'search', component: Search },
  { path: '/file/:id', name: 'file-detail', component: FileDetail },
  { path: '/day', name: 'day-files', component: DayFiles },
]

export default createRouter({
  history: createWebHistory('/files/'),
  routes,
})
