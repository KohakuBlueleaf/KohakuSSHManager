<template>
  <div class="space-y-3">
    <div v-if="machine.enrolled" class="space-y-2">
      <div class="flex items-center gap-2">
        <StatusBadge state="ok" label="enrolled" />
        <span class="text-sm text-warm-600 dark:text-warm-400">Host key verified.</span>
      </div>
      <div>
        <div class="field-label">Verified host-key fingerprint</div>
        <code class="mono-chip break-all">{{ machine.host_key_fingerprint || "—" }}</code>
      </div>
    </div>

    <div v-else class="space-y-3">
      <p class="text-sm text-warm-600 dark:text-warm-400 leading-relaxed">Install the shared management key on this machine, then probe its host key. The presented fingerprint must be confirmed once before Kohaku will trust and manage the machine.</p>

      <KButton v-if="!probed" variant="primary" :loading="probing" @click="probe"> Probe host key </KButton>

      <div v-else class="space-y-3">
        <div>
          <div class="field-label">Presented host-key fingerprint</div>
          <code class="mono-chip break-all">{{ probed }}</code>
        </div>
        <p class="text-xs text-warm-500 dark:text-warm-400">Verify this fingerprint out-of-band (e.g. <code class="mono-chip">ssh-keyscan</code> on the machine) before confirming. Confirming records it as the trusted key and runs the first refresh.</p>
        <div class="flex gap-2">
          <KButton variant="primary" :loading="confirming" @click="confirm"> Confirm &amp; enroll </KButton>
          <KButton variant="secondary" :disabled="confirming" @click="reset">Cancel</KButton>
        </div>
      </div>

      <p v-if="error" class="text-sm text-coral-shadow dark:text-coral-light">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue"

import { ElMessage } from "element-plus"

import KButton from "@/components/common/KButton.vue"
import StatusBadge from "@/components/common/StatusBadge.vue"
import { machinesAPI } from "@/utils/api"

const props = defineProps({
  machine: { type: Object, required: true },
})

const emit = defineEmits(["done"])

const probing = ref(false)
const confirming = ref(false)
const probed = ref("")
const error = ref("")

async function probe() {
  probing.value = true
  error.value = ""
  try {
    const res = await machinesAPI.enroll(props.machine.id)
    probed.value = res.host_key_fingerprint
  } catch (err) {
    error.value = err?.response?.data?.detail || "Failed to reach the machine"
  } finally {
    probing.value = false
  }
}

async function confirm() {
  confirming.value = true
  error.value = ""
  try {
    await machinesAPI.enrollConfirm(props.machine.id, probed.value)
    ElMessage.success("Machine enrolled")
    reset()
    emit("done")
  } catch (err) {
    // 409 = the fingerprint changed between probe and confirm (mismatch).
    error.value = err?.response?.status === 409 ? err?.response?.data?.detail || "Host-key mismatch — the presented key changed. Not enrolled." : err?.response?.data?.detail || "Enrollment failed"
  } finally {
    confirming.value = false
  }
}

function reset() {
  probed.value = ""
  error.value = ""
}
</script>
