<template>
  <div class="h-full flex items-center justify-center bg-warm-50 dark:bg-warm-950 px-4">
    <div class="w-full max-w-sm">
      <div class="flex items-center justify-center gap-2 mb-6">
        <span class="i-carbon-bare-metal-server-01 text-3xl text-iolite" />
        <div class="leading-tight">
          <div class="text-lg font-semibold text-warm-800 dark:text-warm-100">Kohaku SSH</div>
          <div class="text-xs uppercase tracking-wide text-warm-400 dark:text-warm-500">Access Manager</div>
        </div>
      </div>

      <form class="card p-6 space-y-4" @submit.prevent="submit">
        <h1 class="text-base font-semibold text-warm-800 dark:text-warm-100">Sign in</h1>

        <KField label="Username">
          <KInput v-model="username" placeholder="username" autocomplete="username" />
        </KField>

        <KField label="Password">
          <KInput v-model="password" type="password" placeholder="password" autocomplete="current-password" @enter="submit" />
        </KField>

        <KButton variant="primary" :loading="loading" class="w-full" @click="submit"> Sign in </KButton>

        <p class="text-xs text-warm-400 dark:text-warm-500 leading-relaxed">
          Administrators sign in with username
          <code class="mono-chip">__token__</code>
          and the deployment admin token as the password.
        </p>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { ElMessage } from "element-plus"

import KButton from "@/components/common/KButton.vue"
import KField from "@/components/common/KField.vue"
import KInput from "@/components/common/KInput.vue"
import { useAuthStore } from "@/stores/auth"

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const username = ref("")
const password = ref("")
const loading = ref(false)

async function submit() {
  if (!username.value || !password.value) {
    ElMessage.warning("Enter a username and password")
    return
  }
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    ElMessage.success(`Welcome, ${auth.displayName}`)
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/"
    router.push(redirect)
  } catch (err) {
    const detail = err?.response?.data?.detail
    ElMessage.error(detail || "Sign in failed — check your credentials")
  } finally {
    loading.value = false
  }
}
</script>
