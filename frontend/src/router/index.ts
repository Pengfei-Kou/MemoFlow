import { createRouter, createWebHistory } from 'vue-router'
import ReviewView from '../views/ReviewView.vue'
import ImportView from '../views/ImportView.vue'
import LibraryView from '../views/LibraryView.vue'
import StatsView from '../views/StatsView.vue'
import DecksView from '../views/DecksView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',        name: 'review',  component: ReviewView },
    { path: '/import',  name: 'import',  component: ImportView },
    { path: '/decks',   name: 'decks',   component: DecksView },
    { path: '/library', name: 'library', component: LibraryView },
    { path: '/stats',   name: 'stats',   component: StatsView },
  ],
})

export default router
