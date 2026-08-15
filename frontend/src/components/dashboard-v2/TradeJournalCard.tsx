"use client";


type TradeJournalData = {

    open_trades: number;

    closed_trades: number;

    winning_trades: number;

    losing_trades: number;

    total_realized_pnl: number;

    win_rate: number;

};



export default function TradeJournalCard({

    data,

}: {

    data: TradeJournalData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading Trade Journal...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">


            <div className="flex items-center justify-between">


                <h2 className="text-xl font-bold text-white">

                    📒 Trade Journal Intelligence

                </h2>


                <span className="text-cyan-400 font-bold">

                    LIVE

                </span>


            </div>




            <div className="mt-5 grid gap-5 md:grid-cols-3">



                <div>

                    <p className="text-xs text-slate-500">

                        Open Trades

                    </p>

                    <p className="text-2xl font-bold text-white">

                        {data.open_trades}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Closed Trades

                    </p>

                    <p className="text-2xl font-bold text-white">

                        {data.closed_trades}

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

                        Winning Trades

                    </p>

                    <p className="text-2xl font-bold text-emerald-400">

                        {data.winning_trades}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Losing Trades

                    </p>

                    <p className="text-2xl font-bold text-red-400">

                        {data.losing_trades}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Realized P/L

                    </p>

                    <p className="text-2xl font-bold text-cyan-400">

                        ${data.total_realized_pnl}

                    </p>

                </div>



            </div>


        </section>

    );

}
