<template>
  <div class="container-page space-y-5">
    <RouterLink to="/machines" class="inline-flex items-center gap-1 text-sm text-warm-500 dark:text-warm-400 hover:text-iolite"> <span class="i-carbon-arrow-left" /> All machines </RouterLink>

    <LoadingBlock v-if="loading && !machine" :rows="6" />

    <template v-else-if="machine">
      <header class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div class="flex items-center gap-2">
            <h1 class="page-title">{{ machine.name }}</h1>
            <StatusBadge :state="machine.status" dot />
            <StatusBadge v-if="auth.isLeader && !machine.enrolled" state="new" label="not enrolled" />
          </div>
          <p v-if="machine.address" class="text-secondary mt-1 font-mono text-xs">
            {{ machine.management_user ? machine.management_user + "@" : "" }}{{ machine.address }}<template v-if="machine.port && machine.port !== 22">:{{ machine.port }}</template>
          </p>
          <div v-if="(machine.tags || []).length" class="flex flex-wrap gap-1 mt-2">
            <span v-for="t in machine.tags" :key="t" class="mono-chip">{{ t }}</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span v-if="machine.last_check_at" :title="fullTime(machine.last_check_at)" class="text-xs text-warm-400 dark:text-warm-500"> checked {{ fromNow(machine.last_check_at) }} </span>
          <KButton v-if="auth.isLeader" variant="secondary" icon="i-carbon-refresh" :loading="refreshing" @click="refresh"> Refresh </KButton>
        </div>
      </header>

      <div v-if="machine.last_error" class="card p-3 border-coral/40 bg-coral-light/40 dark:bg-coral-shadow/10">
        <div class="flex items-start gap-2 text-sm text-coral-shadow dark:text-coral-light">
          <span class="i-carbon-warning-alt mt-0.5 shrink-0" />
          <span class="break-words">{{ machine.last_error }}</span>
        </div>
      </div>

      <el-tabs v-model="tab" class="ksm-tabs">
        <el-tab-pane label="Facts" name="facts">
          <SectionCard><FactsPanel :facts="machine.facts" /></SectionCard>
        </el-tab-pane>

        <el-tab-pane :label="`Accounts (${accounts.length})`" name="accounts">
          <SectionCard>
            <LoadingBlock v-if="loadingAccounts" />
            <template v-else>
              <AccountsTable v-if="accounts.length" :accounts="accounts" :admin="auth.isAdmin" @adopt="openAdopt" @unlink="unlinkAccount" @groups="openGroups" @delete="openDelete" />
              <EmptyState v-else icon="i-carbon-user-multiple" text="No accounts observed" hint="Refresh the machine to read its accounts." />
            </template>
          </SectionCard>
        </el-tab-pane>

        <el-tab-pane label="Keys" name="keys">
          <SectionCard><KeysPanel :accounts="accounts" /></SectionCard>
        </el-tab-pane>

        <el-tab-pane label="Storage" name="storage">
          <SectionCard title="Configured mounts on this machine" icon="i-carbon-datastore">
            <div v-if="machineMounts.length" class="table-wrap">
              <table class="table-base">
                <thead>
                  <tr>
                    <th class="th-cell">Logical name</th>
                    <th class="th-cell">Path</th>
                    <th class="th-cell">Preferred</th>
                    <th class="th-cell">Enabled</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="mt in machineMounts" :key="mt.id">
                    <td class="td-cell font-medium">{{ mt.name }}</td>
                    <td class="td-cell font-mono text-xs break-all">{{ mt.path }}</td>
                    <td class="td-cell">
                      <span v-if="mt.preferred" class="i-carbon-star-filled text-amber" />
                      <span v-else class="text-warm-300">—</span>
                    </td>
                    <td class="td-cell"><StatusBadge :state="mt.enabled ? 'ok' : 'revoked'" :label="mt.enabled ? 'enabled' : 'disabled'" /></td>
                  </tr>
                </tbody>
              </table>
              <RouterLink v-if="auth.isAdmin" to="/storage" class="inline-block mt-3 text-sm text-iolite dark:text-iolite-light"> Manage mounts &amp; scan usage → </RouterLink>
            </div>
            <EmptyState v-else icon="i-carbon-datastore" text="No mounts configured for this machine" />
          </SectionCard>
        </el-tab-pane>

        <el-tab-pane label="Actions" name="actions">
          <SectionCard title="Recent remote actions" icon="i-carbon-activity">
            <LoadingBlock v-if="loadingActions" />
            <template v-else>
              <ActionsTable v-if="actions.length" :actions="actions" :show-retry="auth.isAdmin" @retry="retryAction" />
              <EmptyState v-else icon="i-carbon-activity" text="No actions yet" />
            </template>
          </SectionCard>
        </el-tab-pane>

        <el-tab-pane v-if="auth.isAdmin" label="Admin ops" name="admin">
          <div class="space-y-5">
            <SectionCard title="Enrollment" icon="i-carbon-security">
              <EnrollPanel :machine="machine" @done="onEnrolled" />
            </SectionCard>
            <SectionCard title="Initialize existing accounts" icon="i-carbon-migrate">
              <InitPanel :machine-id="machine.id" @done="onInitialized" />
            </SectionCard>
            <SectionCard title="Danger zone" icon="i-carbon-warning">
              <div class="flex items-center justify-between gap-3">
                <p class="text-sm text-warm-600 dark:text-warm-400">Delete this machine from the panel. Requires no enabled mounts. Audit history is kept.</p>
                <KButton variant="danger" @click="deleteMachineConfirm">Delete machine</KButton>
              </div>
            </SectionCard>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>

    <EmptyState v-else icon="i-carbon-warning" text="Machine not found" />

    <!-- Adopt account -->
    <el-dialog v-model="adoptModal.open" title="Adopt account → link panel user" width="420px" align-center append-to-body>
      <KField label="Panel user">
        <KSelect v-model="adoptModal.userId" :options="userOptions" placeholder="Select a user…" />
      </KField>
      <template #footer>
        <div class="flex justify-end gap-2">
          <KButton variant="secondary" @click="adoptModal.open = false">Cancel</KButton>
          <KButton variant="primary" :loading="adoptModal.loading" :disabled="!adoptModal.userId" @click="adopt">Adopt</KButton>
        </div>
      </template>
    </el-dialog>

    <!-- Set groups -->
    <el-dialog v-model="groupsModal.open" title="Set account groups" width="460px" align-center append-to-body>
      <div class="space-y-3">
        <p class="text-xs text-warm-500 dark:text-warm-400">Comma-separated group names. Only the groups you list are added or removed; others are left alone.</p>
        <KField label="Add to groups"><KInput v-model="groupsModal.addText" placeholder="docker, video" /></KField>
        <KField label="Remove from groups"><KInput v-model="groupsModal.removeText" placeholder="sudo" /></KField>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <KButton variant="secondary" @click="groupsModal.open = false">Cancel</KButton>
          <KButton variant="primary" :loading="groupsModal.loading" @click="applyGroups">Apply</KButton>
        </div>
      </template>
    </el-dialog>

    <!-- Delete account -->
    <ConfirmModal v-model:open="deleteModal.open" title="Delete physical account" confirm-text="Delete account" variant="danger" :confirm-word="deleteModal.account?.username || ''" :loading="deleteModal.loading" width="520px" @confirm="deleteAccount">
      <div class="space-y-3">
        <p class="text-sm text-warm-700 dark:text-warm-300">
          This deletes the Unix account
          <code class="mono-chip">{{ deleteModal.account?.username }}</code>
          on <strong>{{ machine?.name }}</strong> via a remote action. It does not touch the linked panel user.
        </p>
        <label class="flex items-start gap-2 text-sm p-3 rounded-lg border border-coral/40 bg-coral-light/30 dark:bg-coral-shadow/10 cursor-pointer">
          <input v-model="deleteModal.deleteHome" type="checkbox" class="accent-coral mt-0.5" />
          <span> <strong>Also delete the home directory and its data</strong> (<code class="mono-chip">userdel -r</code>). Leave unchecked to keep all files on disk. </span>
        </label>
      </div>
    </ConfirmModal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from "vue"
