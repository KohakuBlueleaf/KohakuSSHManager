<template>
  <button :class="variantClass" :disabled="disabled || loading" @click="$emit('click', $event)">
    <span v-if="loading" class="i-carbon-circle-dash inline-block animate-spin mr-1" />
    <span v-else-if="icon" :class="icon" class="mr-1" />
    <slot />
  </button>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
  variant: { type: String, default: "primary" }, // primary | secondary | danger | ghost
  icon: { type: String, default: "" },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

defineEmits(["click"])

const variantClass = computed(() => {
  switch (props.variant) {
    case "secondary":
      return "btn-secondary"
    case "danger":
      return "btn-danger"
    case "ghost":
      return "btn-ghost"
    default:
      return "btn-primary"
  }
})
</script>
