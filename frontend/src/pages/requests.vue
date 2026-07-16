<template>
  <div class="container-page space-y-5">
    <header>
      <h1 class="page-title">Access requests</h1>
      <p class="text-secondary mt-1">Review pending requests and manage active grants.</p>
    </header>

    <SectionCard title="Pending review" icon="i-carbon-hourglass" :subtitle="pending.length ? `${pending.length} awaiting a decision` : ''">
      <LoadingBlock v-if="loading" />
      <template v-else>
        <RequestTable v-if="pending.length" :rows="pending" admin @approve="approve" @reject="reject" @revoke="revoke" />
        <EmptyState v-else icon="i-carbon-checkmark-outline" text="Nothing pending" hint="Approved and automatic requests appear below." />
      </template>
    </SectionCard>

    <SectionCard title="All requests" icon="i-carbon-list">
      <template #actions>
        <KSelect v-model="stateFilter" :options="stateOptions" @update:model-value="load" />
      </template>
      <LoadingBlock v-if="loading" />
      <template v-else>
        <RequestTable v-if="requests.length" :rows="requests" admin @approve="approve" @reject="reject" @revoke="revoke" />
        <EmptyState v-else icon="i-carbon-list" text="No requests match this filter" />
      </template>
    </SectionCard>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue"

import { ElMessage, ElMessageBox } from "element-plus"

import EmptyState from "@/components/common/EmptyState.vue"
import KSelect from "@/components/common/KSelect.vue"
import LoadingBlock from "@/components/common/LoadingBlock.vue"
import SectionCard from "@/components/common/SectionCard.vue"
import RequestTable from "@/components/access/RequestTable.vue"
import { accessAPI } from "@/utils/api"

const requests = ref([])
const loading = ref(true)
const stateFilter = ref("")

const stateOptions = [
  { value: "", label: "All states" },
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "active", label: "Active" },
  { value: "failed", label: "Failed" },
  { value: "rejected", label: "Rejected" },
  { value: "revoked", label: "Revoked" },
]

const pending = computed(() => requests.value.filter((r) => r.state === "pending"))

async function load() {
  loading.value = true
  try {
    const params = {}
    if (stateFilter.value) params.state = stateFilter.value
    requests.value = await accessAPI.listRequests(params)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to load requests")
  } finally {
    loading.value = false
  }
}

async function approve(row) {
  try {
    await accessAPI.approve(row.id)
    ElMessage.success("Request approved — provisioning underway")
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to approve")
  }
}

async function reject(row) {
  let reason
  try {
    const res = await ElMessageBox.prompt("Reason for rejection (shown to the requester):", "Reject request", {
      confirmButtonText: "Reject",
      inputPlaceholder: "e.g. not authorized for this machine",
    })
    reason = res.value
  } catch {
    return
  }
  try {
    await accessAPI.reject(row.id, reason || "")
    ElMessage.success("Request rejected")
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to reject")
  }
}

async function revoke(row) {
  try {
    await ElMessageBox.confirm("Revoke this active access? The user's managed keys are removed from the account; the account and its data stay in place.", "Revoke access", { type: "warning", confirmButtonText: "Revoke" })
  } catch {
    return
  }
  try {
    await accessAPI.revoke(row.id)
    ElMessage.success("Access revoked")
    await load()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to revoke")
  }
}

onMounted(load)
</script>
