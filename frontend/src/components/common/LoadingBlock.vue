<template>
  <div class="space-y-2 animate-pulse" :aria-busy="true">
    <div v-for="n in rows" :key="n" class="h-9 rounded-lg bg-warm-100 dark:bg-warm-800/60" :style="{ width: widths[n % widths.length] }" />
  </div>
</template>

<script setup>
defineProps({
  rows: { type: Number, default: 3 },
})

const widths = ["100%", "92%", "96%", "88%"]
</script>
