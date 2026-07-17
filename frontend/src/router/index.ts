import { createRouter, createWebHistory } from 'vue-router'
import ReviewView from '../views/ReviewView.vue'
import ImportView from '../views/ImportView.vue'
import LibraryView from '../views/LibraryView.vue'
import StatsView from '../views/StatsView.vue'
import DecksView from '../views/DecksView.vue'
import LoginView from '../views/LoginView.vue'
import SourceDetailView from '../views/SourceDetailView.vue'
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login',   name: 'login',   component: LoginView },
    { path: '/',        name: 'review',  component: ReviewView },
    { path: '/import',  name: 'import',  component: ImportView },
    { path: '/decks',   name: 'decks',   component: DecksView },
    { path: '/library', name: 'library', component: LibraryView },
    { path: '/stats',   name: 'stats',   component: StatsView },
    { path: '/sources/:id', name: 'source-detail', component: SourceDetailView },
    { path: '/settings', name: 'settings', component: SettingsView },
  ],
})

export default router
