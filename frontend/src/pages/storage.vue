<template>
  <div class="container-page space-y-5">
    <header class="flex items-center justify-between gap-3">
      <div>
        <h1 class="page-title">Storage</h1>
        <p class="text-secondary mt-1">Mount mappings and usage scans. Duplicate sources are grouped, never summed.</p>
      </div>
      <KButton variant="primary" icon="i-carbon-add" @click="openCreate">Add mount</KButton>
    </header>

    <LoadingBlock v-if="loading" :rows="5" />
    <template v-else>
      <EmptyState v-if="!mounts.length" icon="i-carbon-datastore" text="No mounts configured" hint="Add a mount mapping to start scanning usage." />

      <SectionCard v-for="grp in grouped" :key="grp.name" :title="grp.name" :subtitle="grp.mounts.length > 1 ? `${grp.mounts.length} mappings of the same logical source — scan the preferred one` : ''" icon="i-carbon-datastore">
        <div class="table-wrap">
          <table class="table-base">
            <thead>
              <tr>
                <th class="th-cell">Machine</th>
                <th class="th-cell">Path</th>
                <th class="th-cell">Preferred</th>
                <th class="th-cell">Enabled</th>
                <th class="th-cell text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="mt in grp.mounts" :key="mt.id" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30">
                <td class="td-cell">{{ machineName(mt) }}</td>
                <td class="td-cell font-mono text-xs break-all">{{ mt.path }}</td>
                <td class="td-cell">
                  <span v-if="mt.preferred" class="i-carbon-star-filled text-amber" title="Preferred scan location" />
                  <span v-else class="text-warm-300">—</span>
                </td>
                <td class="td-cell"><StatusBadge :state="mt.enabled ? 'ok' : 'revoked'" :label="mt.enabled ? 'enabled' : 'disabled'" /></td>
                <td class="td-cell text-right whitespace-nowrap space-x-1">
                  <button class="btn-ghost" :disabled="scanning[mt.id]" @click="scan(mt)">
                    {{ scanning[mt.id] ? "Scanning…" : "Scan" }}
                  </button>
                  <button class="btn-ghost" @click="openUsage(mt)">Usage</button>
                  <button class="btn-ghost" @click="openEdit(mt)">Edit</button>
                  <button class="btn-ghost text-coral-shadow dark:text-coral-light" @click="removeMount(mt)">Delete</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>
    </template>

    <!-- Create / edit mount -->
    <el-dialog v-model="formModal.open" :title="formModal.id ? 'Edit mount' : 'Add mount'" width="520px" align-center append-to-body>
      <div class="space-y-3">
        <KField label="Logical name" required hint="Same name across machines that mount the same source."><KInput v-model="formModal.name" placeholder="nas1" /></KField>
        <KField label="Machine" required><KSelect v-model="formModal.machine_id" :options="machineOptions" placeholder="Select a machine…" /></KField>
        <KField label="Mount path" required><KInput v-model="formModal.path" placeholder="/mnt/nas1" /></KField>
        <KField label="Directories to summarize" hint="One per line. Optional.">
          <KInput v-model="formModal.subdirsText" type="textarea" :rows="3" placeholder="/mnt/nas1/datasets&#10;/mnt/nas1/home" />
        </KField>
        <KField label="Notes"><KInput v-model="formModal.notes" placeholder="Optional" /></KField>
        <div class="flex gap-6">
          <label class="flex items-center gap-2 text-sm cursor-pointer"><input v-model="formModal.preferred" type="checkbox" class="accent-iolite" /> Preferred scan location</label>
          <label class="flex items-center gap-2 text-sm cursor-pointer"><input v-model="formModal.enabled" type="checkbox" class="accent-iolite" /> Enabled</label>
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <KButton variant="secondary" @click="formModal.open = false">Cancel</KButton>
          <KButton variant="primary" :loading="formModal.loading" :disabled="!formValid" @click="saveMount">Save</KButton>
        </div>
      </template>
    </el-dialog>

    <!-- Usage viewer -->
    <el-dialog v-model="usageModal.open" :title="`Usage — ${usageModal.title}`" width="720px" align-center append-to-body>
      <LoadingBlock v-if="usageModal.loading" />
      <template v-else>
        <UsageTables v-if="usageModal.data" :usage="usageModal.data" />
        <EmptyState v-else icon="i-carbon-chart-line" text="No usage recorded yet" hint="Run a scan to collect usage." />
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue"

import { ElMessage, ElMessageBox } from "element-plus"

