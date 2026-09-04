/**
 * Pure formatting utilities — no side-effects, fully unit-testable.
 */

/** Format a Date or ISO string to a locale-aware date string */
export function formatDate(
  date: Date | string | null | undefined,
  options: Intl.DateTimeFormatOptions = { dateStyle: 'medium' },
): string {
  if (!date) return '—';
  try {
    return new Intl.DateTimeFormat('en-US', options).format(new Date(date));
  } catch {
    return '—';
  }
}

/** Format a Date or ISO string to a locale-aware date + time string */
export function formatDateTime(date: Date | string | null | undefined): string {
  return formatDate(date, { dateStyle: 'medium', timeStyle: 'short' });
}

/** Format a duration in minutes to a human-readable string */
export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

/** Capitalise the first letter of a string */
export function capitalise(str: string): string {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/** Truncate a string to a max length with ellipsis */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return `${str.slice(0, maxLength - 3)}...`;
}

/** Format a number with locale-aware thousand separators */
export function formatNumber(value: number, options?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat('en-US', options).format(value);
}
