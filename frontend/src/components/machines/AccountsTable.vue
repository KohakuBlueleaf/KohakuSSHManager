<template>
  <div class="table-wrap">
    <table class="table-base">
      <thead>
        <tr>
          <th class="th-cell">Account</th>
          <th class="th-cell">UID</th>
          <th class="th-cell">State</th>
          <th class="th-cell">Panel user</th>
          <th class="th-cell">Groups</th>
          <th class="th-cell">Keys</th>
          <th v-if="admin" class="th-cell text-right">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="acct in accounts" :key="acct.id" class="hover:bg-warm-50/60 dark:hover:bg-warm-800/30 align-top">
          <td class="td-cell">
            <div class="font-mono text-sm">{{ acct.username }}</div>
            <div class="text-[11px] text-warm-400 dark:text-warm-500 font-mono">{{ acct.home }}</div>
          </td>
          <td class="td-cell font-mono text-xs">{{ acct.uid ?? "—" }}</td>
          <td class="td-cell">
            <div class="flex flex-wrap items-center gap-1">
              <span v-if="acct.is_management" class="gem-badge bg-iolite/15 text-iolite dark:bg-iolite/25 dark:text-iolite-light" title="Kohaku connects to this machine through this account"> management </span>
              <StatusBadge :state="acct.state" />
              <StatusBadge v-if="acct.present === false" state="absent" label="absent" />
              <span v-if="acct.locked" class="gem-badge bg-warm-200/70 text-warm-600 dark:bg-warm-700/50 dark:text-warm-300"> locked </span>
            </div>
          </td>
          <td class="td-cell">
            <span v-if="acct.user" class="text-sm">
              {{ acct.user.display_name || acct.user.username }}
            </span>
            <span v-else class="text-warm-400 dark:text-warm-500 text-xs">unlinked</span>
          </td>
          <td class="td-cell">
            <div class="flex flex-wrap gap-1 max-w-[14rem]">
              <span v-for="g in acct.groups || []" :key="g" class="mono-chip">{{ g }}</span>
              <span v-if="!(acct.groups || []).length" class="text-warm-400 text-xs">—</span>
            </div>
          </td>
          <td class="td-cell">
            <span class="text-sm">{{ (acct.keys || []).length }}</span>
            <span v-if="noOwnerCount(acct)" class="ml-1 gem-badge bg-warm-200/70 text-warm-600 dark:bg-warm-700/50 dark:text-warm-300" :title="`${noOwnerCount(acct)} key(s) with no linked panel user`"> {{ noOwnerCount(acct) }} no owner </span>
          </td>
          <td v-if="admin" class="td-cell text-right whitespace-nowrap">
            <span v-if="acct.is_management" class="text-warm-400 dark:text-warm-500 text-xs italic">protected</span>
            <el-dropdown v-else trigger="click" @command="(cmd) => $emit(cmd, acct)">
              <button class="btn-ghost inline-flex items-center gap-1">Manage <span class="i-carbon-chevron-down" /></button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-if="!acct.user" command="adopt">Adopt → link user</el-dropdown-item>
                  <el-dropdown-item v-if="acct.user" command="unlink">Unlink panel user</el-dropdown-item>
                  <el-dropdown-item command="groups">Set groups…</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>Delete account…</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import StatusBadge from "@/components/common/StatusBadge.vue"

defineProps({
  accounts: { type: Array, default: () => [] },
  admin: { type: Boolean, default: false },
})

defineEmits(["adopt", "unlink", "groups", "delete"])

function noOwnerCount(acct) {
  return (acct.keys || []).filter((k) => k.state === "no_owner" || !k.user_id).length
}
</script>
