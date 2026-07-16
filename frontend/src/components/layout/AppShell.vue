<template>
  <div class="h-full flex bg-warm-50 dark:bg-warm-950">
    <NavRail />
    <main class="flex-1 h-full overflow-y-auto">
      <slot />
    </main>
  </div>
</template>

<script setup>
import NavRail from "@/components/layout/NavRail.vue"
</script>
