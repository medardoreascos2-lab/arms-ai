"use client";

type AccountOverviewProps = {
    data: {
        balance?: number;
        equity?: number;
        daily_pnl?: number;
        drawdown?: number;
        open_risk?: number;
        account_stage?: string;
        evaluation_status?: string;
        profit_target?: number;
        profit_achieved?: number;
        profit_remaining?: number;
        profit_progress_percent?: number;
        target_reached?: boolean;
    } | null;
};

function formatMoney(
    value?: number
) {
    if (value === undefined) {
        return "$0";
    }

    return new Intl.NumberFormat(
        "en-US",
        {
            style: "currency",
            currency: "USD",
        }
    ).format(value);
}

function formatPercent(
    value?: number
) {
    if (value === undefined) {
        return "0%";
    }

    return `${value.toFixed(1)}%`;
}

export default function AccountOverviewCard(
    {
        data,
    }: AccountOverviewProps
) {
    if (!data) {
        return (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
                Loading Account...
            </div>
        );
    }

    const targetReached =
        data.target_reached === true;

    const evaluationStatus =
        data.evaluation_status ?? "NOT_APPLICABLE";

    const evaluationStatusClass =
        evaluationStatus === "FAILED"
            ? "bg-red-500/15 text-red-400"
            : evaluationStatus === "PASSED"
                ? "bg-emerald-500/15 text-emerald-400"
                : evaluationStatus === "IN_PROGRESS"
                    ? "bg-cyan-500/15 text-cyan-400"
                    : "bg-slate-800 text-slate-300";

    return (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">

            <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-white">
                    💰 Account Overview
                </h2>

                <span className="text-emerald-400 font-bold">
                    ACTIVE
                </span>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-3">

                <div>
                    <p className="text-xs text-slate-500">
                        Balance
                    </p>

                    <p className="text-2xl font-bold text-white">
                        {formatMoney(data.balance)}
                    </p>
                </div>

                <div>
                    <p className="text-xs text-slate-500">
                        Equity
                    </p>

                    <p className="text-2xl font-bold text-cyan-400">
                        {formatMoney(data.equity)}
                    </p>
                </div>

                <div>
                    <p className="text-xs text-slate-500">
                        Daily P/L
                    </p>

                    <p className="text-2xl font-bold text-white">
                        {formatMoney(data.daily_pnl)}
                    </p>
                </div>

                <div>
                    <p className="text-xs text-slate-500">
                        Drawdown
                    </p>

                    <p className="text-xl font-bold text-white">
                        {formatMoney(data.drawdown)}
                    </p>
                </div>

                <div>
                    <p className="text-xs text-slate-500">
                        Open Risk
                    </p>

                    <p className="text-xl font-bold text-white">
                        {formatMoney(data.open_risk)}
                    </p>
                </div>

                <div>
                    <p className="text-xs text-slate-500">
                        Account Stage
                    </p>

                    <p className="text-xl font-bold text-white">
                        {data.account_stage ?? "—"}
                    </p>
                </div>

            </div>

            <div className="mt-6 rounded-xl border border-slate-800 bg-slate-950/60 p-5">

                <div className="flex items-center justify-between">

                    <div>
                        <p className="text-xs uppercase tracking-[0.16em] text-slate-500">
                            Evaluation Status
                        </p>

                        <span
                            className={`mt-2 inline-flex rounded-full px-3 py-1 text-sm font-bold ${evaluationStatusClass}`}
                        >
                            {evaluationStatus}
                        </span>
                    </div>

                    <div className="text-right">

                        <p className="text-xs text-slate-500">
                            Profit Target
                        </p>

                        <p className="text-lg font-bold text-cyan-400">
                            {formatMoney(data.profit_target)}
                        </p>

                    </div>

                </div>

                <div className="mt-5">

                    <div className="flex items-center justify-between text-xs">

                        <span className="text-slate-500">
                            Profit Progress
                        </span>

                        <span className="font-semibold text-white">
                            {formatPercent(
                                data.profit_progress_percent
                            )}
                        </span>

                    </div>

                    <div className="mt-2 h-3 overflow-hidden rounded-full bg-slate-800">

                        <div
                            className="h-full rounded-full bg-cyan-400 transition-all"
                            style={{
                                width: `${Math.min(
                                    Math.max(
                                        data.profit_progress_percent ?? 0,
                                        0
                                    ),
                                    100
                                )}%`,
                            }}
                        />

                    </div>

                </div>

                <div className="mt-4 grid gap-4 md:grid-cols-2">

                    <div>
                        <p className="text-xs text-slate-500">
                            Profit Achieved
                        </p>

                        <p className="text-lg font-bold text-white">
                            {formatMoney(
                                data.profit_achieved
                            )}
                        </p>
                    </div>

                    <div>
                        <p className="text-xs text-slate-500">
                            Profit Remaining
                        </p>

                        <p className="text-lg font-bold text-white">
                            {formatMoney(
                                data.profit_remaining
                            )}
                        </p>
                    </div>

                </div>

                <div className="mt-5">

                    <span
                        className={
                            targetReached
                                ? "inline-flex rounded-full px-3 py-1 text-xs font-bold bg-emerald-500/15 text-emerald-400"
                                : "inline-flex rounded-full px-3 py-1 text-xs font-bold bg-slate-800 text-slate-300"
                        }
                    >
                        {targetReached
                            ? "TARGET REACHED"
                            : "TARGET IN PROGRESS"}
                    </span>

                </div>

            </div>

        </div>
    );
}
