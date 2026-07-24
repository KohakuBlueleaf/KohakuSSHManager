<template>
  <form class="space-y-3" @submit.prevent="submit">
    <KField label="Public key" hint="One OpenSSH public key line (ssh-ed25519, ssh-rsa, ecdsa-…).">
      <KInput v-model="publicKey" type="textarea" :rows="3" placeholder="ssh-ed25519 AAAA… comment" />
    </KField>

    <KField label="Comment" hint="Optional label to help you recognize this key.">
      <KInput v-model="comment" placeholder="e.g. laptop-2026" />
    </KField>

    <label v-if="showInstall" class="flex items-center gap-2 text-sm text-warm-700 dark:text-warm-300 cursor-pointer">
      <input v-model="install" type="checkbox" class="accent-iolite" />
      {{ userId != null ? "Install to this user's active machine accounts now" : "Install to my active machine accounts now" }}
    </label>

    <div class="flex justify-end">
      <KButton variant="primary" :loading="loading" :disabled="!publicKey.trim()" @click="submit"> Add key </KButton>
    </div>
  </form>
</template>

<script setup>
import { ref } from "vue"

import { ElMessage } from "element-plus"

import KButton from "@/components/common/KButton.vue"
import KField from "@/components/common/KField.vue"
import KInput from "@/components/common/KInput.vue"
import { keysAPI } from "@/utils/api"

const props = defineProps({
  // When set (admin adding for a specific user), included as user_id.
  userId: { type: Number, default: null },
  showInstall: { type: Boolean, default: true },
})

const emit = defineEmits(["added"])

const publicKey = ref("")
const comment = ref("")
// Default ON: a key that never lands on any machine is the surprising case.
const install = ref(true)
const loading = ref(false)

async function submit() {
  if (!publicKey.value.trim()) return
  loading.value = true
  try {
    const body = { public_key: publicKey.value.trim() }
    if (comment.value.trim()) body.comment = comment.value.trim()
    if (props.showInstall) body.install = install.value
    if (props.userId != null) body.user_id = props.userId
    const created = await keysAPI.create(body)
    ElMessage.success("Key added")
    publicKey.value = ""
    comment.value = ""
    install.value = true
    emit("added", created)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to add key")
  } finally {
    loading.value = false
  }
}
</script>
