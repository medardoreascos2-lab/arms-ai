"use client";

type AccountOverviewProps = {
    data: {
        balance?: number;
        equity?: number;
        daily_pnl?: number;
        drawdown?: number;
        open_risk?: number;
    } | null;
};


function formatMoney(
    value?: number
) {

    if (value === undefined) {
        return "$0";
    }

    return new Intl.NumberFormat(
        "en-US",
        {
            style: "currency",
            currency: "USD",
        }
    ).format(value);

}



export default function AccountOverviewCard(
    {
        data,
    }: AccountOverviewProps
) {


    if (!data) {

        return (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
                Loading Account...
            </div>
        );

    }


    return (

        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">

            <div className="flex justify-between">

                <h2 className="text-xl font-bold text-white">
                    💰 Account Overview
                </h2>


                <span className="text-emerald-400 font-bold">
                    ACTIVE
                </span>

            </div>


            <div className="mt-6 grid gap-4 md:grid-cols-3">


                <div>
                    <p className="text-xs text-slate-500">
                        Balance
                    </p>

                    <p className="text-2xl font-bold text-white">
                        {formatMoney(data.balance)}
                    </p>
                </div>



                <div>
                    <p className="text-xs text-slate-500">
                        Equity
                    </p>

                    <p className="text-2xl font-bold text-cyan-400">
                        {formatMoney(data.equity)}
                    </p>
                </div>



                <div>
                    <p className="text-xs text-slate-500">
                        Daily P/L
                    </p>

                    <p className="text-2xl font-bold text-white">
                        {formatMoney(data.daily_pnl)}
                    </p>
                </div>



                <div>
                    <p className="text-xs text-slate-500">
                        Drawdown
                    </p>

                    <p className="text-xl font-bold text-white">
                        {formatMoney(data.drawdown)}
                    </p>
                </div>



                <div>
                    <p className="text-xs text-slate-500">
                        Open Risk
                    </p>

                    <p className="text-xl font-bold text-white">
                        {formatMoney(data.open_risk)}
                    </p>
                </div>


            </div>

        </div>

    );

}
