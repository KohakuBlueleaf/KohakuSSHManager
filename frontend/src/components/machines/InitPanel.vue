<template>
  <div class="space-y-4">
    <p class="text-sm text-warm-600 dark:text-warm-400 leading-relaxed">
      One-time initialization archives each selected account's existing
      <code class="mono-chip">authorized_keys</code> file and records its keys as no-owner, so Kohaku can take over key management. The management account is never touched.
    </p>

    <div class="flex gap-2">
      <KButton variant="secondary" :loading="previewing" @click="loadPreview">
        {{ preview.length ? "Reload preview" : "Preview initialization" }}
      </KButton>
      <KButton v-if="preview.length" variant="primary" :disabled="!selectedUsernames.length" @click="confirmOpen = true"> Initialize {{ selectedUsernames.length }} account{{ selectedUsernames.length === 1 ? "" : "s" }}… </KButton>
    </div>

    <div v-if="preview.length" class="table-wrap">
      <table class="table-base">
        <thead>
          <tr>
            <th class="th-cell w-10"></th>
            <th class="th-cell">Account</th>
            <th class="th-cell">UID</th>
            <th class="th-cell">Existing keys</th>
            <th class="th-cell">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="acct in preview" :key="acct.username" class="align-top">
            <td class="td-cell">
              <input v-model="selected[acct.username]" type="checkbox" class="accent-iolite" :disabled="applying" />
            </td>
            <td class="td-cell font-mono text-sm">{{ acct.username }}</td>
            <td class="td-cell font-mono text-xs">{{ acct.uid ?? "—" }}</td>
            <td class="td-cell">
              <div v-if="(acct.keys || []).length" class="space-y-0.5">
                <div v-for="(k, i) in acct.keys" :key="i" class="font-mono text-[11px] text-warm-500 dark:text-warm-400 break-all">
                  {{ k.fingerprint }}
                </div>
              </div>
              <span v-else class="text-xs text-warm-400">no keys</span>
            </td>
            <td class="td-cell">
              <StatusBadge v-if="acct.key_file_archived" state="ok" label="already archived" />
              <span v-else class="text-xs text-warm-400">eligible</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="results.length" class="space-y-2">
      <div class="field-label">Results</div>
      <div class="table-wrap">
        <table class="table-base">
          <thead>
            <tr>
              <th class="th-cell">Account</th>
              <th class="th-cell">Result</th>
              <th class="th-cell">Detail</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in results" :key="i">
              <td class="td-cell font-mono text-sm">{{ r.username }}</td>
              <td class="td-cell"><StatusBadge :state="r.status || (r.error ? 'failed' : 'succeeded')" /></td>
              <td class="td-cell text-xs text-warm-500 dark:text-warm-400 break-words">
                {{ r.error || r.detail || "archived" }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <ConfirmModal v-model:open="confirmOpen" title="Initialize machine accounts" confirm-text="Initialize" variant="primary" :loading="applying" width="560px" @confirm="apply">
      <div class="space-y-2 text-sm text-warm-700 dark:text-warm-300">
        <p>You are about to initialize {{ selectedUsernames.length }} account(s). Please confirm you understand:</p>
        <ul class="space-y-1.5 pl-1">
          <li class="flex gap-2">
            <span class="i-carbon-checkmark-outline text-aquamarine mt-0.5 shrink-0" />
            No account or user data is deleted.
          </li>
          <li class="flex gap-2">
            <span class="i-carbon-checkmark-outline text-aquamarine mt-0.5 shrink-0" />
            The old key file remains available as a backup.
          </li>
          <li class="flex gap-2">
            <span class="i-carbon-warning-alt text-amber mt-0.5 shrink-0" />
            An unreported user may temporarily lose SSH-key access, but their account and data remain.
          </li>
          <li class="flex gap-2">
            <span class="i-carbon-locked text-iolite mt-0.5 shrink-0" />
            The management account is never processed by this key-reset flow.
          </li>
        </ul>
      </div>
    </ConfirmModal>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from "vue"

import { ElMessage } from "element-plus"

import ConfirmModal from "@/components/common/ConfirmModal.vue"
import KButton from "@/components/common/KButton.vue"
import StatusBadge from "@/components/common/StatusBadge.vue"
import { machinesAPI } from "@/utils/api"

const props = defineProps({
  machineId: { type: [Number, String], required: true },
})

const emit = defineEmits(["done"])

const previewing = ref(false)
const applying = ref(false)
const preview = ref([])
const selected = reactive({})
const results = ref([])
const confirmOpen = ref(false)

const selectedUsernames = computed(() => preview.value.filter((a) => selected[a.username]).map((a) => a.username))

async function loadPreview() {
  previewing.value = true
  results.value = []
  try {
    const res = await machinesAPI.initPreview(props.machineId)
    const list = Array.isArray(res) ? res : res.accounts || []
    preview.value = list
    // Default: select eligible (not-yet-archived) accounts.
    for (const acct of list) {
      selected[acct.username] = !acct.key_file_archived
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to load preview")
  } finally {
    previewing.value = false
  }
}

async function apply() {
  applying.value = true
  try {
    const res = await machinesAPI.initApply(props.machineId, selectedUsernames.value)
    results.value = Array.isArray(res) ? res : res.results || []
    ElMessage.success("Initialization applied")
    confirmOpen.value = false
    emit("done")
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Initialization failed")
  } finally {
    applying.value = false
  }
}
</script>
