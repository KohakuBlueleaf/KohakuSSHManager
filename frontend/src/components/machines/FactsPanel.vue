<template>
  <div v-if="!facts" class="text-sm text-warm-500 dark:text-warm-400">No facts collected yet. Enroll and refresh the machine to read its facts.</div>
  <div v-else class="space-y-4">
    <dl class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-3">
      <div v-for="f in factRows" :key="f.label">
        <dt class="text-xs uppercase tracking-wide text-warm-400 dark:text-warm-500">{{ f.label }}</dt>
        <dd class="text-sm text-warm-800 dark:text-warm-200 break-words">{{ f.value }}</dd>
      </div>
    </dl>

    <div v-if="gpus.length">
      <div class="field-label">GPUs</div>
      <div class="flex flex-wrap gap-2">
        <span v-for="(g, i) in gpus" :key="i" class="gem-badge bg-taaffeite-light text-taaffeite-shadow dark:bg-taaffeite-shadow/30 dark:text-taaffeite-light">
          {{ g.name }}<template v-if="g.memory_total"> · {{ g.memory_total }}</template>
        </span>
      </div>
    </div>

    <div v-if="mounts.length">
      <div class="field-label">Mounts</div>
      <div class="table-wrap">
        <table class="table-base">
          <thead>
            <tr>
              <th class="th-cell">Target</th>
              <th class="th-cell">Source</th>
              <th class="th-cell">Type</th>
              <th class="th-cell">Size</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(m, i) in mounts" :key="i">
              <td class="td-cell font-mono text-xs">{{ m.target }}</td>
              <td class="td-cell font-mono text-xs break-all">{{ m.source }}</td>
              <td class="td-cell">{{ m.fstype || "—" }}</td>
              <td class="td-cell">{{ m.size || "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue"

import { humanBytes } from "@/utils/format"

const props = defineProps({
  facts: { type: Object, default: null },
})

const factRows = computed(() => {
  const f = props.facts || {}
  const rows = [
    { label: "Hostname", value: f.hostname },
    { label: "OS", value: f.os },
    { label: "Kernel", value: f.kernel },
    { label: "CPU", value: f.cpu_model || f.cpu },
    { label: "CPU cores", value: f.cpu_count },
    { label: "Memory", value: f.mem_bytes ? humanBytes(f.mem_bytes) : f.mem },
  ]
  return rows.filter((r) => r.value !== undefined && r.value !== null && r.value !== "")
})

const gpus = computed(() => props.facts?.gpus || [])
const mounts = computed(() => props.facts?.mounts || [])
</script>
