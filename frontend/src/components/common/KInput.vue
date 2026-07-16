<template>
  <input v-if="type !== 'textarea'" :type="type" :value="modelValue" :placeholder="placeholder" :disabled="disabled" :autocomplete="autocomplete" class="input-field" @input="$emit('update:modelValue', $event.target.value)" @keyup.enter="$emit('enter')" />
  <textarea v-else :value="modelValue" :placeholder="placeholder" :disabled="disabled" :rows="rows" class="input-field font-mono resize-y" @input="$emit('update:modelValue', $event.target.value)" />
</template>

<script setup>
defineProps({
  modelValue: { type: [String, Number], default: "" },
  type: { type: String, default: "text" },
  placeholder: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
  autocomplete: { type: String, default: "off" },
  rows: { type: Number, default: 3 },
})

defineEmits(["update:modelValue", "enter"])
</script>
