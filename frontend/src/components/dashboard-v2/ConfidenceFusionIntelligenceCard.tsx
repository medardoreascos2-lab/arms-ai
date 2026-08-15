"use client";


type ConfidenceFusionData = {

    technical_score: number;

    probability_score: number;

    structure_score: number;

    risk_score: number;

    memory_score: number;

    final_confidence: number;

    quality: string;

    decision: string;

    explanation: string[];

    recommendations: string[];

};



export default function ConfidenceFusionIntelligenceCard({

    data,

}: {

    data: ConfidenceFusionData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading ARMS AI Final Intelligence...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">


            <div className="flex items-center justify-between">

                <h2 className="text-xl font-bold text-white">

                    🧠 ARMS AI Final Intelligence

                </h2>


                <span className="text-emerald-400 font-bold">

                    {data.decision}

                </span>


            </div>



            <div className="mt-5 text-center">

                <p className="text-sm text-slate-400">

                    Final Confidence

                </p>


                <p className="text-5xl font-bold text-cyan-400">

                    {data.final_confidence}%

                </p>


                <p className="mt-2 text-xl font-bold text-white">

                    Quality {data.quality}

                </p>

            </div>




            <div className="mt-6 grid gap-5 md:grid-cols-5">


                <div>
                    Technical
                    <p className="text-xl font-bold text-white">
                        {data.technical_score}%
                    </p>
                </div>


                <div>
                    Probability
                    <p className="text-xl font-bold text-white">
                        {data.probability_score}%
                    </p>
                </div>


                <div>
                    Structure
                    <p className="text-xl font-bold text-white">
                        {data.structure_score}%
                    </p>
                </div>


                <div>
                    Risk
                    <p className="text-xl font-bold text-white">
                        {data.risk_score}%
                    </p>
                </div>


                <div>
                    Memory
                    <p className="text-xl font-bold text-white">
                        {data.memory_score}%
                    </p>
                </div>


            </div>



            <div className="mt-5">

                {data.explanation.map(

                    (item) => (

                        <p key={item} className="text-sm text-white">

                            ✓ {item}

                        </p>

                    )

                )}

            </div>


        </section>

    );

}
