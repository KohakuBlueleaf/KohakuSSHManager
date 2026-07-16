<template>
  <div class="table-wrap">
    <table class="table-base">
      <thead>
        <tr>
          <th v-if="admin" class="th-cell">Requester</th>
          <th class="th-cell">Machine</th>
          <th class="th-cell">Account</th>
          <th class="th-cell">State</th>
          <th class="th-cell">Reason</th>
          <th class="th-cell">Requested</th>
          <th class="th-cell text-right">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30">
          <td v-if="admin" class="td-cell">{{ row.requested_by || row.user_name || "—" }}</td>
          <td class="td-cell font-medium">{{ row.machine_name || row.machine_id }}</td>
          <td class="td-cell">
            <span class="mono-chip">{{ row.username || "—" }}</span>
          </td>
          <td class="td-cell"><StatusBadge :state="row.state" /></td>
          <td class="td-cell max-w-xs">
            <span class="text-xs text-warm-500 dark:text-warm-400 break-words">
              {{ row.last_error || row.reason || "—" }}
            </span>
          </td>
          <td class="td-cell whitespace-nowrap">
            <span :title="fullTime(row.created_at)" class="text-xs text-warm-500 dark:text-warm-400">
              {{ fromNow(row.created_at) }}
            </span>
          </td>
          <td class="td-cell text-right whitespace-nowrap space-x-1">
            <template v-if="admin && row.state === 'pending'">
              <button class="btn-ghost text-aquamarine-shadow dark:text-aquamarine-light" @click="$emit('approve', row)">Approve</button>
              <button class="btn-ghost text-coral-shadow dark:text-coral-light" @click="$emit('reject', row)">Reject</button>
            </template>
            <button v-if="row.state === 'active'" class="btn-ghost text-coral-shadow dark:text-coral-light" @click="$emit('revoke', row)">Revoke</button>
            <span v-if="!(admin && row.state === 'pending') && row.state !== 'active'" class="text-warm-300 dark:text-warm-600 text-xs"> — </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import StatusBadge from "@/components/common/StatusBadge.vue"
import { fromNow, fullTime } from "@/utils/format"

defineProps({
  rows: { type: Array, default: () => [] },
  admin: { type: Boolean, default: false },
})

defineEmits(["approve", "reject", "revoke"])
</script>
