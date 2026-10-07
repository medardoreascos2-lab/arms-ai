import type { BetaDashboardBundle, BetaSignal } from "./betaDashboardApi";

function timestamp(value: string | null | undefined): number {
  if (!value) return Number.NEGATIVE_INFINITY;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : Number.NEGATIVE_INFINITY;
}

function signalTime(signal: BetaSignal): number {
  return Math.max(timestamp(signal.updated_at), timestamp(signal.created_at));
}

/** Rejects stale bundles and prevents an older signal from replacing a newer one. */
export function reconcileBetaBundle(
  previous: BetaDashboardBundle | null,
  incoming: BetaDashboardBundle,
): BetaDashboardBundle {
  if (
    incoming.contract_version !== "1.0" || incoming.paper_only !== true ||
    incoming.live.signal.paper_only !== true || incoming.performance.paper_only !== true ||
    incoming.runtime.read_only !== true ||
    incoming.runtime.live_execution_allowed !== false ||
    (incoming.live.position !== null && incoming.live.position.paper_only !== true)
  ) {
    throw new Error("Invalid PAPER beta dashboard contract.");
  }
  if (!previous) return incoming;
  if (timestamp(incoming.observed_at) <= timestamp(previous.observed_at)) return previous;
  if (signalTime(incoming.live.signal) < signalTime(previous.live.signal)) {
    return {
      ...incoming,
      live: {
        ...incoming.live,
        current_signal: previous.live.current_signal,
        signal: previous.live.signal,
      },
    };
  }
  return incoming;
}
