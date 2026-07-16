<template>
  <label class="block">
    <span v-if="label" class="field-label">
      {{ label }}
      <span v-if="required" class="text-coral">*</span>
    </span>
    <slot />
    <span v-if="hint" class="block mt-1 text-xs text-warm-400 dark:text-warm-500">{{ hint }}</span>
  </label>
</template>

<script setup>
defineProps({
  label: { type: String, default: "" },
  hint: { type: String, default: "" },
  required: { type: Boolean, default: false },
})
</script>
