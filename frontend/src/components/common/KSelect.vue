<template>
  <select :value="modelValue" :disabled="disabled" class="input-field appearance-none pr-8 cursor-pointer" @change="$emit('update:modelValue', normalize($event.target.value))">
    <option v-if="placeholder" value="">{{ placeholder }}</option>
    <option v-for="opt in normalized" :key="String(opt.value)" :value="opt.value">
      {{ opt.label }}
    </option>
  </select>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
  modelValue: { type: [String, Number], default: "" },
  // Accepts ["a", "b"] or [{ value, label }].
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
})

defineEmits(["update:modelValue"])

const normalized = computed(() => props.options.map((o) => (typeof o === "object" && o !== null ? { value: o.value, label: o.label ?? String(o.value) } : { value: o, label: String(o) })))

// Preserve numeric option values through the native string event.
function normalize(raw) {
  const match = normalized.value.find((o) => String(o.value) === raw)
  return match ? match.value : raw
}
</script>
