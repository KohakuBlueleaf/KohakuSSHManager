<template>
  <nav class="w-56 shrink-0 h-full flex flex-col border-r border-warm-200 dark:border-warm-700 bg-warm-100 dark:bg-warm-950">
    <div class="px-4 py-4 flex items-center gap-2">
      <span class="i-carbon-bare-metal-server-01 text-xl text-iolite" />
      <div class="leading-tight">
        <div class="text-sm font-semibold text-warm-800 dark:text-warm-100">Kohaku SSH</div>
        <div class="text-[10px] uppercase tracking-wide text-warm-400 dark:text-warm-500">Access Manager</div>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
      <router-link v-for="item in visibleItems" :key="item.to" :to="item.to" class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors" :class="isActive(item) ? 'bg-warm-200/80 dark:bg-warm-800/60 text-iolite dark:text-iolite-light' : 'text-warm-600 dark:text-warm-400 hover:bg-warm-200/50 dark:hover:bg-warm-800/40'">
        <span :class="item.icon" class="text-lg" />
        {{ item.label }}
      </router-link>
    </div>

    <div class="border-t border-warm-200 dark:border-warm-700 px-3 py-3 space-y-2">
      <button class="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm text-warm-600 dark:text-warm-400 hover:bg-warm-200/50 dark:hover:bg-warm-800/40 transition-colors" @click="theme.toggle()">
        <span :class="theme.dark ? 'i-carbon-sun' : 'i-carbon-moon'" class="text-lg" />
        {{ theme.dark ? "Light mode" : "Dark mode" }}
      </button>

      <div class="flex items-center gap-2 px-2 py-1">
        <span class="i-carbon-user-avatar text-xl text-warm-400" />
        <div class="min-w-0 flex-1">
          <div class="text-sm font-medium text-warm-800 dark:text-warm-200 truncate">
            {{ auth.displayName }}
          </div>
          <div class="text-[10px] uppercase tracking-wide text-warm-400 dark:text-warm-500">
            {{ auth.role }}
          </div>
        </div>
      </div>

      <button class="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm text-warm-600 dark:text-warm-400 hover:bg-coral-light hover:text-coral-shadow dark:hover:bg-coral-shadow/30 transition-colors" @click="onLogout">
        <span class="i-carbon-logout text-lg" />
        Sign out
      </button>
    </div>
  </nav>
</template>

<script setup>
import { computed } from "vue"
import { useRoute, useRouter } from "vue-router"

import { useAuthStore } from "@/stores/auth"
import { useThemeStore } from "@/stores/theme"

const auth = useAuthStore()
const theme = useThemeStore()
const route = useRoute()
const router = useRouter()

// role: "member" sees Dashboard + Machines; "leader" adds Requests;
// "admin" (the __token__ principal) sees everything.
const items = [
  { to: "/", label: "Dashboard", icon: "i-carbon-dashboard", show: () => true },
  { to: "/machines", label: "Machines", icon: "i-carbon-bare-metal-server", show: () => true },
  {
    to: "/requests",
    label: "Requests",
    icon: "i-carbon-task-approved",
    show: () => auth.isLeader,
  },
  { to: "/users", label: "Users", icon: "i-carbon-user-multiple", show: () => auth.isAdmin },
  { to: "/groups", label: "Groups", icon: "i-carbon-group", show: () => auth.isAdmin },
  { to: "/storage", label: "Storage", icon: "i-carbon-datastore", show: () => auth.isAdmin },
  { to: "/audit", label: "Audit", icon: "i-carbon-catalog", show: () => auth.isAdmin },
  { to: "/settings", label: "Settings", icon: "i-carbon-settings", show: () => !auth.isAdmin },
]

const visibleItems = computed(() => items.filter((i) => i.show()))

function isActive(item) {
  if (item.to === "/") return route.path === "/"
  return route.path === item.to || route.path.startsWith(item.to + "/")
}

async function onLogout() {
  await auth.logout()
  router.push("/login")
}
</script>
