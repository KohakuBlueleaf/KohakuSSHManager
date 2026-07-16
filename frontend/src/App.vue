<template>
  <div class="h-full">
    <!-- The login page renders standalone; every other route lives inside
         the authenticated shell (nav rail + scrollable main). -->
    <router-view v-if="isBare" />
    <AppShell v-else>
      <router-view />
    </AppShell>
  </div>
</template>

<script setup>
import { computed } from "vue"
import { useRoute } from "vue-router"

import AppShell from "@/components/layout/AppShell.vue"

const route = useRoute()
const isBare = computed(() => route.path === "/login")
</script>
