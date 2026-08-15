"use client";


type LearningData = {

    trades_analyzed: number;

    win_rate: number;

    total_profit: number;

    performance_level: string;

    insights: string[];

    recommendations: string[];

};



export default function AILearningIntelligenceCard({

    data,

}: {

    data: LearningData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading ARMS AI Learning Intelligence...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-cyan-500/30 bg-slate-900/90 p-6">


            <div className="flex justify-between items-center">


                <h2 className="text-xl font-bold text-white">

                    🧠 ARMS AI Learning Intelligence

                </h2>


                <span className="text-cyan-400 font-bold">

                    ACTIVE

                </span>


            </div>



            <div className="mt-6 grid gap-4 md:grid-cols-4">


                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                        Trades Analyzed
                    </p>

                    <p className="text-xl font-bold text-white">

                        {data.trades_analyzed}

                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                        Win Rate
                    </p>

                    <p className="text-xl font-bold text-emerald-400">

                        {data.win_rate}%

                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                        Profit
                    </p>

                    <p className="text-xl font-bold text-cyan-400">

                        {data.total_profit}

                    </p>

                </div>



                <div className="rounded-xl bg-slate-800 p-4">

                    <p className="text-xs text-slate-400">
                        Performance
                    </p>

                    <p className="text-xl font-bold text-white">

                        {data.performance_level}

                    </p>

                </div>


            </div>



            <div className="mt-6 rounded-xl bg-slate-800 p-4">


                <p className="text-xs text-slate-400">

                    AI Insights

                </p>


                {data.insights.map(

                    (item, index) => (

                        <p
                            key={index}
                            className="mt-2 text-white"
                        >
                            • {item}
                        </p>

                    )

                )}


            </div>



            <div className="mt-4 rounded-xl bg-slate-800 p-4">


                <p className="text-xs text-slate-400">

                    Recommendations

                </p>


                {data.recommendations.map(

                    (item, index) => (

                        <p
                            key={index}
                            className="mt-2 text-white"
                        >
                            • {item}
                        </p>

                    )

                )}


            </div>


        </section>

    );

}
