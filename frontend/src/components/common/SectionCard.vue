<template>
  <section class="card p-4 sm:p-5">
    <header v-if="title || $slots.actions" class="flex items-start justify-between gap-3 mb-4">
      <div>
        <h2 class="text-base font-semibold text-warm-800 dark:text-warm-100 flex items-center gap-2">
          <span v-if="icon" :class="icon" class="text-iolite" />
          {{ title }}
        </h2>
        <p v-if="subtitle" class="text-xs text-warm-500 dark:text-warm-400 mt-0.5">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.actions" class="flex items-center gap-2 flex-shrink-0">
        <slot name="actions" />
      </div>
    </header>
    <slot />
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, default: "" },
  subtitle: { type: String, default: "" },
  icon: { type: String, default: "" },
})
</script>
