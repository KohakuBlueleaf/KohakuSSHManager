<template>
  <div class="container-page space-y-5">
    <header>
      <h1 class="page-title">Groups</h1>
      <p class="text-secondary mt-1">Leader scope — which users may auto-approve access to which machines.</p>
    </header>

    <SectionCard title="Create group" icon="i-carbon-group">
      <form class="grid grid-cols-1 sm:grid-cols-2 gap-3" @submit.prevent="createGroup">
        <KField label="Name" required><KInput v-model="form.name" placeholder="e.g. vision-team" /></KField>
        <KField label="Description"><KInput v-model="form.description" placeholder="Optional" /></KField>
        <div class="sm:col-span-2 flex justify-end">
          <KButton variant="primary" :loading="creating" :disabled="!form.name.trim()" @click="createGroup">Create group</KButton>
        </div>
      </form>
    </SectionCard>

    <LoadingBlock v-if="loading" :rows="4" />
    <template v-else>
      <EmptyState v-if="!groups.length" icon="i-carbon-group" text="No groups yet" hint="Create one above." />
      <SectionCard v-for="g in groups" :key="g.id" :title="g.name" :subtitle="g.description">
        <template #actions>
          <button class="btn-ghost text-coral-shadow dark:text-coral-light" @click="removeGroup(g)">Delete</button>
        </template>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <!-- Members -->
          <div>
            <div class="field-label">Members</div>
            <div class="flex flex-wrap gap-2 mb-3">
              <span v-for="m in g.members || []" :key="m.id" class="gem-badge bg-warm-200/70 text-warm-700 dark:bg-warm-700/50 dark:text-warm-200 gap-1">
                {{ m.display_name || m.username }}
                <button class="i-carbon-close hover:text-coral" @click="removeMember(g, m)" />
              </span>
              <span v-if="!(g.members || []).length" class="text-warm-400 text-xs">No members</span>
            </div>
            <div class="flex gap-2">
              <KSelect v-model="pick.member[g.id]" :options="memberOptions(g)" placeholder="Add member…" />
              <KButton variant="secondary" :disabled="!pick.member[g.id]" @click="addMember(g)">Add</KButton>
            </div>
          </div>

          <!-- Machines -->
          <div>
            <div class="field-label">Machines</div>
            <div class="flex flex-wrap gap-2 mb-3">
              <span v-for="mc in g.machines || []" :key="mc.id" class="gem-badge bg-iolite-light text-iolite-shadow dark:bg-iolite-shadow/30 dark:text-iolite-light gap-1">
                {{ mc.name }}
                <button class="i-carbon-close hover:text-coral" @click="removeMachine(g, mc)" />
              </span>
              <span v-if="!(g.machines || []).length" class="text-warm-400 text-xs">No machines</span>
            </div>
            <div class="flex gap-2">
              <KSelect v-model="pick.machine[g.id]" :options="machineOptions(g)" placeholder="Add machine…" />
              <KButton variant="secondary" :disabled="!pick.machine[g.id]" @click="addMachine(g)">Add</KButton>
            </div>
          </div>
        </div>
      </SectionCard>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue"

import { ElMessage, ElMessageBox } from "element-plus"

import EmptyState from "@/components/common/EmptyState.vue"
import KButton from "@/components/common/KButton.vue"
import KField from "@/components/common/KField.vue"
import KInput from "@/components/common/KInput.vue"
import KSelect from "@/components/common/KSelect.vue"
import LoadingBlock from "@/components/common/LoadingBlock.vue"
import SectionCard from "@/components/common/SectionCard.vue"
import { groupsAPI, usersAPI, machinesAPI } from "@/utils/api"

const groups = ref([])
const users = ref([])
const machines = ref([])
const loading = ref(true)
const creating = ref(false)

const form = reactive({ name: "", description: "" })
// Per-group selected value for the add-member / add-machine pickers.
const pick = reactive({ member: {}, machine: {} })

function memberOptions(g) {
  const has = new Set((g.members || []).map((m) => m.id))
  return users.value.filter((u) => !has.has(u.id)).map((u) => ({ value: u.id, label: u.display_name || u.username }))
}
function machineOptions(g) {
  const has = new Set((g.machines || []).map((m) => m.id))
  return machines.value.filter((m) => !has.has(m.id)).map((m) => ({ value: m.id, label: m.name }))
}

async function load() {
  loading.value = true
  try {
    const [gs, us, ms] = await Promise.all([groupsAPI.list(), usersAPI.list(), machinesAPI.list()])
    groups.value = gs
    users.value = us
    machines.value = ms
  } finally {
    loading.value = false
  }
}

async function createGroup() {
  if (!form.name.trim()) return
  creating.value = true
  try {
    await groupsAPI.create({ name: form.name.trim(), description: form.description.trim() })
    ElMessage.success("Group created")
    form.name = ""
    form.description = ""
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to create group")
  } finally {
    creating.value = false
  }
}

async function removeGroup(g) {
  try {
    await ElMessageBox.confirm(`Delete group ${g.name}? Members and machines are unassigned; nothing else changes.`, "Delete group", {
      type: "warning",
      confirmButtonText: "Delete",
    })
  } catch {
    return
  }
  try {
    await groupsAPI.remove(g.id)
    ElMessage.success("Group deleted")
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to delete group")
  }
}

async function addMember(g) {
  const userId = pick.member[g.id]
  if (!userId) return
  try {
    await groupsAPI.addMember(g.id, userId)
    pick.member[g.id] = ""
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to add member")
  }
}
async function removeMember(g, m) {
  try {
    await groupsAPI.removeMember(g.id, m.id)
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to remove member")
  }
}

async function addMachine(g) {
  const machineId = pick.machine[g.id]
  if (!machineId) return
  try {
    await groupsAPI.addMachine(g.id, machineId)
    pick.machine[g.id] = ""
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to add machine")
  }
}
async function removeMachine(g, mc) {
  try {
    await groupsAPI.removeMachine(g.id, mc.id)
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to remove machine")
  }
}

onMounted(load)
</script>
