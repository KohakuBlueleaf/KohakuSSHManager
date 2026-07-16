<template>
  <div class="container-page space-y-5">
    <header class="flex items-end justify-between gap-3">
      <div>
        <h1 class="page-title">Admin dashboard</h1>
        <p class="text-secondary mt-1">Fleet health, pending work, and recent activity.</p>
      </div>
      <button class="btn-ghost inline-flex items-center gap-1.5 text-sm shrink-0" :disabled="loading" @click="loadAll">
        <span class="i-carbon-refresh" :class="loading && 'animate-spin'" />
        Refresh
      </button>
    </header>

    <!-- Status tiles -->
    <div class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
      <component :is="tile.to ? 'router-link' : 'div'" v-for="tile in tiles" :key="tile.label" :to="tile.to" class="card p-4 block" :class="tile.to && 'card-hover'">
        <div class="flex items-center gap-2 text-secondary">
          <span :class="tile.icon" class="text-base" />
          <span class="text-xs font-medium uppercase tracking-wide">{{ tile.label }}</span>
        </div>
        <div class="mt-2 text-2xl font-semibold text-warm-800 dark:text-warm-100">{{ tile.value }}</div>
        <div class="mt-1 text-xs text-warm-500 dark:text-warm-400 min-h-[1rem]">{{ tile.sub }}</div>
      </component>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <!-- Pending requests quick list -->
      <SectionCard title="Pending requests" icon="i-carbon-task">
        <LoadingBlock v-if="loading" />
        <template v-else>
          <div v-if="pending.length" class="space-y-2">
            <div v-for="req in pending" :key="req.id" class="flex items-center justify-between gap-3 rounded-lg border border-warm-200/60 dark:border-warm-700/60 px-3 py-2">
              <div class="min-w-0">
                <div class="text-sm truncate">
                  <span class="font-medium">{{ req.requested_by }}</span>
                  <span class="text-warm-400"> → </span>
                  <span class="font-mono">{{ req.username }}</span>
                  <span class="text-warm-400"> @ </span>
                  <span>{{ req.machine_name }}</span>
                </div>
                <div class="text-[11px] text-warm-500 dark:text-warm-400" :title="fullTime(req.created_at)">{{ fromNow(req.created_at) }}</div>
              </div>
              <div class="flex items-center gap-1 shrink-0">
                <KButton variant="primary" :loading="busy === req.id" @click="approve(req)">Approve</KButton>
                <KButton variant="secondary" :disabled="busy === req.id" @click="reject(req)">Reject</KButton>
              </div>
            </div>
          </div>
          <EmptyState v-else icon="i-carbon-checkmark-outline" text="No pending requests" hint="Everything is reviewed." />
        </template>
      </SectionCard>

      <!-- Machine status -->
      <SectionCard title="Machine status" icon="i-carbon-bare-metal-server">
        <LoadingBlock v-if="loading" />
        <template v-else>
          <div v-if="machines.length" class="space-y-1.5 max-h-80 overflow-y-auto">
            <router-link v-for="m in machines" :key="m.id" :to="`/machines/${m.id}`" class="flex items-center justify-between gap-3 rounded-lg px-3 py-1.5 hover:bg-warm-50/60 dark:hover:bg-warm-800/30">
              <span class="text-sm font-medium truncate">{{ m.name }}</span>
              <span class="flex items-center gap-2 shrink-0">
                <StatusBadge v-if="isStaleMachine(m)" state="stale" label="stale" />
                <StatusBadge :state="m.status" :dot="true" />
              </span>
            </router-link>
          </div>
          <EmptyState v-else icon="i-carbon-bare-metal-server" text="No machines yet" hint="Register machines to see their status." />
        </template>
      </SectionCard>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <!-- Recent activity (remote actions) -->
      <SectionCard title="Recent activity" icon="i-carbon-activity">
        <LoadingBlock v-if="loading" />
        <template v-else>
          <div v-if="actions.length" class="space-y-1">
            <div v-for="a in actions" :key="a.id" class="flex items-center justify-between gap-3 py-1 text-sm">
              <span class="min-w-0 truncate">
                <span class="font-mono text-xs text-warm-500 dark:text-warm-400">{{ a.action }}</span>
                <span class="text-warm-400"> · </span>
                <span class="text-warm-600 dark:text-warm-300">{{ a.input_summary || a.machine?.name || "—" }}</span>
              </span>
              <span class="flex items-center gap-2 shrink-0">
                <StatusBadge :state="a.state" />
                <span class="text-[11px] text-warm-400" :title="fullTime(a.created_at)">{{ fromNow(a.finished_at || a.created_at) }}</span>
              </span>
            </div>
          </div>
          <EmptyState v-else icon="i-carbon-activity" text="No activity yet" />
        </template>
      </SectionCard>

      <!-- Audit log -->
      <SectionCard title="Latest log" icon="i-carbon-catalog">
        <LoadingBlock v-if="loading" />
        <template v-else>
          <div v-if="auditRows.length" class="space-y-1">
            <div v-for="row in auditRows" :key="row.id" class="flex items-center justify-between gap-3 py-1 text-sm">
              <span class="min-w-0 truncate">
                <span class="font-medium">{{ row.actor }}</span>
                <span class="text-warm-400"> · </span>
                <span class="text-warm-600 dark:text-warm-300">{{ row.action }}</span>
                <span v-if="row.target" class="text-warm-400"> · {{ row.target }}</span>
              </span>
              <span class="text-[11px] text-warm-400 shrink-0" :title="fullTime(row.created_at)">{{ fromNow(row.created_at) }}</span>
            </div>
          </div>
          <EmptyState v-else icon="i-carbon-catalog" text="No log entries" />
        </template>
      </SectionCard>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue"

