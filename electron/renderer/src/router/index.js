import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Settings from '../views/Settings.vue'
import Prompts from '../views/Prompts.vue'
import KnowledgeBase from '../views/KnowledgeBase.vue'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/settings', component: Settings },
  { path: '/prompts', component: Prompts },
  { path: '/knowledge', component: KnowledgeBase },
]

export default createRouter({
  history: createWebHashHistory(),
  routes,
})
