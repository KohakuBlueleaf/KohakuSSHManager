<template>
  <div class="container-page space-y-5">
    <header>
      <h1 class="page-title">Users</h1>
      <p class="text-secondary mt-1">Panel identities. Deleting a user never touches machine accounts.</p>
    </header>

    <SectionCard title="Create user" icon="i-carbon-user-follow">
      <form class="grid grid-cols-1 sm:grid-cols-2 gap-3" @submit.prevent="createUser">
        <KField label="Username" required><KInput v-model="form.username" placeholder="jdoe" /></KField>
        <KField label="Display name"><KInput v-model="form.display_name" placeholder="Jane Doe" /></KField>
        <KField label="Password" required><KInput v-model="form.password" type="password" placeholder="initial password" /></KField>
        <KField label="Role"><KSelect v-model="form.role" :options="roleOptions" /></KField>
        <div class="sm:col-span-2 flex justify-end">
          <KButton variant="primary" :loading="creating" :disabled="!canCreate" @click="createUser">Create user</KButton>
        </div>
      </form>
    </SectionCard>

    <SectionCard title="All users" icon="i-carbon-user-multiple">
      <template #actions>
        <KButton variant="secondary" icon="i-carbon-renew" :loading="accessBusy === 'sync:all'" :disabled="accessBusy !== null" @click="syncAllUsers">Sync all keys</KButton>
      </template>
      <LoadingBlock v-if="loading" :rows="4" />
      <template v-else>
        <div v-if="users.length" class="table-wrap">
          <table class="table-base">
            <thead>
              <tr>
                <th class="th-cell">User</th>
                <th class="th-cell">Role</th>
                <th class="th-cell">Enabled</th>
                <th class="th-cell text-right">Keys</th>
                <th class="th-cell text-right">Active access</th>
                <th class="th-cell text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="u in users" :key="u.id">
                <tr class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30">
                  <td class="td-cell">
                    <div class="font-medium">{{ u.display_name || u.username }}</div>
                    <div class="text-[11px] text-warm-400 dark:text-warm-500 font-mono">{{ u.username }}</div>
                  </td>
                  <td class="td-cell">
                    <span class="gem-badge" :class="u.role === 'leader' ? 'bg-sapphire-light text-sapphire-shadow dark:bg-sapphire-shadow/30 dark:text-sapphire-light' : 'bg-warm-200/70 text-warm-600 dark:bg-warm-700/50 dark:text-warm-300'">
                      {{ u.role }}
                    </span>
                  </td>
                  <td class="td-cell"><StatusBadge :state="u.enabled ? 'active' : 'revoked'" :label="u.enabled ? 'enabled' : 'disabled'" /></td>
                  <td class="td-cell text-right">{{ u.key_count ?? "—" }}</td>
                  <td class="td-cell text-right">{{ u.active_access_count ?? "—" }}</td>
                  <td class="td-cell text-right whitespace-nowrap space-x-1">
                    <button class="btn-ghost" :class="expandedId === u.id && 'text-iolite dark:text-iolite-light'" @click="toggleAccess(u)">Access</button>
                    <button class="btn-ghost" @click="openKeys(u)">Keys</button>
                    <button class="btn-ghost" @click="openEdit(u)">Edit</button>
                    <button class="btn-ghost text-coral-shadow dark:text-coral-light" @click="removeUser(u)">Delete</button>
                  </td>
                </tr>
                <tr v-if="expandedId === u.id">
                  <td colspan="6" class="td-cell bg-warm-50/60 dark:bg-warm-900/40">
                    <div class="py-1 space-y-2">
                      <div class="flex items-center justify-between gap-3">
                        <div class="text-xs text-warm-500 dark:text-warm-400">
                          Machine access for <span class="font-mono">{{ u.username }}</span> — granting creates/adopts the Unix account <span class="font-mono">{{ u.username }}</span> and installs their active keys; revoking removes only their managed keys.
                        </div>
                        <KButton variant="secondary" icon="i-carbon-renew" :loading="accessBusy === `sync:${u.id}`" :disabled="accessBusy !== null" @click="syncUserKeys(u)">Sync keys</KButton>
                      </div>
                      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        <div v-for="m in machines" :key="m.id" class="flex items-center justify-between gap-2 rounded-lg border border-warm-200/60 dark:border-warm-700/60 px-3 py-1.5">
                          <span class="text-sm font-medium truncate">{{ m.name }}</span>
                          <span class="flex items-center gap-1.5 shrink-0">
                            <StatusBadge v-if="requestFor(u, m)" :state="requestFor(u, m).state" :label="requestStateLabel(requestFor(u, m).state)" />
                            <KButton v-if="!hasAccess(u, m)" variant="secondary" :loading="accessBusy === busyKey(u, m)" :disabled="accessBusy !== null" @click="grantAccess(u, m)">Grant</KButton>
                            <KButton v-else-if="requestFor(u, m).state === 'active'" variant="danger" :loading="accessBusy === busyKey(u, m)" :disabled="accessBusy !== null" @click="revokeAccess(u, m)">Revoke</KButton>
                          </span>
                        </div>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <EmptyState v-else icon="i-carbon-user-multiple" text="No users yet" hint="Create the first user above." />
      </template>
    </SectionCard>

    <SectionCard title="Unassigned keys (no owner)" icon="i-carbon-unknown" subtitle="Keys discovered during initialization. Assign each to the right panel user.">
      <LoadingBlock v-if="loadingNoOwner" />
      <template v-else>
        <KeyList v-if="noOwnerKeys.length" :keys="noOwnerKeys" :revocable="false" assignable @assign="openAssign" />
        <EmptyState v-else icon="i-carbon-checkmark-outline" text="No unassigned keys" />
      </template>
    </SectionCard>

    <!-- Edit user -->
    <el-dialog v-model="editModal.open" title="Edit user" width="440px" align-center append-to-body>
      <div v-if="editModal.user" class="space-y-3">
        <KField label="Display name"><KInput v-model="editModal.display_name" /></KField>
        <KField label="Role"><KSelect v-model="editModal.role" :options="roleOptions" /></KField>
        <label class="flex items-center gap-2 text-sm cursor-pointer"> <input v-model="editModal.enabled" type="checkbox" class="accent-iolite" /> Enabled </label>
        <KField label="Reset password" hint="Leave blank to keep the current password.">
          <KInput v-model="editModal.password" type="password" placeholder="new password" />
        </KField>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <KButton variant="secondary" @click="editModal.open = false">Cancel</KButton>
          <KButton variant="primary" :loading="editModal.loading" @click="saveEdit">Save</KButton>
        </div>
      </template>
    </el-dialog>

    <!-- Manage user keys -->
    <el-dialog v-model="keysModal.open" :title="`Keys — ${keysModal.user?.display_name || keysModal.user?.username || ''}`" width="640px" align-center append-to-body>
      <div class="space-y-4">
        <LoadingBlock v-if="keysModal.loading" />
        <template v-else>
          <KeyList v-if="keysModal.keys.length" :keys="keysModal.keys" @revoke="revokeUserKey" />
          <EmptyState v-else icon="i-carbon-password" text="No keys for this user" />
          <div class="border-t border-warm-100 dark:border-warm-800 pt-4">
            <div class="field-label">Add a key for this user</div>
            <AddKeyForm :user-id="keysModal.user?.id" :show-install="true" @added="reloadUserKeys" />
          </div>
        </template>
      </div>
    </el-dialog>

    <!-- Assign no-owner key -->
    <el-dialog v-model="assignModal.open" title="Assign key to user" width="420px" align-center append-to-body>
      <p class="text-xs font-mono text-warm-500 dark:text-warm-400 break-all mb-3">{{ assignModal.key?.fingerprint }}</p>
      <KField label="Panel user">
        <KSelect v-model="assignModal.userId" :options="userOptions" placeholder="Select a user…" />
      </KField>
      <template #footer>
        <div class="flex justify-end gap-2">
          <KButton variant="secondary" @click="assignModal.open = false">Cancel</KButton>
          <KButton variant="primary" :loading="assignModal.loading" :disabled="!assignModal.userId" @click="assignKey">Assign</KButton>
        </div>
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
import AddKeyForm from "@/components/keys/AddKeyForm.vue"
import KeyList from "@/components/keys/KeyList.vue"
import { useActionPoll } from "@/composables/useActionPoll"
import { usersAPI, keysAPI, machinesAPI, accessAPI, actionsAPI } from "@/utils/api"
import { requestStateLabel } from "@/utils/format"

