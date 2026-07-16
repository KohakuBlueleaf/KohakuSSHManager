<template>
  <div v-if="!rows.length" class="text-sm text-warm-500 dark:text-warm-400">No public keys observed on this machine yet.</div>
  <div v-else class="table-wrap">
    <table class="table-base">
      <thead>
        <tr>
          <th class="th-cell">Fingerprint</th>
          <th class="th-cell">Account</th>
          <th class="th-cell">Owner</th>
          <th class="th-cell">Origin</th>
          <th class="th-cell">State</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in rows" :key="i" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30">
          <td class="td-cell">
            <div class="font-mono text-xs break-all">{{ row.fingerprint }}</div>
            <div v-if="row.comment" class="text-[11px] text-warm-400 dark:text-warm-500">{{ row.comment }}</div>
          </td>
          <td class="td-cell">
            <span class="mono-chip">{{ row.account_username }}</span>
          </td>
          <td class="td-cell">
            <span v-if="row.owner_name" class="text-sm">{{ row.owner_name }}</span>
            <StatusBadge v-else state="no_owner" label="no owner" />
          </td>
          <td class="td-cell text-xs text-warm-500 dark:text-warm-400">{{ row.origin || "—" }}</td>
          <td class="td-cell">
            <div class="flex flex-wrap gap-1">
              <span v-if="row.managed" class="gem-badge bg-aquamarine-light text-aquamarine-shadow dark:bg-aquamarine-shadow/30 dark:text-aquamarine-light"> managed </span>
              <StatusBadge v-if="row.observed === false" state="stale" label="not observed" />
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { computed } from "vue"

import StatusBadge from "@/components/common/StatusBadge.vue"

// Flattens the per-account observed keys into one list, labeling any key
// with no linked panel user as "no owner".
const props = defineProps({
  accounts: { type: Array, default: () => [] },
})

const rows = computed(() => {
  const out = []
  for (const acct of props.accounts) {
    for (const key of acct.keys || []) {
      out.push({
        fingerprint: key.fingerprint,
        comment: key.comment,
        account_username: acct.username,
        owner_name: key.owner_name || key.user?.display_name || key.user?.username || null,
        origin: key.origin,
        managed: key.managed,
        observed: key.observed,
      })
    }
  }
  return out
})
</script>
