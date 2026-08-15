"use client";


type AIDecisionMemoryData = {

    technical_confidence: number;

    memory_confidence: number;

    memory_adjustment: number;

    final_confidence: number;

    memory_reliability: string;

    decision: string;

    explanation: string[];

    recommendations: string[];

};



export default function AIDecisionMemoryIntelligenceCard({

    data,

}: {

    data: AIDecisionMemoryData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading AI Decision Memory Intelligence...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">


            <div className="flex items-center justify-between">


                <h2 className="text-xl font-bold text-white">

                    🧠 AI Decision Memory Intelligence

                </h2>


                <span className="text-cyan-400 font-bold">

                    {data.decision}

                </span>


            </div>





            <div className="mt-5 grid gap-5 md:grid-cols-3">


                <div>

                    <p className="text-xs text-slate-500">

                        Technical Confidence

                    </p>

                    <p className="text-2xl font-bold text-white">

                        {data.technical_confidence}%

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Historical Memory

                    </p>

                    <p className="text-2xl font-bold text-cyan-400">

                        {data.memory_confidence}%

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Final Confidence

                    </p>

                    <p className="text-2xl font-bold text-emerald-400">

                        {data.final_confidence}%

                    </p>

                </div>


            </div>





            <div className="mt-5 grid gap-5 md:grid-cols-2">


                <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-4">


                    <p className="font-bold text-cyan-300">

                        Memory Analysis

                    </p>


                    <p className="text-sm text-white">

                        Reliability: {data.memory_reliability}

                    </p>


                    <p className="text-sm text-white">

                        Adjustment: +{data.memory_adjustment}%

                    </p>


                </div>




                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">


                    <p className="font-bold text-emerald-300">

                        Decision

                    </p>


                    <p className="text-2xl font-bold text-white">

                        {data.decision}

                    </p>


                </div>


            </div>





            <div className="mt-5 grid gap-5 md:grid-cols-2">


                <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-4">


                    <p className="font-bold text-white">

                        Explanation

                    </p>


                    {data.explanation.map(

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





                <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-4">


                    <p className="font-bold text-yellow-300">

                        Recommendations

                    </p>


                    {data.recommendations.map(

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


            </div>


        </section>

    );

}
