"use client";


type DecisionCenterData = {

    symbol: string;

    direction: string;

    entry: number;

    stop_loss: number;

    take_profit: number;

    confidence: number;

    quality: string;

    decision: string;

    reasoning: string[];

    recommendations: string[];

};



export default function AIDecisionCenterCard({

    data,

}: {

    data: DecisionCenterData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading ARMS AI Decision Center...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-cyan-500/30 bg-slate-900/90 p-6">


            <div className="flex items-center justify-between">

                <h2 className="text-xl font-bold text-white">

                    🧠 ARMS AI Decision Center

                </h2>


                <span className="text-emerald-400 font-bold">

                    {data.decision}

                </span>


            </div>




            <div className="mt-6 text-center">


                <p className="text-slate-400">

                    {data.symbol} · {data.direction}

                </p>


                <p className="mt-2 text-5xl font-bold text-cyan-400">

                    {data.confidence}%

                </p>


                <p className="text-xl font-bold text-white">

                    Quality {data.quality}

                </p>


            </div>





            <div className="mt-6 grid gap-4 md:grid-cols-3">


                <div className="rounded-xl bg-slate-800/60 p-4">

                    <p className="text-xs text-slate-400">

                        Entry

                    </p>

                    <p className="text-xl font-bold text-white">

                        {data.entry}

                    </p>

                </div>



                <div className="rounded-xl bg-slate-800/60 p-4">

                    <p className="text-xs text-slate-400">

                        Stop Loss

                    </p>

                    <p className="text-xl font-bold text-red-400">

                        {data.stop_loss}

                    </p>

                </div>



                <div className="rounded-xl bg-slate-800/60 p-4">

                    <p className="text-xs text-slate-400">

                        Take Profit

                    </p>

                    <p className="text-xl font-bold text-emerald-400">

                        {data.take_profit}

                    </p>

                </div>


            </div>





            <div className="mt-6">


                <p className="font-bold text-white">

                    AI Reasoning

                </p>


                {data.reasoning.map(

                    (item) => (

                        <p

                            key={item}

                            className="text-sm text-white"

                        >

                            ✓ {item}

                        </p>

                    )

                )}


            </div>



        </section>

    );

}
