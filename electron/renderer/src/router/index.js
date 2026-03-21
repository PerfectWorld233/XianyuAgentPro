import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Settings from '../views/Settings.vue'
import Prompts from '../views/Prompts.vue'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/settings', component: Settings },
  { path: '/prompts', component: Prompts },
]

export default createRouter({
  history: createWebHashHistory(),
  routes,
})
