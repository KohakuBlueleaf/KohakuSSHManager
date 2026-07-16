<template>
  <div class="table-wrap">
    <table class="table-base">
      <thead>
        <tr>
          <th class="th-cell">Fingerprint</th>
          <th class="th-cell">Comment</th>
          <th class="th-cell">State</th>
          <th v-if="showActions" class="th-cell text-right">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="key in keys" :key="key.id" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30">
          <td class="td-cell">
            <span class="font-mono text-xs break-all">{{ key.fingerprint }}</span>
          </td>
          <td class="td-cell">
            <span class="text-warm-600 dark:text-warm-400">{{ key.comment || "—" }}</span>
          </td>
          <td class="td-cell">
            <StatusBadge :state="key.state" />
          </td>
          <td v-if="showActions" class="td-cell text-right whitespace-nowrap">
            <button v-if="key.state === 'active' && revocable" class="btn-ghost text-coral-shadow dark:text-coral-light" @click="$emit('revoke', key)">Revoke</button>
            <button v-if="assignable && key.state === 'no_owner'" class="btn-ghost" @click="$emit('assign', key)">Assign</button>
            <button v-if="deletable && key.state !== 'active'" class="btn-ghost text-coral-shadow dark:text-coral-light" @click="$emit('delete', key)">Delete</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { computed } from "vue"

import StatusBadge from "@/components/common/StatusBadge.vue"

const props = defineProps({
  keys: { type: Array, default: () => [] },
  revocable: { type: Boolean, default: true },
  assignable: { type: Boolean, default: false },
  deletable: { type: Boolean, default: false },
})

defineEmits(["revoke", "assign", "delete"])

const showActions = computed(() => props.revocable || props.assignable || props.deletable)
</script>
