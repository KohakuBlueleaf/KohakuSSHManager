<template>
  <form class="space-y-3" @submit.prevent="submit">
    <KField label="Machine">
      <KSelect v-model="machineId" :options="machineOptions" placeholder="Select a machine…" />
    </KField>

    <KField label="Target account name" :hint="`Optional. Defaults to your panel name (${defaultUsername || 'your username'}).`">
      <KInput v-model="username" :placeholder="defaultUsername || 'unix username'" />
    </KField>

    <div class="flex justify-end">
      <KButton variant="primary" :loading="loading" :disabled="!machineId" @click="submit"> Request access </KButton>
    </div>
  </form>
</template>

<script setup>
import { ref, computed } from "vue"

import { ElMessage } from "element-plus"

import KButton from "@/components/common/KButton.vue"
import KField from "@/components/common/KField.vue"
import KInput from "@/components/common/KInput.vue"
import KSelect from "@/components/common/KSelect.vue"
import { accessAPI } from "@/utils/api"

const props = defineProps({
  machines: { type: Array, default: () => [] },
  defaultUsername: { type: String, default: "" },
})

const emit = defineEmits(["requested"])

const machineId = ref("")
const username = ref("")
const loading = ref(false)

const machineOptions = computed(() => props.machines.map((m) => ({ value: m.id, label: m.name })))

async function submit() {
  if (!machineId.value) return
  loading.value = true
  try {
    const body = { machine_id: machineId.value }
    if (username.value.trim()) body.username = username.value.trim()
    const req = await accessAPI.createRequest(body)
    const auto = req?.state === "active"
    ElMessage.success(auto ? "Access granted" : "Request submitted for review")
    machineId.value = ""
    username.value = ""
    emit("requested", req)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to submit request")
  } finally {
    loading.value = false
  }
}
</script>