import EmptyState from "@/components/common/EmptyState.vue"
import KButton from "@/components/common/KButton.vue"
import KField from "@/components/common/KField.vue"
import KInput from "@/components/common/KInput.vue"
import KSelect from "@/components/common/KSelect.vue"
import LoadingBlock from "@/components/common/LoadingBlock.vue"
import SectionCard from "@/components/common/SectionCard.vue"
import StatusBadge from "@/components/common/StatusBadge.vue"
import UsageTables from "@/components/storage/UsageTables.vue"
import { useActionPoll } from "@/composables/useActionPoll"
import { storageAPI, machinesAPI } from "@/utils/api"

const poll = useActionPoll()

const mounts = ref([])
const machines = ref([])
const loading = ref(true)
const scanning = reactive({})

const machineOptions = computed(() => machines.value.map((m) => ({ value: m.id, label: m.name })))

// Group mount rows by their logical name so duplicate sources sit together.
const grouped = computed(() => {
  const map = new Map()
  for (const mt of mounts.value) {
    if (!map.has(mt.name)) map.set(mt.name, [])
    map.get(mt.name).push(mt)
  }
  return [...map.entries()].map(([name, list]) => ({ name, mounts: list }))
})

function machineName(mt) {
  const id = mt.machine_id ?? mt.machine?.id
  return mt.machine_name || mt.machine?.name || machines.value.find((m) => m.id === id)?.name || "—"
}

const formModal = reactive({
  open: false,
  id: null,
  name: "",
  machine_id: "",
  path: "",
  subdirsText: "",
  notes: "",
  preferred: false,
  enabled: true,
  loading: false,
})
const formValid = computed(() => formModal.name.trim() && formModal.machine_id && formModal.path.trim())

const usageModal = reactive({ open: false, title: "", data: null, loading: false, mountId: null })

async function load() {
  loading.value = true
  try {
    const [mts, ms] = await Promise.all([storageAPI.listMounts(), machinesAPI.list()])
    mounts.value = mts
    machines.value = ms
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(formModal, {
    open: true,
    id: null,
    name: "",
    machine_id: "",
    path: "",
    subdirsText: "",
    notes: "",
    preferred: false,
    enabled: true,
    loading: false,
  })
}
function openEdit(mt) {
  Object.assign(formModal, {
    open: true,
    id: mt.id,
    name: mt.name,
    machine_id: mt.machine_id ?? mt.machine?.id ?? "",
    path: mt.path,
    subdirsText: (mt.subdirs || []).join("\n"),
    notes: mt.notes || "",
    preferred: !!mt.preferred,
    enabled: mt.enabled !== false,
    loading: false,
  })
}
async function saveMount() {
  if (!formValid.value) return
  formModal.loading = true
  try {
    const body = {
      name: formModal.name.trim(),
      machine_id: formModal.machine_id,
      path: formModal.path.trim(),
      subdirs: formModal.subdirsText
        .split(/[\n,]/)
        .map((s) => s.trim())
        .filter(Boolean),
      notes: formModal.notes.trim(),
      preferred: formModal.preferred,
      enabled: formModal.enabled,
    }
    if (formModal.id) await storageAPI.updateMount(formModal.id, body)
    else await storageAPI.createMount(body)
    ElMessage.success("Mount saved")
    formModal.open = false
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to save mount")
  } finally {
    formModal.loading = false
  }
}

async function removeMount(mt) {
  try {
    await ElMessageBox.confirm(`Delete mount mapping ${mt.name} (${mt.path})? Stored usage for it is removed.`, "Delete mount", {
      type: "warning",
      confirmButtonText: "Delete",
    })
  } catch {
    return
  }
  try {
    await storageAPI.removeMount(mt.id)
    ElMessage.success("Mount deleted")
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to delete mount")
  }
}

async function scan(mt) {
  scanning[mt.id] = true
  try {
    const res = await storageAPI.scan(mt.id)
    if (res?.action_id) {
      const row = await poll.start(res.action_id)
      if (row.state === "succeeded") {
        ElMessage.success(`Scan of ${mt.name} finished`)
        if (usageModal.open && usageModal.mountId === mt.id) await reloadUsage(mt)
      } else {
        ElMessage.error(row.error || `Scan ${row.state}`)
      }
    } else {
      ElMessage.success("Scan started")
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Scan failed")
  } finally {
    scanning[mt.id] = false
  }
}

async function openUsage(mt) {
  usageModal.open = true
  usageModal.title = `${mt.name} · ${machineName(mt)}`
  usageModal.mountId = mt.id
  await reloadUsage(mt)
}
async function reloadUsage(mt) {
  usageModal.loading = true
  try {
    usageModal.data = await storageAPI.usage(mt.id)
  } catch {
    usageModal.data = null
  } finally {
    usageModal.loading = false
  }
}

onMounted(load)
</script>
