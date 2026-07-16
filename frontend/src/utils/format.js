import dayjs from "dayjs"
import relativeTime from "dayjs/plugin/relativeTime"
import utc from "dayjs/plugin/utc"

dayjs.extend(relativeTime)
dayjs.extend(utc)

// The backend emits ISO-8601 UTC with a trailing Z. Parse as UTC, then
// let dayjs render in the viewer's local zone.
function parse(ts) {
  if (!ts) return null
  const d = dayjs.utc(ts)
  return d.isValid() ? d.local() : null
}

/** Relative time ("3 minutes ago"). Falls back to an em-dash. */
export function fromNow(ts) {
  const d = parse(ts)
  return d ? d.fromNow() : "—"
}

/** Full absolute timestamp for a title/tooltip attribute. */
export function fullTime(ts) {
  const d = parse(ts)
  return d ? d.format("YYYY-MM-DD HH:mm:ss") : ""
}

/** Short absolute date-time ("2026-07-17 14:03"). */
export function shortTime(ts) {
  const d = parse(ts)
  return d ? d.format("YYYY-MM-DD HH:mm") : "—"
}

/** Is this timestamp older than ``minutes`` ago? Used for stale hints. */
export function isStale(ts, minutes = 30) {
  const d = parse(ts)
  if (!d) return false
  return dayjs().diff(d, "minute") >= minutes
}

/** Humanize a byte count into a compact binary-unit string. */
export function humanBytes(bytes) {
  if (bytes === null || bytes === undefined || bytes === "") return "—"
  let n = Number(bytes)
  if (!Number.isFinite(n)) return "—"
  if (n < 1024) return `${n} B`
  const units = ["KiB", "MiB", "GiB", "TiB", "PiB"]
  let i = -1
  do {
    n /= 1024
    i += 1
  } while (n >= 1024 && i < units.length - 1)
  return `${n.toFixed(n >= 100 || i === 0 ? 0 : 1)} ${units[i]}`
}

/** Compact integer with thousands separators. */
export function humanCount(n) {
  if (n === null || n === undefined || n === "") return "—"
  const v = Number(n)
  return Number.isFinite(v) ? v.toLocaleString() : "—"
}
