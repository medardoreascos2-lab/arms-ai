"use client";


type TradingMemoryData = {

    trades_analyzed: number;

    buy_count: number;

    sell_count: number;

    dominant_strategy: string;

    memory_quality: string;

    winning_patterns: string[];

    losing_patterns: string[];

    insights: string[];

    recommendations: string[];

};



export default function AITradingMemoryIntelligenceCard({

    data,

}: {

    data: TradingMemoryData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading AI Trading Memory Intelligence...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">


            <div className="flex items-center justify-between">


                <h2 className="text-xl font-bold text-white">

                    🧠 AI Trading Memory Intelligence

                </h2>


                <span className="text-cyan-400 font-bold">

                    {data.memory_quality}

                </span>


            </div>




            <div className="mt-5 grid gap-5 md:grid-cols-4">


                <div>

                    <p className="text-xs text-slate-500">

                        Trades Remembered

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

                        {data.buy_count}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        SELL

                    </p>

                    <p className="text-red-400 text-2xl font-bold">

                        {data.sell_count}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Dominant Strategy

                    </p>

                    <p className="text-cyan-400 text-xl font-bold">

                        {data.dominant_strategy}

                    </p>

                </div>


            </div>





            <div className="mt-5 grid gap-5 md:grid-cols-2">


                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">


                    <p className="font-bold text-emerald-300">

                        Winning Patterns

                    </p>


                    {data.winning_patterns.map(

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




                <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">


                    <p className="font-bold text-red-300">

                        Losing Patterns

                    </p>


                    {data.losing_patterns.map(

                        (item) => (

                            <p

                                key={item}

                                className="text-sm text-white"

                            >

                                ✕ {item}

                            </p>

                        )

                    )}


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