const roleOptions = [
  { value: "member", label: "member" },
  { value: "leader", label: "leader" },
]

const poll = useActionPoll()

const users = ref([])
const noOwnerKeys = ref([])
const machines = ref([])
const requests = ref([])
const loading = ref(true)
const loadingNoOwner = ref(true)
const expandedId = ref(null)
const accessBusy = ref(null)

const form = reactive({ username: "", display_name: "", password: "", role: "member" })
const creating = ref(false)
const canCreate = computed(() => form.username.trim() && form.password.trim())

const editModal = reactive({ open: false, user: null, display_name: "", role: "member", enabled: true, password: "", loading: false })
const keysModal = reactive({ open: false, user: null, keys: [], loading: false })
const assignModal = reactive({ open: false, key: null, userId: "", loading: false })

const userOptions = computed(() => users.value.map((u) => ({ value: u.id, label: u.display_name || u.username })))

async function load() {
  loading.value = true
  try {
    users.value = await usersAPI.list()
  } finally {
    loading.value = false
  }
}

async function loadAccessData() {
  try {
    const [ms, reqs] = await Promise.all([machinesAPI.list(), accessAPI.listRequests()])
    machines.value = ms
    requests.value = reqs
  } catch {
    machines.value = []
    requests.value = []
  }
}

