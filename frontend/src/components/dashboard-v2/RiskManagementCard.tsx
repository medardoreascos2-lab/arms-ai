"use client";

type RiskData = {
    trading_blocked: boolean;
    blocking_reasons: string[];
    drawdown: number;
    open_risk: number;
    daily_loss_used: number;
    remaining_daily_loss_capacity: number;
    remaining_drawdown_capacity: number;
};


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



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

            <div className="flex justify-between items-center">

                <h2 className="text-xl font-bold text-white">
                    🛡️ Risk Management
                </h2>


                <span
                    className={
                        data.trading_blocked
                        ? "text-red-400 font-bold"
                        : "text-emerald-400 font-bold"
                    }
                >

                    {
                        data.trading_blocked
                        ? "BLOCKED"
                        : "ENABLED"
                    }

                </span>

            </div>



            <div className="mt-5 grid gap-4 md:grid-cols-3">


                <div>
                    <p className="text-xs text-slate-500">
                        Daily Loss Used
                    </p>

                    <p className="text-2xl font-bold text-white">
                        ${data.daily_loss_used}
                    </p>
                </div>



                <div>
                    <p className="text-xs text-slate-500">
                        Remaining Daily Capacity
                    </p>

                    <p className="text-2xl font-bold text-cyan-400">
                        ${data.remaining_daily_loss_capacity}
                    </p>
                </div>



                <div>
                    <p className="text-xs text-slate-500">
                        Current Drawdown
                    </p>

                    <p className="text-2xl font-bold text-white">
                        ${data.drawdown}
                    </p>
                </div>


            </div>



            <div className="mt-5 border-t border-slate-800 pt-4">


                <p className="text-xs text-slate-500">
                    Remaining Drawdown Capacity
                </p>


                <p className="text-xl font-bold text-cyan-400">
                    ${data.remaining_drawdown_capacity}
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
                                        className="text-sm text-red-200"
                                    >
                                        • {reason}
                                    </p>
                                )
                            )
                        }

                    </div>

                )
            }


        </section>

    );
}
