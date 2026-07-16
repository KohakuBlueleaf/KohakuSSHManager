import { createApp } from "vue"
import { createPinia } from "pinia"
import { createRouter, createWebHistory } from "vue-router"
import { routes } from "vue-router/auto-routes"
import App from "./App.vue"

import { useAuthStore } from "@/stores/auth"
import { useThemeStore } from "@/stores/theme"

import "element-plus/es/components/message/style/css"
import "element-plus/es/components/message-box/style/css"
import "uno.css"
import "./style.css"

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Route guard — the auth store fetches /api/auth/me once on boot (below).
// Any route other than /login needs an authenticated session; a missing
// one bounces to the login page. A logged-in user hitting /login is sent
// home so the form never shows to someone already in.
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!auth.isAuthenticated && to.path !== "/login") {
    return { path: "/login", query: to.path === "/" ? {} : { redirect: to.fullPath } }
  }
  if (auth.isAuthenticated && to.path === "/login") {
    return { path: "/" }
  }
  return undefined
})

async function bootstrap() {
  const pinia = createPinia()
  const app = createApp(App)

  app.use(pinia)
  app.use(router)

  // Theme before mount so first paint matches the persisted preference.
  useThemeStore().init()

  // Resolve the session before the first navigation so the guard has a
  // real answer. A failed /me (401) simply leaves me == null.
  await useAuthStore().fetchMe()

  app.mount("#app")
}

bootstrap()
