<template>
  <form class="space-y-3" @submit.prevent="submit">
    <KField label="Machine">
      <KSelect v-model="machineId" :options="machineOptions" placeholder="Select a machine…" />
    </KField>

    <KField v-if="accountEditable" label="Target account name" hint="Optional. The Unix account to grant access to.">
      <KInput v-model="username" :placeholder="defaultUsername || 'unix username'" />
    </KField>

    <KField v-else label="Target account name" hint="The Unix account you will be granted access to. Change it in Settings → Default machine account.">
      <div class="input-field flex items-center bg-warm-100/60 dark:bg-warm-800/40 text-warm-600 dark:text-warm-300 font-mono cursor-not-allowed">
        {{ defaultUsername || "your username" }}
      </div>
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
  // Non-admins can only request under their configured default account, so the
  // target is read-only for them (edited via Settings). Admins may type one.
  accountEditable: { type: Boolean, default: false },
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
