<template>
  <div class="table-wrap">
    <table class="table-base">
      <thead>
        <tr>
          <th class="th-cell">Action</th>
          <th class="th-cell">State</th>
          <th class="th-cell">Actor</th>
          <th class="th-cell">Detail</th>
          <th class="th-cell">When</th>
          <th v-if="showRetry" class="th-cell text-right">Retry</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in actions" :key="a.id" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30 align-top">
          <td class="td-cell">
            <div class="text-sm font-medium">{{ a.action }}</div>
            <div v-if="a.input_summary" class="text-[11px] text-warm-400 dark:text-warm-500">{{ a.input_summary }}</div>
          </td>
          <td class="td-cell"><StatusBadge :state="a.state" /></td>
          <td class="td-cell text-xs text-warm-500 dark:text-warm-400">{{ a.actor }}</td>
          <td class="td-cell max-w-sm">
            <span v-if="a.error" class="text-xs text-coral-shadow dark:text-coral-light break-words">{{ a.error }}</span>
            <span v-else class="text-xs text-warm-500 dark:text-warm-400 break-words">{{ resultText(a) }}</span>
          </td>
          <td class="td-cell whitespace-nowrap">
            <span :title="fullTime(a.started_at || a.created_at)" class="text-xs text-warm-500 dark:text-warm-400">
              {{ fromNow(a.finished_at || a.started_at || a.created_at) }}
            </span>
          </td>
          <td v-if="showRetry" class="td-cell text-right whitespace-nowrap">
            <button v-if="['failed', 'interrupted'].includes(a.state)" class="btn-ghost" @click="$emit('retry', a)">Retry</button>
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
  actions: { type: Array, default: () => [] },
  showRetry: { type: Boolean, default: false },
})

defineEmits(["retry"])

function resultText(a) {
  if (!a.result) return "—"
  if (typeof a.result === "string") return a.result
  try {
    return JSON.stringify(a.result)
  } catch {
    return "—"
  }
}
</script>