function toggleAccess(u) {
  expandedId.value = expandedId.value === u.id ? null : u.id
}

function busyKey(u, m) {
  return `${u.id}:${m.id}`
}

// The user's most relevant request for this machine: an in-flight/active one
// wins; otherwise the most recent historical one (failed/revoked/rejected).
function requestFor(u, m) {
  const rows = requests.value.filter((r) => r.user_id === u.id && r.machine_id === m.id)
  if (!rows.length) return null
  const live = rows.filter((r) => ["pending", "approved", "active"].includes(r.state))
  const pool = live.length ? live : rows
  return pool.reduce((a, b) => (b.id > a.id ? b : a))
}

function hasAccess(u, m) {
  const req = requestFor(u, m)
  return !!req && ["pending", "approved", "active"].includes(req.state)
}

async function grantAccess(u, m) {
  accessBusy.value = busyKey(u, m)
  try {
    const res = await accessAPI.createRequest({ machine_id: m.id, user_id: u.id })
    for (const aid of res.action_ids || []) await poll.start(aid)
    ElMessage.success(`Access to ${m.name} granted for ${u.username}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to grant access")
  } finally {
    accessBusy.value = null
    await Promise.all([loadAccessData(), load()])
  }
}

// Poll many actions to a terminal state; returns failure/unfinished counts.
const TERMINAL = ["succeeded", "failed", "interrupted"]
async function pollActions(ids, timeoutMs = 180000) {
  const pending = new Set(ids)
  let failed = 0
  const deadline = Date.now() + timeoutMs
  while (pending.size && Date.now() < deadline) {
    for (const id of [...pending]) {
      try {
        const row = await actionsAPI.get(id)
        if (TERMINAL.includes(row.state)) {
          pending.delete(id)
          if (row.state !== "succeeded") failed += 1
        }
      } catch {
        // transient poll error — retry next round
      }
    }
    if (pending.size) await new Promise((r) => setTimeout(r, 2000))
  }
  return { failed, unfinished: pending.size }
}

function emptySyncMessage(res, who) {
  if (res.active_access === 0) return `${who}: no active machine access`
  if (res.active_keys === 0) return `${who}: no active SSH keys — add one first`
  return `${who}: nothing to sync (machine accounts not discovered yet? refresh the machine)`
}

async function syncUserKeys(u) {
  accessBusy.value = `sync:${u.id}`
  try {
    const res = await accessAPI.sync({ user_id: u.id })
    const ids = res.action_ids || []
    if (!ids.length) {
      ElMessage.info(emptySyncMessage(res, u.username))
    } else {
      const { failed, unfinished } = await pollActions(ids)
      if (failed || unfinished) ElMessage.warning(`Sync for ${u.username}: ${failed} failed, ${unfinished} still running of ${ids.length}`)
      else ElMessage.success(`Keys synced for ${u.username} (${ids.length} action(s))`)
    }
    await Promise.all([loadAccessData(), load()])
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Sync failed")
  } finally {
    accessBusy.value = null
  }
}

async function syncAllUsers() {
  accessBusy.value = "sync:all"
  try {
    const res = await accessAPI.sync({ all_users: true })
    const ids = res.action_ids || []
    if (!ids.length) {
      ElMessage.info("Nothing to sync for any user")
    } else {
      ElMessage.info(`Dispatched ${ids.length} action(s) for ${res.synced_users.length} user(s)…`)
      const { failed, unfinished } = await pollActions(ids)
      if (failed || unfinished) ElMessage.warning(`Batch sync: ${failed} failed, ${unfinished} still running of ${ids.length}`)
      else ElMessage.success(`Batch sync complete: ${ids.length} action(s), ${res.synced_users.length} user(s)`)
    }
    await Promise.all([loadAccessData(), load()])
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Batch sync failed")
  } finally {
    accessBusy.value = null
  }
}

async function revokeAccess(u, m) {
  const req = requestFor(u, m)
  if (!req) return
  try {
    await ElMessageBox.confirm(`Revoke ${u.username}'s access to ${m.name}? Their managed keys are removed; the account and data stay.`, "Revoke access", { type: "warning", confirmButtonText: "Revoke" })
  } catch {
    return
  }
  accessBusy.value = busyKey(u, m)
  try {
    const res = await accessAPI.revoke(req.id)
    for (const aid of res.action_ids || []) await poll.start(aid)
    ElMessage.success(`Access to ${m.name} revoked for ${u.username}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to revoke access")
  } finally {
    accessBusy.value = null
    await Promise.all([loadAccessData(), load()])
  }
}

async function loadNoOwner() {
  loadingNoOwner.value = true
  try {
    noOwnerKeys.value = await keysAPI.list({ state: "no_owner" })
  } catch {
    noOwnerKeys.value = []
  } finally {
    loadingNoOwner.value = false
  }
}

async function createUser() {
  if (!canCreate.value) return
  creating.value = true
  try {
    await usersAPI.create({
      username: form.username.trim(),
      display_name: form.display_name.trim(),
      password: form.password,
      role: form.role,
    })
    ElMessage.success("User created")
    form.username = ""
    form.display_name = ""
    form.password = ""
    form.role = "member"
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to create user")
  } finally {
    creating.value = false
  }
}

function openEdit(u) {
  editModal.user = u
  editModal.display_name = u.display_name || ""
  editModal.role = u.role
  editModal.enabled = u.enabled
  editModal.password = ""
  editModal.open = true
}
async function saveEdit() {
  editModal.loading = true
  try {
    const body = {
      display_name: editModal.display_name,
      role: editModal.role,
      enabled: editModal.enabled,
    }
    if (editModal.password) body.password = editModal.password
    await usersAPI.update(editModal.user.id, body)
    ElMessage.success("User updated")
    editModal.open = false
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to update user")
  } finally {
    editModal.loading = false
  }
}

async function removeUser(u) {
  try {
    await ElMessageBox.confirm(`Delete panel user ${u.display_name || u.username}? This removes only the panel identity. Their keys become no-owner and any machine accounts are left completely untouched (they simply become unmanaged/unlinked).`, "Delete user", { type: "warning", confirmButtonText: "Delete" })
  } catch {
    return
  }
  try {
    await usersAPI.remove(u.id)
    ElMessage.success("User deleted")
    await Promise.all([load(), loadNoOwner()])
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to delete user")
  }
}

async function openKeys(u) {
  keysModal.user = u
  keysModal.keys = []
  keysModal.open = true
  await reloadUserKeys()
}
async function reloadUserKeys() {
  keysModal.loading = true
  try {
    keysModal.keys = await keysAPI.list({ user_id: keysModal.user.id })
  } finally {
    keysModal.loading = false
  }
  load()
}
async function revokeUserKey(key) {
  try {
    await ElMessageBox.confirm("Revoke this key? It is removed from every machine account it is installed on.", "Revoke key", {
      type: "warning",
      confirmButtonText: "Revoke",
    })
  } catch {
    return
  }
  try {
    await keysAPI.revoke(key.id)
    ElMessage.success("Key revoked")
    await reloadUserKeys()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to revoke key")
  }
}

function openAssign(key) {
  assignModal.key = key
  assignModal.userId = ""
  assignModal.open = true
}
async function assignKey() {
  assignModal.loading = true
  try {
    await keysAPI.assign(assignModal.key.id, assignModal.userId)
    ElMessage.success("Key assigned")
    assignModal.open = false
    await Promise.all([loadNoOwner(), load()])
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to assign key")
  } finally {
    assignModal.loading = false
  }
}

onMounted(() => {
  load()
  loadNoOwner()
  loadAccessData()
})
</script>
