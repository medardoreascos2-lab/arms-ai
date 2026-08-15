"use client";


type AIDecisionData = {

    decision: string;

    direction: string;

    strategy_id: string | null;

    confidence: number;

    action: string;

    reasons: string[];

};



export default function AIDecisionEngineCard({

    data,

}: {

    data: AIDecisionData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading AI Decision Engine...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">


            <div className="flex items-center justify-between">


                <h2 className="text-xl font-bold text-white">

                    🤖 AI Decision Engine

                </h2>


                <span className="text-cyan-400 font-bold">

                    LIVE AI

                </span>


            </div>




            <div className="mt-5 grid gap-5 md:grid-cols-3">


                <div>

                    <p className="text-xs text-slate-500">

                        Decision

                    </p>

                    <p className="text-2xl font-bold text-white">

                        {data.decision}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Direction

                    </p>

                    <p className={

                        data.direction === "BUY"

                        ? "text-emerald-400 text-2xl font-bold"

                        : data.direction === "SELL"

                        ? "text-red-400 text-2xl font-bold"

                        : "text-white text-2xl font-bold"

                    }>

                        {data.direction}

                    </p>

                </div>




                <div>

                    <p className="text-xs text-slate-500">

                        Confidence

                    </p>

                    <p className="text-cyan-400 text-2xl font-bold">

                        {data.confidence}%

                    </p>

                </div>


            </div>





            <div className="mt-5 border-t border-slate-800 pt-4 grid md:grid-cols-2 gap-4">


                <div>

                    <p className="text-xs text-slate-500">

                        Strategy

                    </p>

                    <p className="text-white font-bold">

                        {data.strategy_id ?? "NONE"}

                    </p>

                </div>




                <div>

                    <p className="text-xs text-slate-500">

                        Action

                    </p>

                    <p className="text-emerald-400 font-bold">

                        {data.action}

                    </p>

                </div>


            </div>





            {

                data.reasons.length > 0 && (

                    <div className="mt-5 rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-4">


                        <p className="font-bold text-cyan-300">

                            AI Reasoning

                        </p>


                        {

                            data.reasons.map(

                                (reason) => (

                                    <p

                                        key={reason}

                                        className="text-sm text-white"

                                    >

                                        ✓ {reason}

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
