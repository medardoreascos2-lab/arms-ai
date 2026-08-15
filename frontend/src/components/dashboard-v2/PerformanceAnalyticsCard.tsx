"use client";


type PerformanceData = {

    total_trades: number;

    winning_trades: number;

    losing_trades: number;

    win_rate: number;

    profit_factor: number;

    expectancy: number;

    net_profit: number;

    average_win: number;

    average_loss: number;

};



export default function PerformanceAnalyticsCard({

    data,

}: {

    data: PerformanceData | null;

}) {



    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading Performance Analytics...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">


            <div className="flex items-center justify-between">


                <h2 className="text-xl font-bold text-white">

                    📊 Performance Analytics

                </h2>


                <span className="text-cyan-400 font-bold">

                    LIVE

                </span>


            </div>




            <div className="mt-5 grid gap-5 md:grid-cols-3">



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

                    <p className="text-2xl font-bold text-emerald-400">

                        {data.win_rate}%

                    </p>

                </div>




                <div>

                    <p className="text-xs text-slate-500">

                        Profit Factor

                    </p>

                    <p className="text-2xl font-bold text-white">

                        {data.profit_factor}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Expectancy

                    </p>

                    <p className="text-2xl font-bold text-cyan-400">

                        ${data.expectancy}

                    </p>

                </div>




                <div>

                    <p className="text-xs text-slate-500">

                        Net Profit

                    </p>

                    <p className="text-2xl font-bold text-white">

                        ${data.net_profit}

                    </p>

                </div>




                <div>

                    <p className="text-xs text-slate-500">

                        Average Win

                    </p>

                    <p className="text-2xl font-bold text-emerald-400">

                        ${data.average_win}

                    </p>

                </div>



            </div>


        </section>

    );

}
