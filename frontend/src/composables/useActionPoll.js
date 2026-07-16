import { ref, computed, onUnmounted } from "vue"

import { actionsAPI } from "@/utils/api"

const TERMINAL = ["succeeded", "failed", "interrupted"]
const INTERVAL_MS = 1500

/**
 * Poll a single RemoteAction until it reaches a terminal state.
 *
 * Usage:
 *   const { action, polling, done, failed, start } = useActionPoll()
 *   await start(actionId)   // resolves with the terminal action row
 *
 * The composable owns one in-flight poll at a time; calling ``start``
 * again cancels the previous timer. The timer is cleared on unmount.
 */
export function useActionPoll() {
  const action = ref(null)
  const polling = ref(false)
  let timer = null

  const done = computed(() => !!action.value && TERMINAL.includes(action.value.state))
  const failed = computed(
    () => !!action.value && ["failed", "interrupted"].includes(action.value.state),
  )

  function stop() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    polling.value = false
  }

  function start(actionId) {
    stop()
    action.value = null
    polling.value = true
    return new Promise((resolve) => {
      const tick = async () => {
        try {
          const row = await actionsAPI.get(actionId)
          action.value = row
          if (TERMINAL.includes(row.state)) {
            stop()
            resolve(row)
            return
          }
        } catch {
          // Transient poll error — keep trying on the next tick.
        }
        timer = setTimeout(tick, INTERVAL_MS)
      }
      tick()
    })
  }

  onUnmounted(stop)

  return { action, polling, done, failed, start, stop }
}
