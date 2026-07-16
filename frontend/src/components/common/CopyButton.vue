<template>
  <button class="btn-ghost inline-flex items-center gap-1" :title="copied ? 'Copied' : 'Copy'" @click="copy">
    <span :class="copied ? 'i-carbon-checkmark text-aquamarine' : 'i-carbon-copy'" />
    <span v-if="label">{{ copied ? "Copied" : label }}</span>
  </button>
</template>

<script setup>
import { ref } from "vue"

import { ElMessage } from "element-plus"

const props = defineProps({
  value: { type: String, default: "" },
  label: { type: String, default: "" },
})

const copied = ref(false)

async function copy() {
  try {
    await navigator.clipboard.writeText(props.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    ElMessage.error("Copy failed — select and copy manually")
  }
}
</script>
