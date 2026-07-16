<template>
  <div class="container-page space-y-5">
    <header class="flex items-center justify-between gap-3">
      <div>
        <h1 class="page-title">Machines</h1>
        <p class="text-secondary mt-1">Managed machines and their connectivity.</p>
      </div>
      <KButton v-if="auth.isAdmin" variant="secondary" icon="i-carbon-refresh" @click="load"> Reload </KButton>
    </header>

    <SectionCard>
      <LoadingBlock v-if="loading" :rows="4" />
      <template v-else>
        <div v-if="machines.length" class="table-wrap">
          <table class="table-base">
            <thead>
              <tr>
                <th class="th-cell">Name</th>
                <th v-if="auth.isLeader" class="th-cell">Address</th>
                <th class="th-cell">Tags</th>
                <th class="th-cell">Status</th>
                <th class="th-cell">Last check</th>
                <th class="th-cell text-right"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in machines" :key="m.id" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30 cursor-pointer" @click="open(m)">
                <td class="td-cell">
                  <div class="font-medium">{{ m.name }}</div>
                  <div v-if="m.facts?.os" class="text-[11px] text-warm-400 dark:text-warm-500">{{ m.facts.os }}</div>
                </td>
                <td v-if="auth.isLeader" class="td-cell font-mono text-xs">
                  {{ m.address }}<template v-if="m.port && m.port !== 22">:{{ m.port }}</template>
                </td>
                <td class="td-cell">
                  <div class="flex flex-wrap gap-1">
                    <span v-for="t in m.tags || []" :key="t" class="mono-chip">{{ t }}</span>
                    <span v-if="!(m.tags || []).length" class="text-warm-400 text-xs">—</span>
                  </div>
                </td>
                <td class="td-cell">
                  <div class="flex items-center gap-1">
                    <StatusBadge :state="m.status" dot />
                    <StatusBadge v-if="isStaleMachine(m)" state="stale" label="stale" />
                  </div>
                </td>
                <td class="td-cell whitespace-nowrap">
                  <span :title="fullTime(m.last_check_at)" class="text-xs text-warm-500 dark:text-warm-400">
                    {{ m.last_check_at ? fromNow(m.last_check_at) : "never" }}
                  </span>
                </td>
                <td class="td-cell text-right">
                  <span class="i-carbon-chevron-right text-warm-400" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else icon="i-carbon-bare-metal-server" text="No machines registered" :hint="auth.isAdmin ? 'Register one below.' : 'Ask an admin to register machines.'" />
      </template>
    </SectionCard>

    <template v-if="auth.isAdmin">
      <SectionCard title="Register a machine" icon="i-carbon-add-alt">
        <RegisterForm @created="onCreated" />
      </SectionCard>

      <SectionCard title="Shared management key" icon="i-carbon-key">
        <ManagementKeyCard />
      </SectionCard>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"

import EmptyState from "@/components/common/EmptyState.vue"
import KButton from "@/components/common/KButton.vue"
import LoadingBlock from "@/components/common/LoadingBlock.vue"
import SectionCard from "@/components/common/SectionCard.vue"
import StatusBadge from "@/components/common/StatusBadge.vue"
import ManagementKeyCard from "@/components/machines/ManagementKeyCard.vue"
import RegisterForm from "@/components/machines/RegisterForm.vue"
import { useAuthStore } from "@/stores/auth"
import { machinesAPI } from "@/utils/api"
import { fromNow, fullTime, isStale } from "@/utils/format"

const auth = useAuthStore()
const router = useRouter()

const machines = ref([])
const loading = ref(true)

function isStaleMachine(m) {
  // An online machine whose last check is old enough is worth flagging.
  return m.status === "online" && isStale(m.last_check_at, 30)
}

async function load() {
  loading.value = true
  try {
    machines.value = await machinesAPI.list()
  } finally {
    loading.value = false
  }
}

function open(m) {
  router.push(`/machines/${m.id}`)
}

function onCreated(m) {
  load()
  if (m?.id) router.push(`/machines/${m.id}`)
}

onMounted(load)
</script>
