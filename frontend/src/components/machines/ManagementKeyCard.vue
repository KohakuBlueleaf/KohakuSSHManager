<template>
  <div class="space-y-3">
    <p class="text-sm text-warm-600 dark:text-warm-400 leading-relaxed">
      Install this shared management public key into the management user's
      <code class="mono-chip">~/.ssh/authorized_keys</code> on every machine you register. Kohaku connects with it to read and manage accounts.
    </p>

    <div v-if="loading">
      <LoadingBlock :rows="2" />
    </div>

    <div v-else-if="unavailable" class="text-sm text-amber-shadow dark:text-amber-light">The deployment secret is not configured, so the management key is unavailable (<code class="mono-chip">KSM_SECRET</code> must be set). Configure it and reload.</div>

    <template v-else-if="publicKey">
      <div class="relative">
        <pre class="card p-3 pr-24 text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all bg-warm-50 dark:bg-warm-950">{{ publicKey }}</pre>
        <div class="absolute top-2 right-2">
          <CopyButton :value="publicKey" label="Copy" />
        </div>
      </div>

      <details class="text-sm">
        <summary class="cursor-pointer text-iolite dark:text-iolite-light">Install instructions</summary>
        <ol class="mt-2 space-y-1 text-warm-600 dark:text-warm-400 list-decimal pl-5 text-xs leading-relaxed">
          <li>SSH into the machine as the management user.</li>
          <li>
            Run
            <code class="mono-chip">mkdir -p ~/.ssh &amp;&amp; chmod 700 ~/.ssh</code>.
          </li>
          <li>Append the key above to <code class="mono-chip">~/.ssh/authorized_keys</code>.</li>
          <li>Ensure <code class="mono-chip">chmod 600 ~/.ssh/authorized_keys</code> and passwordless sudo for the management user.</li>
          <li>Return here and enroll the machine to verify the host key.</li>
        </ol>
      </details>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue"

import CopyButton from "@/components/common/CopyButton.vue"
import LoadingBlock from "@/components/common/LoadingBlock.vue"
import { machinesAPI } from "@/utils/api"

const loading = ref(true)
const publicKey = ref("")
const unavailable = ref(false)

onMounted(async () => {
  try {
    const res = await machinesAPI.managementKey()
    publicKey.value = res.public_key
  } catch (err) {
    // 503 = KSM_SECRET missing (mgmt-key ops disabled).
    if (err?.response?.status === 503) unavailable.value = true
  } finally {
    loading.value = false
  }
})
</script>
