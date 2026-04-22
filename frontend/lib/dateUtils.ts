/**
 * Parse a backend-supplied ISO timestamp safely.
 *
 * The backend intends all timestamps to be UTC (created via
 * `datetime.now(timezone.utc)`). But SQLAlchemy/SQLite often strips the
 * tzinfo on round-trip, so `.isoformat()` returns a NAIVE string like
 * "2026-04-17T10:00:00" — no trailing Z or +00:00.
 *
 * JavaScript's `new Date(naiveString)` interprets naive ISO strings as
 * LOCAL time (per ECMAScript spec), which produces wrong results when
 * the server TZ differs from the browser TZ (e.g. server UTC, browser IST).
 *
 * This helper normalizes the input: if no timezone marker is present,
 * treat it as UTC by appending "Z" before parsing.
 */
export function parseBackendDate(iso: string | null | undefined): Date | null {
  if (!iso) return null
  // Already has a timezone marker (Z, +HH:MM, or -HH:MM after the time portion)
  const hasTz = /(Z|[+-]\d{2}:?\d{2})$/.test(iso)
  const normalized = hasTz ? iso : iso + 'Z'
  const d = new Date(normalized)
  return isNaN(d.getTime()) ? null : d
}
