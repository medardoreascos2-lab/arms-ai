"use client";


type ExecutionManagerData = {

    status: string;

    symbol: string;

    direction: string;

    order_type: string;

    contracts: number;

    entry: number;

    stop_loss: number;

    take_profit: number;

    risk_amount: number;

    validation: string[];

};



export default function ExecutionManagerCard({

    data,

}: {

    data: ExecutionManagerData | null;

}) {


    if (!data) {

        return (

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

                Loading Execution Manager...

            </div>

        );

    }



    return (

        <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">


            <div className="flex items-center justify-between">


                <h2 className="text-xl font-bold text-white">

                    🚀 Execution Manager Intelligence

                </h2>


                <span className={

                    data.status === "READY"

                    ? "text-emerald-400 font-bold"

                    : "text-red-400 font-bold"

                }>

                    {data.status}

                </span>


            </div>





            <div className="mt-5 grid gap-5 md:grid-cols-4">


                <div>

                    <p className="text-xs text-slate-500">

                        Symbol

                    </p>

                    <p className="text-2xl font-bold text-white">

                        {data.symbol}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Direction

                    </p>

                    <p className={

                        data.direction === "BUY"

                        ? "text-emerald-400 text-2xl font-bold"

                        : "text-red-400 text-2xl font-bold"

                    }>

                        {data.direction}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Order Type

                    </p>

                    <p className="text-cyan-400 text-2xl font-bold">

                        {data.order_type}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Contracts

                    </p>

                    <p className="text-white text-2xl font-bold">

                        {data.contracts}

                    </p>

                </div>


            </div>





            <div className="mt-5 grid gap-5 md:grid-cols-4 border-t border-slate-800 pt-4">


                <div>

                    <p className="text-xs text-slate-500">

                        Entry

                    </p>

                    <p className="text-white font-bold text-xl">

                        {data.entry}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Stop Loss

                    </p>

                    <p className="text-red-400 font-bold text-xl">

                        {data.stop_loss}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Take Profit

                    </p>

                    <p className="text-emerald-400 font-bold text-xl">

                        {data.take_profit}

                    </p>

                </div>



                <div>

                    <p className="text-xs text-slate-500">

                        Risk

                    </p>

                    <p className="text-white font-bold text-xl">

                        ${data.risk_amount}

                    </p>

                </div>


            </div>





            {

                data.validation.length > 0 && (

                    <div className="mt-5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">


                        <p className="font-bold text-emerald-300">

                            Execution Validation

                        </p>


                        {

                            data.validation.map(

                                (item) => (

                                    <p

                                        key={item}

                                        className="text-sm text-white"

                                    >

                                        ✓ {item}

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