import { useRoute, useRouter, RouterLink } from "vue-router"

import { ElMessage, ElMessageBox } from "element-plus"

import ConfirmModal from "@/components/common/ConfirmModal.vue"
import EmptyState from "@/components/common/EmptyState.vue"
import KButton from "@/components/common/KButton.vue"
import KField from "@/components/common/KField.vue"
import KInput from "@/components/common/KInput.vue"
import KSelect from "@/components/common/KSelect.vue"
import LoadingBlock from "@/components/common/LoadingBlock.vue"
import SectionCard from "@/components/common/SectionCard.vue"
import StatusBadge from "@/components/common/StatusBadge.vue"
import AccountsTable from "@/components/machines/AccountsTable.vue"
import ActionsTable from "@/components/machines/ActionsTable.vue"
import EnrollPanel from "@/components/machines/EnrollPanel.vue"
import FactsPanel from "@/components/machines/FactsPanel.vue"
import InitPanel from "@/components/machines/InitPanel.vue"
import KeysPanel from "@/components/machines/KeysPanel.vue"
import { useActionPoll } from "@/composables/useActionPoll"
import { useAuthStore } from "@/stores/auth"
import { machinesAPI, actionsAPI, storageAPI, usersAPI } from "@/utils/api"
import { fromNow, fullTime } from "@/utils/format"

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const poll = useActionPoll()

