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
              <tr v-for="u in users" :key="u.id" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30">
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
                  <button class="btn-ghost" @click="openKeys(u)">Keys</button>
                  <button class="btn-ghost" @click="openEdit(u)">Edit</button>
                  <button class="btn-ghost text-coral-shadow dark:text-coral-light" @click="removeUser(u)">Delete</button>
                </td>
              </tr>
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
            <AddKeyForm :user-id="keysModal.user?.id" :show-install="false" @added="reloadUserKeys" />
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
import { usersAPI, keysAPI } from "@/utils/api"

const roleOptions = [
  { value: "member", label: "member" },
  { value: "leader", label: "leader" },
]

const users = ref([])
const noOwnerKeys = ref([])
const loading = ref(true)
const loadingNoOwner = ref(true)

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
})
</script>