import { ElMessage, ElMessageBox } from "element-plus"

import EmptyState from "@/components/common/EmptyState.vue"
import KButton from "@/components/common/KButton.vue"
import LoadingBlock from "@/components/common/LoadingBlock.vue"
import SectionCard from "@/components/common/SectionCard.vue"
import StatusBadge from "@/components/common/StatusBadge.vue"
import { adminAPI, accessAPI, actionsAPI, machinesAPI } from "@/utils/api"
import { fromNow, fullTime, isStale } from "@/utils/format"

const loading = ref(true)
const busy = ref(null)
const overview = ref({})
const pending = ref([])
const machines = ref([])
const actions = ref([])
const auditRows = ref([])

const tiles = computed(() => {
  const o = overview.value
  const m = o.machines_by_status || {}
  const k = o.keys_by_state || {}
  const r = o.users_by_role || {}
  return [
    {
      label: "Users",
      value: o.users_total ?? "—",
      sub: `${r.member || 0} member · ${r.leader || 0} leader${o.users_disabled ? ` · ${o.users_disabled} disabled` : ""}`,
      icon: "i-carbon-user-multiple",
      to: "/users",
    },
    {
      label: "Machines",
      value: o.machines_total ?? "—",
      sub: `${m.online || 0} online · ${m.offline || 0} offline · ${m.error || 0} error · ${m.new || 0} new`,
      icon: "i-carbon-bare-metal-server",
      to: "/machines",
    },
    {
      label: "SSH keys",
      value: o.keys_total ?? "—",
      sub: `${k.active || 0} active · ${k.revoked || 0} revoked · ${k.no_owner || 0} no owner`,
      icon: "i-carbon-password",
      to: null,
    },
    {
      label: "Pending requests",
      value: o.pending_requests ?? "—",
      sub: "awaiting review",
      icon: "i-carbon-task",
      to: "/requests",
    },
    {
      label: "Failed actions",
      value: o.failed_actions_24h ?? "—",
      sub: "in the last 24h",
      icon: "i-carbon-warning-alt",
      to: "/audit",
    },
  ]
})

function isStaleMachine(m) {
  // Only enrolled, currently-online machines can look "stale" (old last check).
  return m.status === "online" && isStale(m.last_check_at, 15)
}

async function loadAll() {
  loading.value = true
  try {
    const [ov, pend, mach, acts, aud] = await Promise.all([adminAPI.overview().catch(() => ({})), accessAPI.listRequests({ state: "pending" }).catch(() => []), machinesAPI.list().catch(() => []), actionsAPI.list({ limit: 8 }).catch(() => []), adminAPI.audit({ limit: 8 }).catch(() => [])])
    overview.value = ov
    pending.value = pend
    machines.value = mach
    actions.value = acts
    auditRows.value = aud
  } finally {
    loading.value = false
  }
}

async function approve(req) {
  busy.value = req.id
  try {
    await accessAPI.approve(req.id)
    ElMessage.success("Approved")
    await loadAll()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to approve")
  } finally {
    busy.value = null
  }
}

async function reject(req) {
  let reason = ""
  try {
    const res = await ElMessageBox.prompt("Reason for rejection (optional)", "Reject request", {
      confirmButtonText: "Reject",
      inputPlaceholder: "e.g. not in your group",
    })
    reason = res.value || ""
  } catch {
    return
  }
  busy.value = req.id
  try {
    await accessAPI.reject(req.id, reason)
    ElMessage.success("Rejected")
    await loadAll()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to reject")
  } finally {
    busy.value = null
  }
}

onMounted(loadAll)
</script>
