"use client";


type RiskProfileData = {
  account: string;
  balance: number;
  risk_percent: number;
  risk_per_trade: number;
  daily_loss_limit: number;
  max_drawdown: number;
  status: string;
};


export default function RiskProfileCard({
  data,
}: {
  data: RiskProfileData | null;
}) {


  if (!data) {

    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">
        Loading Risk Profile...
      </div>
    );

  }


  return (

    <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

      <div className="flex items-center justify-between">

        <h2 className="text-xl font-bold text-white">
          🛡️ Account Risk Profile
        </h2>


        <span className="font-bold text-emerald-400">
          {data.status}
        </span>

      </div>


      <div className="mt-5 grid gap-4 md:grid-cols-3">


        <div>
          <p className="text-xs text-slate-500">
            Account
          </p>

          <p className="text-xl font-bold text-white">
            {data.account}
          </p>
        </div>


        <div>
          <p className="text-xs text-slate-500">
            Balance
          </p>

          <p className="text-xl font-bold text-white">
            ${data.balance}
          </p>
        </div>


        <div>
          <p className="text-xs text-slate-500">
            Risk %
          </p>

          <p className="text-xl font-bold text-cyan-400">
            {data.risk_percent}%
          </p>
        </div>


        <div>
          <p className="text-xs text-slate-500">
            Risk Per Trade
          </p>

          <p className="text-xl font-bold text-white">
            ${data.risk_per_trade}
          </p>
        </div>


        <div>
          <p className="text-xs text-slate-500">
            Daily Loss Limit
          </p>

          <p className="text-xl font-bold text-red-400">
            ${data.daily_loss_limit}
          </p>
        </div>


        <div>
          <p className="text-xs text-slate-500">
            Max Drawdown
          </p>

          <p className="text-xl font-bold text-yellow-400">
            ${data.max_drawdown}
          </p>
        </div>


      </div>

    </section>

  );

}
