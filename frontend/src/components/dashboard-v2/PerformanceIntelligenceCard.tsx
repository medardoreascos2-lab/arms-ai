"use client";


type PerformanceData = {

    total_trades: number;

    winning_trades: number;

    losing_trades: number;

    win_rate: number;

    total_profit: number;

    average_trade: number;

    best_trade: number;

    worst_trade: number;

};



export default function PerformanceIntelligenceCard({

    data,

}: {

    data: PerformanceData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading Performance Intelligence...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">


            <div className="flex items-center justify-between">


                <h2 className="text-xl font-bold text-white">

                    📊 Performance Intelligence

                </h2>


                <span className="text-cyan-400 font-bold">

                    ANALYTICS

                </span>


            </div>



            <div className="mt-5 grid gap-5 md:grid-cols-4">


                <div>

                    <p className="text-xs text-slate-500">

                        Total Trades

                    </p>

                    <p className="text-2xl font-bold text-white">

                        {data.total_trades}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Win Rate

                    </p>

                    <p className="text-emerald-400 text-2xl font-bold">

                        {data.win_rate}%

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Total Profit

                    </p>

                    <p className="text-emerald-400 text-2xl font-bold">

                        ${data.total_profit}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Average Trade

                    </p>

                    <p className="text-cyan-400 text-2xl font-bold">

                        ${data.average_trade}

                    </p>

                </div>


            </div>



            <div className="mt-5 grid gap-5 md:grid-cols-2 border-t border-slate-800 pt-4">


                <div>

                    <p className="text-xs text-slate-500">

                        Best Trade

                    </p>

                    <p className="text-emerald-400 text-xl font-bold">

                        +${data.best_trade}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Worst Trade

                    </p>

                    <p className="text-red-400 text-xl font-bold">

                        ${data.worst_trade}

                    </p>

                </div>


            </div>


        </section>

    );

}
