<template>
  <span class="gem-badge" :class="[colorClass, pulse && 'kohaku-pulse']">
    <span v-if="dot" class="w-1.5 h-1.5 rounded-full mr-1.5" :class="dotClass" />
    {{ text }}
  </span>
</template>

<script setup>
import { computed } from "vue"

// One badge for every state string the API emits. Color semantics (spec §12):
//   aquamarine = active / online / succeeded / ok / managed
//   amber      = pending / running / new / stale / approved
//   coral      = failed / error / offline / rejected / absent
//   warm       = revoked / unmanaged / no_owner / interrupted (neutral/inactive)
//   sapphire   = adopted (informational)
const props = defineProps({
  state: { type: String, default: "" },
  label: { type: String, default: "" },
  dot: { type: Boolean, default: false },
})

const GEM_BY_STATE = {
  active: "aquamarine",
  online: "aquamarine",
  succeeded: "aquamarine",
  ok: "aquamarine",
  managed: "aquamarine",
  pending: "amber",
  running: "amber",
  new: "amber",
  stale: "amber",
  approved: "amber",
  idle: "amber",
  failed: "coral",
  error: "coral",
  offline: "coral",
  rejected: "coral",
  absent: "coral",
  revoked: "warm",
  unmanaged: "warm",
  no_owner: "warm",
  interrupted: "warm",
  skipped: "warm",
  adopted: "sapphire",
  archived: "aquamarine",
}

const LABEL_BY_STATE = {
  no_owner: "no owner",
}

const COLOR_CLASS = {
  sapphire: "bg-sapphire-light text-sapphire-shadow dark:bg-sapphire-shadow/30 dark:text-sapphire-light",
  aquamarine: "bg-aquamarine-light text-aquamarine-shadow dark:bg-aquamarine-shadow/30 dark:text-aquamarine-light",
  amber: "bg-amber-light text-amber-shadow dark:bg-amber-shadow/30 dark:text-amber-light",
  coral: "bg-coral-light text-coral-shadow dark:bg-coral-shadow/30 dark:text-coral-light",
  warm: "bg-warm-200/70 text-warm-600 dark:bg-warm-700/50 dark:text-warm-300",
}

const DOT_CLASS = {
  sapphire: "bg-sapphire",
  aquamarine: "bg-aquamarine",
  amber: "bg-amber",
  coral: "bg-coral",
  warm: "bg-warm-400",
}

const gem = computed(() => GEM_BY_STATE[props.state] || "warm")
const colorClass = computed(() => COLOR_CLASS[gem.value])
const dotClass = computed(() => DOT_CLASS[gem.value])
const pulse = computed(() => ["running", "pending"].includes(props.state))
const text = computed(() => props.label || LABEL_BY_STATE[props.state] || props.state || "—")
</script>
