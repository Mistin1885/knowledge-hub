export const COLLAB_STABLE_CONNECTION_MS = 30_000;
export const COLLAB_RECONNECT_BASE_MS = 2_000;
export const COLLAB_RECONNECT_MAX_MS = 30_000;

/**
 * Exponential backoff with equal jitter.
 *
 * A lower bound prevents a successful HTTP 101 followed by an immediate close
 * from producing a reconnect storm. Jitter keeps many clients behind the same
 * corporate NAT from retrying in lockstep.
 */
export function collabReconnectDelayMs(
  consecutiveFailures: number,
  random: () => number = Math.random,
): number {
  const exponent = Math.max(0, Math.min(consecutiveFailures - 1, 30));
  const ceiling = Math.min(
    COLLAB_RECONNECT_MAX_MS,
    COLLAB_RECONNECT_BASE_MS * 2 ** exponent,
  );
  const floor = ceiling / 2;
  return Math.round(floor + random() * (ceiling - floor));
}
