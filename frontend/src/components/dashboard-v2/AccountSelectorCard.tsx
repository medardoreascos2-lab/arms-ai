"use client";

import {
  useState,
} from "react";


type AccountData = {
  account: string;
  balance: number;
  risk_percent: number;
  daily_loss_limit: number;
  max_drawdown: number;
};


export default function AccountSelectorCard({
  data,
  onChangeAccount,
}: {
  data: AccountData | null;

  onChangeAccount: (
    account: string
  ) => Promise<void>;

}) {


  const [
    selectedAccount,
    setSelectedAccount,
  ] = useState(
    data?.account ?? "TOPSTEP_150K"
  );


  if (!data) {

    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">
        Loading Account...
      </div>
    );

  }


  return (

    <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">

      <div className="flex items-center justify-between">

        <h2 className="text-xl font-bold text-white">
          💼 Trading Account
        </h2>


        <span className="text-emerald-400 font-bold">
          ACTIVE
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
            Risk
          </p>

          <p className="text-xl font-bold text-cyan-400">
            {data.risk_percent}%
          </p>
        </div>


      </div>


      <div className="mt-6 flex gap-4">


        <select
          value={selectedAccount}
          onChange={
            (event) =>
              setSelectedAccount(
                event.target.value
              )
          }
          className="rounded-xl bg-slate-800 px-4 py-2 text-white"
        >

          <option value="TOPSTEP_50K">
            TOPSTEP 50K
          </option>

          <option value="TOPSTEP_150K">
            TOPSTEP 150K
          </option>

          <option value="PERSONAL">
            PERSONAL
          </option>

        </select>


        <button
          onClick={
            () =>
              onChangeAccount(
                selectedAccount
              )
          }
          className="rounded-xl bg-cyan-600 px-5 py-2 font-bold text-white"
        >

          Change Account

        </button>


      </div>


    </section>

  );

}
