<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center gap-3">
      <div v-if="usage.total" class="flex items-baseline gap-2">
        <span class="text-2xl font-semibold text-warm-800 dark:text-warm-100">
          {{ humanBytes(usage.total.bytes) }}
        </span>
        <span class="text-xs text-warm-400 dark:text-warm-500">total used</span>
      </div>
      <StatusBadge v-if="usage.status" :state="usage.status" />
      <span v-if="usage.scanned_at" :title="fullTime(usage.scanned_at)" class="text-xs text-warm-400 dark:text-warm-500"> scanned {{ fromNow(usage.scanned_at) }} </span>
      <StatusBadge v-if="stale" state="stale" label="stale" />
    </div>

    <div v-if="usage.error" class="text-sm text-coral-shadow dark:text-coral-light">{{ usage.error }}</div>

    <div v-if="(usage.by_owner || []).length">
      <div class="field-label">By owner</div>
      <div class="table-wrap">
        <table class="table-base">
          <thead>
            <tr>
              <th class="th-cell">UID</th>
              <th class="th-cell">Owner (on machine)</th>
              <th class="th-cell">Panel user</th>
              <th class="th-cell text-right">Size</th>
              <th class="th-cell text-right">Files</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in usage.by_owner" :key="i" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30">
              <td class="td-cell font-mono text-xs">{{ row.uid ?? "—" }}</td>
              <td class="td-cell">{{ row.owner_name || "—" }}</td>
              <td class="td-cell">
                <span v-if="row.panel_user">{{ row.panel_user }}</span>
                <span v-else class="text-warm-400 text-xs">—</span>
              </td>
              <td class="td-cell text-right font-medium">{{ humanBytes(row.bytes) }}</td>
              <td class="td-cell text-right text-warm-500 dark:text-warm-400">{{ humanCount(row.file_count) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="(usage.by_directory || []).length">
      <div class="field-label">By directory</div>
      <div class="table-wrap">
        <table class="table-base">
          <thead>
            <tr>
              <th class="th-cell">Directory</th>
              <th class="th-cell text-right">Size</th>
              <th class="th-cell text-right">Files</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in usage.by_directory" :key="i" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30">
              <td class="td-cell font-mono text-xs break-all">{{ row.path }}</td>
              <td class="td-cell text-right font-medium">{{ humanBytes(row.bytes) }}</td>
              <td class="td-cell text-right text-warm-500 dark:text-warm-400">{{ humanCount(row.file_count) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue"

import StatusBadge from "@/components/common/StatusBadge.vue"
import { humanBytes, humanCount, fromNow, fullTime, isStale } from "@/utils/format"

const props = defineProps({
  usage: { type: Object, default: () => ({}) },
})

const stale = computed(() => isStale(props.usage?.scanned_at, 24 * 60))
</script>
