"use client";


type StrategyRankingItem = {

    name: string;

    score: number;

    confidence: string;

    status: string;

};



type StrategyRankingData = {

    ranking: StrategyRankingItem[];

};



export default function StrategyRankingCard({

    data,

}: {

    data: StrategyRankingData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading Strategy Ranking...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">


            <div className="flex items-center justify-between">


                <h2 className="text-xl font-bold text-white">

                    🏆 Strategy Ranking Intelligence

                </h2>


                <span className="text-cyan-400 font-bold">

                    AI RANKING

                </span>


            </div>




            <div className="mt-5 space-y-4">


                {

                    data.ranking.map(

                        (strategy, index) => (

                            <div

                                key={strategy.name}

                                className="rounded-xl border border-slate-800 bg-slate-950/40 p-4"

                            >


                                <div className="flex justify-between">


                                    <p className="font-bold text-white">

                                        #{index + 1} {strategy.name}

                                    </p>


                                    <p className="text-cyan-400 font-bold">

                                        {strategy.score}/100

                                    </p>


                                </div>




                                <div className="mt-3 grid gap-3 md:grid-cols-3">


                                    <div>

                                        <p className="text-xs text-slate-500">

                                            Confidence

                                        </p>

                                        <p className="text-white">

                                            {strategy.confidence}

                                        </p>

                                    </div>



                                    <div>

                                        <p className="text-xs text-slate-500">

                                            Market Fit

                                        </p>

                                        <p className="text-white">

                                            {strategy.status}

                                        </p>

                                    </div>



                                    <div>

                                        <p className="text-xs text-slate-500">

                                            Decision

                                        </p>

                                        <p className="text-emerald-400 font-bold">

                                            {strategy.status}

                                        </p>

                                    </div>


                                </div>


                            </div>

                        )

                    )

                }


            </div>


        </section>

    );

}
