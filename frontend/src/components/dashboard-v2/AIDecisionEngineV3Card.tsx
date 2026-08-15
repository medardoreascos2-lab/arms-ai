"use client";


type DecisionEngineV3Data = {

    symbol: string;

    direction: string;

    confidence: number;

    quality: string;

    decision: string;

    execution_status: string;

    risk_allowed: boolean;

    risk_score: number;

};



export default function AIDecisionEngineV3Card({

    data,

}: {

    data: DecisionEngineV3Data | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading ARMS AI Decision Engine V3...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-cyan-500/30 bg-slate-900/90 p-6">


            <div className="flex justify-between items-center">


                <h2 className="text-xl font-bold text-white">

                    🧠 ARMS AI Decision Engine V3

                </h2>


                <span className="text-emerald-400 font-bold">

                    {data.decision}

                </span>


            </div>




            <div className="mt-6 text-center">


                <p className="text-slate-400">

                    {data.symbol} · {data.direction}

                </p>


                <p className="text-5xl font-bold text-cyan-400">

                    {data.confidence}%

                </p>


                <p className="text-xl text-white font-bold">

                    Quality {data.quality}

                </p>


            </div>




            <div className="mt-6 grid gap-4 md:grid-cols-3">


                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">

                        Execution

                    </p>

                    <p className="text-xl font-bold text-white">

                        {data.execution_status}

                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">

                        Risk Score

                    </p>

                    <p className="text-xl font-bold text-white">

                        {data.risk_score}

                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">

                        Risk Allowed

                    </p>

                    <p className="text-xl font-bold text-emerald-400">

                        {data.risk_allowed ? "YES" : "NO"}

                    </p>

                </div>


            </div>


        </section>

    );

}