const machineId = computed(() => Number(route.params.id))
const tab = ref("facts")

const machine = ref(null)
const accounts = ref([])
const actions = ref([])
const mounts = ref([])
const users = ref([])

const loading = ref(true)
const loadingAccounts = ref(false)
const loadingActions = ref(false)
const refreshing = ref(false)

const machineMounts = computed(() => mounts.value.filter((m) => (m.machine_id ?? m.machine?.id) === machineId.value))
const userOptions = computed(() => users.value.map((u) => ({ value: u.id, label: u.display_name || u.username })))

const adoptModal = reactive({ open: false, account: null, userId: "", loading: false })
const groupsModal = reactive({ open: false, account: null, addText: "", removeText: "", loading: false })
const deleteModal = reactive({ open: false, account: null, deleteHome: false, loading: false })

let liveTimer = null

async function loadMachine() {
  machine.value = await machinesAPI.get(machineId.value)
}

async function loadAccounts() {
  loadingAccounts.value = true
  try {
    accounts.value = await machinesAPI.accounts(machineId.value)
  } catch {
    accounts.value = []
  } finally {
    loadingAccounts.value = false
  }
}

async function loadActions() {
  loadingActions.value = true
  try {
    actions.value = await actionsAPI.list({ machine_id: machineId.value, limit: 25 })
  } catch {
    actions.value = []
  } finally {
    loadingActions.value = false
  }
}

async function loadMounts() {
  if (!auth.isAdmin) return
  try {
    mounts.value = await storageAPI.listMounts()
  } catch {
    mounts.value = []
  }
}

async function loadUsers() {
  if (!auth.isAdmin) return
  try {
    users.value = await usersAPI.list()
  } catch {
    users.value = []
  }
}

async function loadAll() {
  loading.value = true
  try {
    await loadMachine()
  } catch {
    machine.value = null
    loading.value = false
    return
  }
  loading.value = false
  await Promise.all([loadAccounts(), loadActions(), loadMounts(), loadUsers()])
}

// While any action is pending/running, refresh the actions + accounts every
// 5s so progress and results land without a manual reload.
function ensureLivePoll() {
  const hasLive = actions.value.some((a) => ["pending", "running"].includes(a.state))
  if (hasLive && !liveTimer) {
    liveTimer = setInterval(async () => {
      await loadActions()
      if (!actions.value.some((a) => ["pending", "running"].includes(a.state))) {
        clearInterval(liveTimer)
        liveTimer = null
        await Promise.all([loadMachine(), loadAccounts()])
      }
    }, 5000)
  }
}

