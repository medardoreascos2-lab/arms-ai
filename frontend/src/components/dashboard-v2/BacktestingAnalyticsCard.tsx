"use client";

type BacktestingData = {

    total_runs: number;

    total_strategies: number;

    best_strategy: string;

    worst_strategy: string;

    win_rate: number;

    profit_factor: number;

    max_drawdown: number;

    recommendation: string;

};


export default function BacktestingAnalyticsCard({

    data,

}: {

    data: BacktestingData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading Backtesting Analytics...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">


            <div className="flex items-center justify-between">


                <h2 className="text-xl font-bold text-white">

                    🧪 Backtesting Analytics Intelligence

                </h2>


                <span className="text-cyan-400 font-bold">

                    AI BACKTEST

                </span>


            </div>



            <div className="mt-5 grid gap-5 md:grid-cols-3">


                <div>

                    <p className="text-xs text-slate-500">

                        Total Runs

                    </p>

                    <p className="text-2xl font-bold text-white">

                        {data.total_runs}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Strategies Tested

                    </p>

                    <p className="text-2xl font-bold text-white">

                        {data.total_strategies}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Win Rate

                    </p>

                    <p className="text-2xl font-bold text-emerald-400">

                        {data.win_rate}%

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Profit Factor

                    </p>

                    <p className="text-2xl font-bold text-cyan-400">

                        {data.profit_factor}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Max Drawdown

                    </p>

                    <p className="text-2xl font-bold text-red-400">

                        ${data.max_drawdown}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Recommendation

                    </p>

                    <p className="text-lg font-bold text-emerald-400">

                        {data.recommendation}

                    </p>

                </div>


            </div>



            <div className="mt-5 border-t border-slate-800 pt-4 grid md:grid-cols-2 gap-4">


                <div>

                    <p className="text-xs text-slate-500">

                        Best Strategy

                    </p>

                    <p className="text-white font-bold">

                        {data.best_strategy}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Worst Strategy

                    </p>

                    <p className="text-white font-bold">

                        {data.worst_strategy}

                    </p>

                </div>


            </div>


        </section>

    );

}
