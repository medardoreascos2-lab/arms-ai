"use client";


type TradePlanData = {

    entry: number;

    stop_loss: number;

    take_profit: number;

    risk_amount: number;

    reward_amount: number;

    risk_reward_ratio: number;

    contracts: number;

    approved: boolean;

};



export default function TradeExecutionPlanCard({

    data,

}: {

    data: TradePlanData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading ARMS AI Trade Execution Plan...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-emerald-500/30 bg-slate-900/90 p-6">


            <div className="flex justify-between items-center">


                <h2 className="text-xl font-bold text-white">

                    📈 ARMS AI Trade Execution Plan

                </h2>


                <span className="text-emerald-400 font-bold">

                    {data.approved ? "READY" : "BLOCKED"}

                </span>


            </div>



            <div className="mt-6 grid gap-4 md:grid-cols-4">


                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                        Entry
                    </p>

                    <p className="text-xl font-bold text-white">
                        {data.entry}
                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                        Stop Loss
                    </p>

                    <p className="text-xl font-bold text-red-400">
                        {data.stop_loss}
                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                        Take Profit
                    </p>

                    <p className="text-xl font-bold text-emerald-400">
                        {data.take_profit}
                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                        Contracts
                    </p>

                    <p className="text-xl font-bold text-white">
                        {data.contracts}
                    </p>

                </div>


            </div>



            <div className="mt-6 grid gap-4 md:grid-cols-3">


                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                        Risk $
                    </p>

                    <p className="text-xl font-bold text-red-400">
                        {data.risk_amount}
                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                        Reward $
                    </p>

                    <p className="text-xl font-bold text-emerald-400">
                        {data.reward_amount}
                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                        Risk Reward
                    </p>

                    <p className="text-xl font-bold text-cyan-400">
                        {data.risk_reward_ratio}
                    </p>

                </div>


            </div>


        </section>

    );

}
