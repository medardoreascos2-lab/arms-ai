"use client";


type ExecutionPipelineData = {

    trade_id: string;

    symbol: string;

    direction: string;

    execution_status: string;

    journal_status: string;

    message: string;

};



export default function ExecutionPipelineCard({

    data,

}: {

    data: ExecutionPipelineData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading ARMS AI Execution Pipeline...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-purple-500/30 bg-slate-900/90 p-6">


            <div className="flex justify-between items-center">


                <h2 className="text-xl font-bold text-white">

                    ⚙️ ARMS AI Execution Pipeline

                </h2>


                <span className="text-emerald-400 font-bold">

                    {data.execution_status}

                </span>


            </div>



            <div className="mt-6 grid gap-4 md:grid-cols-3">


                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">

                        Trade ID

                    </p>

                    <p className="text-xl font-bold text-white">

                        {data.trade_id}

                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">

                        Symbol

                    </p>

                    <p className="text-xl font-bold text-white">

                        {data.symbol}

                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">

                        Direction

                    </p>

                    <p className="text-xl font-bold text-cyan-400">

                        {data.direction}

                    </p>

                </div>


            </div>



            <div className="mt-6 grid gap-4 md:grid-cols-2">


                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">

                        Execution Status

                    </p>

                    <p className="text-xl font-bold text-emerald-400">

                        {data.execution_status}

                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">

                        Journal Status

                    </p>

                    <p className="text-xl font-bold text-white">

                        {data.journal_status}

                    </p>

                </div>


            </div>



            <p className="mt-6 text-sm text-slate-300">

                {data.message}

            </p>


        </section>

    );

}
