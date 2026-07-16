<template>
  <div class="container-page space-y-5">
    <header>
      <h1 class="page-title">Audit</h1>
      <p class="text-secondary mt-1">Security events and the full remote-action history.</p>
    </header>

    <!-- Remote actions -->
    <SectionCard title="Remote actions" icon="i-carbon-activity">
      <template #actions>
        <KSelect v-model="actionState" :options="actionStateOptions" @update:model-value="reloadActions" />
        <KButton variant="secondary" icon="i-carbon-refresh" @click="reloadActions">Reload</KButton>
      </template>
      <LoadingBlock v-if="loadingActions" :rows="4" />
      <template v-else>
        <ActionsTable v-if="actions.length" :actions="actions" show-retry @retry="retry" />
        <EmptyState v-else icon="i-carbon-activity" text="No actions match this filter" />
        <div v-if="actions.length && actionsMore" class="mt-3 text-center">
          <KButton variant="secondary" :loading="loadingMoreActions" @click="loadMoreActions">Load more</KButton>
        </div>
      </template>
    </SectionCard>

    <!-- Audit log -->
    <SectionCard title="Audit log" icon="i-carbon-catalog">
      <template #actions>
        <KInput v-model="auditAction" placeholder="filter by action…" @enter="reloadAudit" />
        <KButton variant="secondary" icon="i-carbon-search" @click="reloadAudit">Filter</KButton>
      </template>
      <LoadingBlock v-if="loadingAudit" :rows="4" />
      <template v-else>
        <div v-if="audit.length" class="table-wrap">
          <table class="table-base">
            <thead>
              <tr>
                <th class="th-cell">When</th>
                <th class="th-cell">Actor</th>
                <th class="th-cell">Action</th>
                <th class="th-cell">Target</th>
                <th class="th-cell">Detail</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in audit" :key="row.id" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30 align-top">
                <td class="td-cell whitespace-nowrap">
                  <span :title="fullTime(row.created_at)" class="text-xs text-warm-500 dark:text-warm-400">{{ fromNow(row.created_at) }}</span>
                </td>
                <td class="td-cell text-xs font-mono">{{ row.actor }}</td>
                <td class="td-cell">
                  <span class="mono-chip">{{ row.action }}</span>
                </td>
                <td class="td-cell text-xs">{{ row.target || "—" }}</td>
                <td class="td-cell text-xs text-warm-500 dark:text-warm-400 break-words max-w-sm">{{ row.detail || "—" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else icon="i-carbon-catalog" text="No audit entries" />
        <div v-if="audit.length && auditMore" class="mt-3 text-center">
          <KButton variant="secondary" :loading="loadingMoreAudit" @click="loadMoreAudit">Load more</KButton>
        </div>
      </template>
    </SectionCard>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue"

import { ElMessage } from "element-plus"

import ActionsTable from "@/components/machines/ActionsTable.vue"
import EmptyState from "@/components/common/EmptyState.vue"
import KButton from "@/components/common/KButton.vue"
import KInput from "@/components/common/KInput.vue"
import KSelect from "@/components/common/KSelect.vue"
import LoadingBlock from "@/components/common/LoadingBlock.vue"
import SectionCard from "@/components/common/SectionCard.vue"
import { actionsAPI, adminAPI } from "@/utils/api"
import { fromNow, fullTime } from "@/utils/format"

const PAGE = 50

const actions = ref([])
const audit = ref([])
const loadingActions = ref(true)
const loadingAudit = ref(true)
const loadingMoreActions = ref(false)
const loadingMoreAudit = ref(false)
const actionState = ref("")
const auditAction = ref("")
const actionsMore = ref(false)
const auditMore = ref(false)

const actionStateOptions = [
  { value: "", label: "All states" },
  { value: "pending", label: "Pending" },
  { value: "running", label: "Running" },
  { value: "succeeded", label: "Succeeded" },
  { value: "failed", label: "Failed" },
  { value: "interrupted", label: "Interrupted" },
]

async function reloadActions() {
  loadingActions.value = true
  try {
    const params = { limit: PAGE, offset: 0 }
    if (actionState.value) params.state = actionState.value
    actions.value = await actionsAPI.list(params)
    actionsMore.value = actions.value.length === PAGE
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to load actions")
  } finally {
    loadingActions.value = false
  }
}
async function loadMoreActions() {
  loadingMoreActions.value = true
  try {
    const params = { limit: PAGE, offset: actions.value.length }
    if (actionState.value) params.state = actionState.value
    const more = await actionsAPI.list(params)
    actions.value = actions.value.concat(more)
    actionsMore.value = more.length === PAGE
  } finally {
    loadingMoreActions.value = false
  }
}

async function reloadAudit() {
  loadingAudit.value = true
  try {
    const params = { limit: PAGE, offset: 0 }
    if (auditAction.value.trim()) params.action = auditAction.value.trim()
    audit.value = await adminAPI.audit(params)
    auditMore.value = audit.value.length === PAGE
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to load audit log")
  } finally {
    loadingAudit.value = false
  }
}
async function loadMoreAudit() {
  loadingMoreAudit.value = true
  try {
    const params = { limit: PAGE, offset: audit.value.length }
    if (auditAction.value.trim()) params.action = auditAction.value.trim()
    const more = await adminAPI.audit(params)
    audit.value = audit.value.concat(more)
    auditMore.value = more.length === PAGE
  } finally {
    loadingMoreAudit.value = false
  }
}

async function retry(a) {
  try {
    await actionsAPI.retry(a.id)
    ElMessage.success("Retry queued")
    await reloadActions()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to retry")
  }
}

onMounted(() => {
  reloadActions()
  reloadAudit()
})
</script>
