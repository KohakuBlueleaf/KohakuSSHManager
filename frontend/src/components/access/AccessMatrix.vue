<template>
  <div class="table-wrap">
    <table class="table-base">
      <thead>
        <tr>
          <th class="th-cell">Machine</th>
          <th class="th-cell">Account</th>
          <th class="th-cell">State</th>
          <th class="th-cell">Last result</th>
          <th class="th-cell">Updated</th>
          <th class="th-cell text-right">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.request_id" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30">
          <td class="td-cell font-medium">{{ row.machine_name || row.machine_id }}</td>
          <td class="td-cell">
            <span class="mono-chip">{{ row.username || "—" }}</span>
          </td>
          <td class="td-cell"><StatusBadge :state="row.state" /></td>
          <td class="td-cell max-w-xs">
            <span v-if="row.last_error" class="text-coral-shadow dark:text-coral-light text-xs break-words">
              {{ row.last_error }}
            </span>
            <span v-else class="text-warm-400 dark:text-warm-500 text-xs">—</span>
          </td>
          <td class="td-cell whitespace-nowrap">
            <span :title="fullTime(row.updated_at)" class="text-warm-500 dark:text-warm-400 text-xs">
              {{ fromNow(row.updated_at) }}
            </span>
          </td>
          <td class="td-cell text-right whitespace-nowrap">
            <button v-if="row.state === 'active'" class="btn-ghost text-coral-shadow dark:text-coral-light" @click="$emit('revoke', row)">Revoke</button>
            <span v-else class="text-warm-300 dark:text-warm-600 text-xs">—</span>
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
})

defineEmits(["revoke"])
</script>
