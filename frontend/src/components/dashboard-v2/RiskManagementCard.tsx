"use client";

type RiskEventAnalytics = {
    total_events?: number;
    decision_summary?: {
        approved?: number;
        blocked?: number;
        unknown?: number;
        decision_total?: number;
        approval_rate_percent?: number | null;
        block_rate_percent?: number | null;
    } | null;
    by_event_type?: Record<string, number>;
    by_symbol?: Record<string, number>;
    by_reason?: Record<string, number>;
};

type RiskData = {
    trading_blocked: boolean;
    blocking_reasons: string[];
    drawdown: number;
    open_risk: number;
    daily_loss_used: number;
    remaining_daily_loss_capacity: number;
    remaining_drawdown_capacity: number;
    event_analytics?: RiskEventAnalytics | null;
};

function formatNumber(
    value: number | undefined
): string {
    if (
        value === undefined
        || !Number.isFinite(value)
    ) {
        return "—";
    }

    return new Intl.NumberFormat(
        "en-US",
        {
            maximumFractionDigits: 2,
        }
    ).format(value);
}

function formatPercent(
    value: number | undefined
): string {
    if (
        value === undefined
        || !Number.isFinite(value)
    ) {
        return "—";
    }

    return `${formatNumber(value)}%`;
}

export default function RiskManagementCard({
    data,
}: {
    data: RiskData | null;
}) {
    if (!data) {
        return (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">
                Loading Risk Management...
            </div>
        );
    }

    const analytics =
        data.event_analytics ?? null;

    return (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Execution Safety
                    </p>

                    <h2 className="mt-1 text-xl font-bold text-white">
                        🛡️ Risk Management
                    </h2>
                </div>

                <span
                    className={
                        data.trading_blocked
                            ? "rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-sm font-bold text-red-400"
                            : "rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-sm font-bold text-emerald-400"
                    }
                >
                    {
                        data.trading_blocked
                            ? "BLOCKED"
                            : "ENABLED"
                    }
                </span>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                    <p className="text-xs text-slate-500">
                        Daily Loss Used
                    </p>

                    <p className="mt-2 text-2xl font-bold text-white">
                        ${formatNumber(data.daily_loss_used)}
                    </p>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                    <p className="text-xs text-slate-500">
                        Remaining Daily Capacity
                    </p>

                    <p className="mt-2 text-2xl font-bold text-cyan-400">
                        ${formatNumber(
                            data.remaining_daily_loss_capacity
                        )}
                    </p>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                    <p className="text-xs text-slate-500">
                        Current Drawdown
                    </p>

                    <p className="mt-2 text-2xl font-bold text-white">
                        ${formatNumber(data.drawdown)}
                    </p>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                    <p className="text-xs text-slate-500">
                        Open Risk
                    </p>

                    <p className="mt-2 text-2xl font-bold text-white">
                        ${formatNumber(data.open_risk)}
                    </p>
                </div>
            </div>

            <div className="mt-5 border-t border-slate-800 pt-5">
                <p className="text-xs text-slate-500">
                    Remaining Drawdown Capacity
                </p>

                <p className="mt-2 text-xl font-bold text-cyan-400">
                    ${formatNumber(
                        data.remaining_drawdown_capacity
                    )}
                </p>
            </div>

            {
                data.blocking_reasons.length > 0 && (
                    <div className="mt-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4">
                        <p className="font-bold text-red-300">
                            Blocking Reasons
                        </p>

                        {
                            data.blocking_reasons.map(
                                (reason) => (
                                    <p
                                        key={reason}
                                        className="mt-1 text-sm text-red-200"
                                    >
                                        • {reason}
                                    </p>
                                )
                            )
                        }
                    </div>
                )
            }

            <div className="mt-6 border-t border-slate-800 pt-6">
                <div className="flex flex-wrap items-end justify-between gap-3">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                            Risk Event Analytics V2
                        </p>

                        <h3 className="mt-1 text-lg font-semibold text-white">
                            Execution Risk Intelligence
                        </h3>
                    </div>

                    <span className="text-xs text-slate-500">
                        Historical safety telemetry
                    </span>
                </div>

                {
                    analytics ? (
                        <>
                            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                                    <p className="text-xs text-slate-500">
                                        Total Events
                                    </p>

                                    <p className="mt-2 text-xl font-bold text-white">
                                        {formatNumber(
                                            analytics.total_events
                                        )}
                                    </p>
                                </div>

                                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                                    <p className="text-xs text-slate-500">
                                        Blocked Events
                                    </p>

                                    <p className="mt-2 text-xl font-bold text-red-300">
                                        {formatNumber(
                                            analytics.decision_summary?.blocked
                                        )}
                                    </p>
                                </div>

                                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                                    <p className="text-xs text-slate-500">
                                        Allowed Events
                                    </p>

                                    <p className="mt-2 text-xl font-bold text-emerald-300">
                                        {formatNumber(
                                            analytics.decision_summary?.approved
                                        )}
                                    </p>
                                </div>

                                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                                    <p className="text-xs text-slate-500">
                                        Block Rate
                                    </p>

                                    <p className="mt-2 text-xl font-bold text-cyan-300">
                                        {formatPercent(
                                            analytics.decision_summary?.block_rate_percent ?? undefined
                                        )}
                                    </p>
                                </div>
                            </div>

                            <div className="mt-4 grid gap-3 lg:grid-cols-2">
                                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                                    <p className="text-xs text-slate-500">
                                        Most Common Risk Reason
                                    </p>

                                    <p className="mt-2 break-words text-sm font-semibold text-slate-200">
                                        {
                                            Object.keys(
                                                analytics.by_reason ?? {}
                                            )[0]
                                            ?? "No dominant risk reason"
                                        }
                                    </p>
                                </div>

                                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                                    <p className="text-xs text-slate-500">
                                        Latest Event Type
                                    </p>

                                    <p className="mt-2 break-words text-sm font-semibold text-slate-200">
                                        {
                                            Object.keys(
                                                analytics.by_event_type ?? {}
                                            )[0]
                                            ?? "No recent event"
                                        }
                                    </p>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
                            <p className="text-sm text-slate-400">
                                Risk event analytics are not available yet.
                            </p>
                        </div>
                    )
                }
            </div>
        </section>
    );
}
