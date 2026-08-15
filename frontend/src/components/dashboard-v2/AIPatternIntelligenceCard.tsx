"use client";


type AIPatternData = {

    trades_analyzed: number;

    buy_trades: number;

    sell_trades: number;

    average_profit: number;

    average_loss: number;

    best_direction: string;

    pattern_quality: string;

    insights: string[];

    recommendations: string[];

};



export default function AIPatternIntelligenceCard({

    data,

}: {

    data: AIPatternData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading AI Pattern Intelligence...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">


            <div className="flex items-center justify-between">


                <h2 className="text-xl font-bold text-white">

                    🧠 AI Pattern Intelligence

                </h2>


                <span className="text-cyan-400 font-bold">

                    {data.pattern_quality}

                </span>


            </div>





            <div className="mt-5 grid gap-5 md:grid-cols-4">


                <div>

                    <p className="text-xs text-slate-500">

                        Trades

                    </p>

                    <p className="text-2xl font-bold text-white">

                        {data.trades_analyzed}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        BUY

                    </p>

                    <p className="text-emerald-400 text-2xl font-bold">

                        {data.buy_trades}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        SELL

                    </p>

                    <p className="text-red-400 text-2xl font-bold">

                        {data.sell_trades}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Best Direction

                    </p>

                    <p className="text-cyan-400 text-2xl font-bold">

                        {data.best_direction}

                    </p>

                </div>


            </div>





            <div className="mt-5 grid gap-5 md:grid-cols-2 border-t border-slate-800 pt-4">


                <div>

                    <p className="text-xs text-slate-500">

                        Average Profit

                    </p>

                    <p className="text-emerald-400 text-xl font-bold">

                        +${data.average_profit}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Average Loss

                    </p>

                    <p className="text-red-400 text-xl font-bold">

                        ${data.average_loss}

                    </p>

                </div>


            </div>





            <div className="mt-5 grid gap-5 md:grid-cols-2">


                <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-4">


                    <p className="font-bold text-cyan-300">

                        Insights

                    </p>


                    {data.insights.map(

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





                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">


                    <p className="font-bold text-emerald-300">

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
