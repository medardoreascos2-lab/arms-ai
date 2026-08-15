"use client";

import {
    useEffect,
    useState,
} from "react";

import {
    getStrategyIntelligence,
    StrategyIntelligence,
} from "../../../dashboard-v2/strategyIntelligenceApi";


function decisionStyle(
    decision: string
) {

    if (decision === "ACTIVATE") {
        return "text-emerald-400";
    }

    if (decision === "DISABLE") {
        return "text-rose-400";
    }

    return "text-amber-400";
}



export default function StrategyIntelligenceCard() {

    const [
        data,
        setData,
    ] = useState<StrategyIntelligence | null>(
        null
    );


    useEffect(() => {

        getStrategyIntelligence()
            .then(setData)
            .catch(console.error);

    }, []);



    if (!data) {

        return (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 text-slate-400">
                Loading Strategy Intelligence...
            </div>
        );

    }


    const score =
        data.scores.final;


    return (

        <article className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-cyan-950/30 p-6 shadow-xl">


            <div className="flex items-center justify-between">

                <h2 className="text-lg font-bold text-white">
                    🧠 Strategy Intelligence
                </h2>


                <span
                    className={`font-bold ${decisionStyle(data.final_decision)}`}
                >
                    {data.final_decision}
                </span>

            </div>



            <div className="mt-5 space-y-4">


                <div>
                    <p className="text-xs uppercase text-slate-500">
                        Strategy
                    </p>

                    <p className="text-white font-semibold">
                        {data.strategy}
                    </p>
                </div>



                <div>
                    <p className="text-xs uppercase text-slate-500">
                        Confidence
                    </p>

                    <p className="text-cyan-300 font-semibold">
                        {data.confidence}
                    </p>
                </div>



                <div>

                    <div className="flex justify-between text-xs text-slate-400">

                        <span>
                            Final Score
                        </span>

                        <span>
                            {score}/100
                        </span>

                    </div>


                    <div className="mt-2 h-2 rounded-full bg-slate-800">

                        <div
                            className="h-2 rounded-full bg-cyan-400"
                            style={{
                                width: `${score}%`,
                            }}
                        />

                    </div>

                </div>




                <div>

                    <p className="text-xs uppercase text-slate-500">
                        Market Context
                    </p>


                    <p className="text-white">
                        {data.market.regime}
                    </p>


                    <p className="text-emerald-400 text-sm">
                        Compatibility: {data.market.compatibility}
                    </p>

                </div>




                <div>

                    <p className="text-xs uppercase text-slate-500">
                        AI Reasoning
                    </p>


                    <ul className="mt-2 space-y-1 text-sm text-slate-300">

                        {data.reason.map(
                            (
                                reason,
                                index
                            ) => (

                            <li key={index}>
                                ✓ {reason}
                            </li>

                        ))}

                    </ul>

                </div>




                <div className="border-t border-slate-800 pt-3 text-sm text-slate-300">

                    Win Rate:
                    {" "}
                    <span className="text-white font-semibold">
                        {data.history.win_rate}%
                    </span>

                </div>


            </div>

        </article>

    );
}
