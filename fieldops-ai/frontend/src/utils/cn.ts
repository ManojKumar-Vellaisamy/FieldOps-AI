/**
 * Utility to merge Tailwind CSS class names conditionally.
 *
 * Accepts any combination of:
 *  - Strings
 *  - Falsy values (false | null | undefined | 0) — ignored
 *  - Arrays of the above
 *
 * Usage:
 *   cn('px-4 py-2', isActive && 'bg-brand-500', className)
 */
type ClassInput = string | boolean | null | undefined | ClassInput[];

export function cn(...inputs: ClassInput[]): string {
  return inputs
    .flat(Infinity as 10)
    .filter((x): x is string => typeof x === 'string' && x.length > 0)
    .join(' ');
}
