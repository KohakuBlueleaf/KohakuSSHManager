<template>
  <div class="flex flex-col items-center justify-center text-center py-10 px-4">
    <span :class="icon" class="text-3xl text-warm-300 dark:text-warm-600 mb-2" />
    <p class="text-sm text-warm-500 dark:text-warm-400">{{ text }}</p>
    <p v-if="hint" class="text-xs text-warm-400 dark:text-warm-500 mt-1">{{ hint }}</p>
    <div v-if="$slots.action" class="mt-3">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  icon: { type: String, default: "i-carbon-tree-view-alt" },
  text: { type: String, default: "Nothing here yet" },
  hint: { type: String, default: "" },
})
</script>
