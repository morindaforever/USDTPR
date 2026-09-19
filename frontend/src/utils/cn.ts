/**
 * Join conditional class names. Small stand-in for `clsx` so the design
 * system has a single, dependency-free way to compose classes.
 */
export function cn(
  ...classes: Array<string | number | false | null | undefined>
): string {
  return classes.filter(Boolean).join(' ');
}
