<template>
  <div class="container-page space-y-5">
    <header>
      <h1 class="page-title">Dashboard</h1>
      <p class="text-secondary mt-1">Your machine access, requests, storage, and keys.</p>
    </header>

    <!-- My machine access -->
    <SectionCard title="My machine access" icon="i-carbon-connect">
      <LoadingBlock v-if="loading.access" />
      <template v-else>
        <AccessMatrix v-if="currentAccess.length" :rows="currentAccess" @revoke="revokeAccess" />
        <EmptyState v-else icon="i-carbon-connect" text="No access yet" hint="Request access to a machine below." />
      </template>
    </SectionCard>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <!-- Request access -->
      <SectionCard title="Request access" icon="i-carbon-add-alt">
        <RequestAccessForm :machines="machines" :default-username="defaultTarget" @requested="onRequested" />
      </SectionCard>

      <!-- My requests -->
      <SectionCard title="My requests" icon="i-carbon-task" subtitle="Granted access moves up to the access list.">
        <LoadingBlock v-if="loading.requests" />
        <template v-else>
          <RequestTable v-if="openRequests.length" :rows="openRequests" @revoke="revokeAccess" />
          <EmptyState v-else icon="i-carbon-task" text="No open requests" />
        </template>
      </SectionCard>
    </div>

    <!-- My storage usage -->
    <SectionCard title="My storage usage" icon="i-carbon-datastore">
      <LoadingBlock v-if="loading.storage" />
      <template v-else>
        <div v-if="storage.length" class="table-wrap">
          <table class="table-base">
            <thead>
              <tr>
                <th class="th-cell">Mount</th>
                <th class="th-cell">Machine</th>
                <th class="th-cell">Path</th>
                <th class="th-cell text-right">Size</th>
                <th class="th-cell">Scanned</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in storage" :key="i" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30">
                <td class="td-cell font-medium">{{ row.mount_name || row.name }}</td>
                <td class="td-cell">{{ row.machine_name || "—" }}</td>
                <td class="td-cell font-mono text-xs break-all">{{ row.path }}</td>
                <td class="td-cell text-right font-medium">{{ humanBytes(row.bytes) }}</td>
                <td class="td-cell whitespace-nowrap">
                  <span :title="fullTime(row.scanned_at)" class="text-xs text-warm-500 dark:text-warm-400">
                    {{ fromNow(row.scanned_at) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else icon="i-carbon-datastore" text="No storage usage recorded" hint="Usage appears once an admin scans a mount you own files on." />
      </template>
    </SectionCard>

    <!-- My SSH keys (add key at the bottom) -->
    <SectionCard title="My SSH keys" icon="i-carbon-password" subtitle="Sync pushes your active keys to every machine you have access to and cleans up revoked ones.">
      <template #actions>
        <KButton variant="secondary" icon="i-carbon-renew" :loading="syncing" @click="syncKeys">Sync keys to machines</KButton>
      </template>
      <LoadingBlock v-if="loading.keys" />
      <template v-else>
        <KeyList v-if="keys.length" :keys="keys" @revoke="revokeKey" />
        <EmptyState v-else icon="i-carbon-password" text="No keys yet" hint="Add a public key below to start requesting access." />
        <div class="mt-4 border-t border-warm-100 dark:border-warm-800 pt-4">
          <h3 class="text-sm font-medium text-warm-700 dark:text-warm-300 mb-3">Add a new SSH key</h3>
          <AddKeyForm :show-install="true" @added="reloadKeys" />
        </div>
      </template>
    </SectionCard>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue"

import { ElMessage, ElMessageBox } from "element-plus"

import AccessMatrix from "@/components/access/AccessMatrix.vue"
import RequestAccessForm from "@/components/access/RequestAccessForm.vue"
import RequestTable from "@/components/access/RequestTable.vue"
import EmptyState from "@/components/common/EmptyState.vue"
import KButton from "@/components/common/KButton.vue"
import LoadingBlock from "@/components/common/LoadingBlock.vue"
import SectionCard from "@/components/common/SectionCard.vue"
import AddKeyForm from "@/components/keys/AddKeyForm.vue"
import KeyList from "@/components/keys/KeyList.vue"
import { useActionPoll } from "@/composables/useActionPoll"
import { useAuthStore } from "@/stores/auth"
import { keysAPI, accessAPI, machinesAPI, storageAPI } from "@/utils/api"
import { humanBytes, fromNow, fullTime } from "@/utils/format"

const auth = useAuthStore()

const keys = ref([])
const access = ref([])
const requests = ref([])
const machines = ref([])
const storage = ref([])

const loading = reactive({ keys: true, access: true, requests: true, storage: true })
const syncing = ref(false)
const poll = useActionPoll()

// Prefer the user's configured default machine account, else their panel name.
const defaultTarget = computed(() => auth.defaultAccount || auth.name)

// Split the two dashboard sections cleanly: granted access lives in the
// matrix; the requests table keeps only not-yet-granted lifecycle rows.
const currentAccess = computed(() => access.value.filter((r) => r.state === "active"))
const openRequests = computed(() => requests.value.filter((r) => r.state !== "active"))

async function reloadKeys() {
  loading.keys = true
  try {
    keys.value = await keysAPI.list()
  } finally {
    loading.keys = false
  }
}

async function reloadAccess() {
  loading.access = true
  loading.requests = true
  try {
    // /access/overview returns {access: [...], keys: [...]}, not a bare array.
    access.value = (await accessAPI.overview()).access ?? []
  } finally {
    loading.access = false
  }
  try {
    requests.value = await accessAPI.listRequests({ mine: true })
  } finally {
    loading.requests = false
  }
}

async function loadMachines() {
  try {
    machines.value = await machinesAPI.list()
  } catch {
    machines.value = []
  }
}

async function loadStorage() {
  loading.storage = true
  try {
    storage.value = await storageAPI.mine()
  } catch {
    storage.value = []
  } finally {
    loading.storage = false
  }
}

async function revokeKey(key) {
  try {
    await ElMessageBox.confirm("Revoke this key? It will be removed from every machine account it is installed on. Your account data is untouched.", "Revoke key", { type: "warning", confirmButtonText: "Revoke" })
  } catch {
    return
  }
  try {
    await keysAPI.revoke(key.id)
    ElMessage.success("Key revoked")
    await Promise.all([reloadKeys(), reloadAccess()])
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to revoke key")
  }
}

async function revokeAccess(row) {
  const id = row.request_id || row.id
  try {
    await ElMessageBox.confirm("Revoke this access? Your managed keys are removed from the account. The account, home directory, and data are left in place.", "Revoke access", { type: "warning", confirmButtonText: "Revoke" })
  } catch {
    return
  }
  try {
    await accessAPI.revoke(id)
    ElMessage.success("Access revoked")
    await reloadAccess()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to revoke access")
  }
}

function onRequested() {
  reloadAccess()
}

async function syncKeys() {
  syncing.value = true
  try {
    const res = await accessAPI.sync()
    const ids = res.action_ids || []
    let failed = 0
    for (const aid of ids) {
      const row = await poll.start(aid)
      if (row.state !== "succeeded") failed += 1
    }
    if (!ids.length) ElMessage.info("Nothing to sync — no active machine access")
    else if (failed) ElMessage.warning(`Sync finished with ${failed} failed action(s) — check with an admin`)
    else ElMessage.success(`Keys synced (${ids.length} action(s))`)
    await Promise.all([reloadKeys(), reloadAccess()])
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Sync failed")
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  reloadKeys()
  reloadAccess()
  loadMachines()
  loadStorage()
})
</script>
