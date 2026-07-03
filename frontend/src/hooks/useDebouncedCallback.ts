import { useEffect, useMemo, useRef } from 'react';

/** Debounced callback; always calls the latest closure. Pending call is dropped on unmount. */
export function useDebouncedCallback<A extends unknown[]>(
  fn: (...args: A) => void,
  delayMs: number,
): (...args: A) => void {
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const timerRef = useRef<number>();

  useEffect(() => () => window.clearTimeout(timerRef.current), []);

  return useMemo(
    () =>
      (...args: A) => {
        window.clearTimeout(timerRef.current);
        timerRef.current = window.setTimeout(() => fnRef.current(...args), delayMs);
      },
    [delayMs],
  );
}