// Await an action-returning endpoint: poll it to terminal, toast, reload.
async function track(actionId, label) {
  const row = await poll.start(actionId)
  if (row.state === "succeeded") {
    ElMessage.success(`${label} succeeded`)
  } else {
    ElMessage.error(row.error || `${label} ${row.state}`)
  }
  await Promise.all([loadMachine(), loadAccounts(), loadActions()])
  return row
}

async function refresh() {
  refreshing.value = true
  try {
    const res = await machinesAPI.refresh(machineId.value)
    await loadActions()
    ensureLivePoll()
    if (res?.action_id) await track(res.action_id, "Refresh")
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Refresh failed")
  } finally {
    refreshing.value = false
  }
}

async function retryAction(a) {
  try {
    const res = await actionsAPI.retry(a.id)
    await loadActions()
    ensureLivePoll()
    if (res?.action_id) await track(res.action_id, "Retry")
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Retry failed")
  }
}

function openAdopt(account) {
  adoptModal.account = account
  adoptModal.userId = ""
  adoptModal.open = true
}
async function adopt() {
  adoptModal.loading = true
  try {
    await machinesAPI.adoptAccount(adoptModal.account.id, adoptModal.userId)
    ElMessage.success("Account adopted")
    adoptModal.open = false
    await loadAccounts()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to adopt")
  } finally {
    adoptModal.loading = false
  }
}

async function unlinkAccount(account) {
  try {
    await ElMessageBox.confirm(`Unlink ${account.username} from its panel user? The account becomes unmanaged; nothing on the machine changes.`, "Unlink account", { confirmButtonText: "Unlink" })
  } catch {
    return
  }
  try {
    await machinesAPI.unlinkAccount(account.id)
    ElMessage.success("Account unlinked")
    await loadAccounts()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to unlink")
  }
}

function openGroups(account) {
  groupsModal.account = account
  groupsModal.addText = ""
  groupsModal.removeText = ""
  groupsModal.open = true
}
async function applyGroups() {
  const add = groupsModal.addText
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
  const remove = groupsModal.removeText
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
  if (!add.length && !remove.length) {
    ElMessage.warning("Enter at least one group to add or remove")
    return
  }
  groupsModal.loading = true
  try {
    const res = await machinesAPI.setAccountGroups(groupsModal.account.id, { add, remove })
    groupsModal.open = false
    await loadActions()
    ensureLivePoll()
    if (res?.action_id) await track(res.action_id, "Set groups")
    else await loadAccounts()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to set groups")
  } finally {
    groupsModal.loading = false
  }
}

function openDelete(account) {
  deleteModal.account = account
  deleteModal.deleteHome = false
  deleteModal.open = true
}
async function deleteAccount() {
  deleteModal.loading = true
  try {
    const res = await machinesAPI.deleteAccount(deleteModal.account.id, {
      deleteHome: deleteModal.deleteHome,
      confirm: deleteModal.account.username,
    })
    deleteModal.open = false
    await loadActions()
    ensureLivePoll()
    if (res?.action_id) await track(res.action_id, "Delete account")
    else await loadAccounts()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to delete account")
  } finally {
    deleteModal.loading = false
  }
}

async function deleteMachineConfirm() {
  try {
    await ElMessageBox.confirm(`Delete machine ${machine.value.name}? This removes it from the panel. Audit history is kept.`, "Delete machine", { type: "warning", confirmButtonText: "Delete" })
  } catch {
    return
  }
  try {
    await machinesAPI.remove(machineId.value)
    ElMessage.success("Machine deleted")
    router.push("/machines")
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to delete machine")
  }
}

function onEnrolled() {
  loadAll()
}
function onInitialized() {
  loadAccounts()
  loadActions()
}

onMounted(loadAll)
onUnmounted(() => {
  if (liveTimer) clearInterval(liveTimer)
})
</script>

<style scoped>
.ksm-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
}
</style>
