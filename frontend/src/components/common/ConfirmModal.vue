<template>
  <el-dialog :model-value="open" :title="title" :width="width" align-center append-to-body :close-on-click-modal="!loading" @update:model-value="$emit('update:open', $event)" @closed="$emit('cancel')">
    <div class="space-y-3">
      <p v-if="message" class="text-sm text-warm-700 dark:text-warm-300 leading-relaxed whitespace-pre-line">
        {{ message }}
      </p>

      <slot />

      <KField v-if="confirmWord" :label="`Type “${confirmWord}” to confirm`">
        <KInput v-model="typed" :placeholder="confirmWord" />
      </KField>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <KButton variant="secondary" :disabled="loading" @click="close">{{ cancelText }}</KButton>
        <KButton :variant="variant" :loading="loading" :disabled="!confirmable" @click="$emit('confirm')">
          {{ confirmText }}
        </KButton>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from "vue"

import KButton from "@/components/common/KButton.vue"
import KField from "@/components/common/KField.vue"
import KInput from "@/components/common/KInput.vue"

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "Confirm" },
  message: { type: String, default: "" },
  confirmText: { type: String, default: "Confirm" },
  cancelText: { type: String, default: "Cancel" },
  variant: { type: String, default: "danger" },
  // When set, the confirm button stays disabled until the user types this
  // exact string (used for the typed-username account-delete guard).
  confirmWord: { type: String, default: "" },
  width: { type: String, default: "480px" },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(["update:open", "confirm", "cancel"])

const typed = ref("")

// Reset the typed guard each time the dialog opens so a stale match can't
// carry over from a previous target.
watch(
  () => props.open,
  (v) => {
    if (v) typed.value = ""
  },
)

const confirmable = computed(() => !props.confirmWord || typed.value === props.confirmWord)

function close() {
  emit("update:open", false)
  emit("cancel")
}
</script>
