"use client";


type ExecutionSimulatorData = {

    status: string;

    symbol: string;

    direction: string;

    entry: number;

    stop_loss: number;

    take_profit: number;

    risk_points: number;

    reward_points: number;

    risk_reward: number;

    contracts: number;

    max_loss: number;

    expected_profit: number;

};



export default function ExecutionSimulatorCard({

    data,

}: {

    data: ExecutionSimulatorData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading Execution Simulator...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">


            <div className="flex items-center justify-between">


                <h2 className="text-xl font-bold text-white">

                    ⚙️ Execution Simulator Intelligence

                </h2>


                <span className="text-cyan-400 font-bold">

                    {data.status}

                </span>


            </div>




            <div className="mt-5 grid gap-5 md:grid-cols-4">


                <div>

                    <p className="text-xs text-slate-500">

                        Symbol

                    </p>

                    <p className="text-2xl font-bold text-white">

                        {data.symbol}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Direction

                    </p>

                    <p className={

                        data.direction === "BUY"

                        ? "text-emerald-400 text-2xl font-bold"

                        : "text-red-400 text-2xl font-bold"

                    }>

                        {data.direction}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Contracts

                    </p>

                    <p className="text-cyan-400 text-2xl font-bold">

                        {data.contracts}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Risk Reward

                    </p>

                    <p className="text-white text-2xl font-bold">

                        1:{data.risk_reward}

                    </p>

                </div>


            </div>




            <div className="mt-5 grid gap-5 md:grid-cols-3 border-t border-slate-800 pt-4">


                <div>

                    <p className="text-xs text-slate-500">

                        Max Loss

                    </p>

                    <p className="text-red-400 font-bold text-xl">

                        ${data.max_loss}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Expected Profit

                    </p>

                    <p className="text-emerald-400 font-bold text-xl">

                        ${data.expected_profit}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Risk Points

                    </p>

                    <p className="text-white font-bold text-xl">

                        {data.risk_points}

                    </p>

                </div>


            </div>




            <div className="mt-5 rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-4">


                <p className="font-bold text-cyan-300">

                    Execution Plan

                </p>


                <p className="text-sm text-white">

                    Entry: {data.entry}

                </p>


                <p className="text-sm text-red-300">

                    Stop Loss: {data.stop_loss}

                </p>


                <p className="text-sm text-emerald-300">

                    Take Profit: {data.take_profit}

                </p>


            </div>


        </section>

    );

}
