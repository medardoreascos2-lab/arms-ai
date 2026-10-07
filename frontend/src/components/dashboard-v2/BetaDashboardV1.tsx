"use client";

import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";

import {
  BetaApiError,
  createBetaUser,
  extendBetaUser,
  getBetaDashboard,
  getBetaSession,
  getBetaUsers,
  loginBeta,
  logoutBeta,
  setBetaUserEnabled,
  type BetaDashboardBundle,
  type BetaPerformance,
  type BetaRuntimeObservation,
  type BetaUser,
  type BetaUserList,
} from "@/lib/betaDashboardApi";
import { reconcileBetaBundle } from "@/lib/betaDashboardProjection";


type Section = "live" | "history" | "performance" | "admin" | "owner";

const card = "rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-xl shadow-black/10";
const button = "rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-cyan-600 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-50";

function value(value: unknown, suffix = ""): string {
  if (value === null || value === undefined || value === "") return "Unavailable";
  if (typeof value === "number") return `${value.toLocaleString(undefined, { maximumFractionDigits: 4 })}${suffix}`;
  return String(value);
}

function money(valueToFormat: number | null): string {
  if (valueToFormat === null) return "Unavailable";
  return valueToFormat.toLocaleString(undefined, {
    style: "currency", currency: "USD", maximumFractionDigits: 2,
  });
}

function dateTime(input: string | null): string {
  if (!input) return "Unavailable";
  const parsed = new Date(input);
  return Number.isNaN(parsed.getTime()) ? "Unavailable" : parsed.toLocaleString();
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={card}>
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-slate-100">{children}</p>
    </div>
  );
}

function Login({ onLogin }: { onLogin: (email: string, password: string) => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onLogin(email, password);
      setPassword("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-16 text-slate-100">
      <div className="mx-auto max-w-md">
        <div className="mb-6 flex items-center justify-between">
          <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-bold tracking-[0.2em] text-amber-300">BETA</span>
          <span className="text-xs text-slate-500">ARMS AI</span>
        </div>
        <form onSubmit={submit} className={`${card} space-y-5`}>
          <div>
            <h1 className="text-2xl font-semibold">Beta Dashboard V1</h1>
            <p className="mt-2 text-sm text-slate-400">Sign in to view authenticated PAPER observations.</p>
          </div>
          <label className="block text-sm text-slate-300">
            Username or email
            <input className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 outline-none focus:border-cyan-500" type="text" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="block text-sm text-slate-300">
            Password
            <input className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 outline-none focus:border-cyan-500" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error && <p role="alert" className="rounded-lg border border-rose-800 bg-rose-950/50 p-3 text-sm text-rose-300">{error}</p>}
          <button className="w-full rounded-lg bg-cyan-700 px-4 py-2 font-semibold hover:bg-cyan-600 disabled:opacity-50" disabled={busy} type="submit">{busy ? "Signing in…" : "Sign in"}</button>
          <p className="text-xs leading-5 text-amber-300">PAPER / SIMULATED RESULTS · NOT LIVE BROKER PERFORMANCE</p>
        </form>
      </div>
    </main>
  );
}

function LiveView({ bundle }: { bundle: BetaDashboardBundle }) {
  const signal = bundle.live.signal;
  const color = signal.direction === "BUY" ? "text-emerald-300" : signal.direction === "SELL" ? "text-rose-300" : "text-amber-300";
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="ARMS Status">{bundle.live.arms_status}</Stat>
        <Stat label="Market Status">{bundle.live.market_status}</Stat>
        <Stat label="Instrument">{bundle.live.instrument}</Stat>
        <Stat label="Contract">{bundle.live.contract}</Stat>
        <Stat label="Current Signal"><span className={color}>{bundle.live.current_signal}</span></Stat>
      </div>
      <section className={card}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">Signal status</p>
            <h2 className={`mt-2 text-4xl font-bold ${color}`}>{signal.status}</h2>
          </div>
          <p className="text-sm text-slate-500">{dateTime(signal.created_at)}</p>
        </div>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
          <Stat label="Entry price">{value(signal.entry_price)}</Stat>
          <Stat label="Stop loss">{value(signal.stop_loss)}</Stat>
          <Stat label="Take profit">{value(signal.take_profit)}</Stat>
          <Stat label="Reward / risk">{value(signal.reward_risk)}</Stat>
          <Stat label="Confidence">{value(signal.confidence)}</Stat>
          <Stat label="Confluence">{value(signal.confluence)}</Stat>
        </div>
      </section>
      <section className={card}>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">Current PAPER position</p>
        {bundle.live.position ? (
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
            <Stat label="Status">{bundle.live.position.status}</Stat>
            <Stat label="Direction">{bundle.live.position.direction}</Stat>
            <Stat label="Quantity">{value(bundle.live.position.quantity)}</Stat>
            <Stat label="Entry">{value(bundle.live.position.entry_price)}</Stat>
            <Stat label="Stop">{value(bundle.live.position.stop_loss)}</Stat>
            <Stat label="Target">{value(bundle.live.position.take_profit)}</Stat>
          </div>
        ) : <p className="mt-3 text-slate-400">FLAT / no canonical PAPER position.</p>}
      </section>      <section className={`${card} border-cyan-900/70`}>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">Why ARMS</p>
        <p className="mt-3 text-base leading-7 text-slate-300">{signal.decision_summary}</p>
      </section>
    </div>
  );
}

function HistoryView({ bundle }: { bundle: BetaDashboardBundle }) {
  const records = bundle.history.records;
  return (
    <section className={`${card} overflow-hidden p-0`}>
      <div className="border-b border-slate-800 p-5">
        <h2 className="text-lg font-semibold">PAPER signal and trade history</h2>
        <p className="mt-1 text-sm text-slate-500">Canonical read-only records; unavailable values are not estimated.</p>
      </div>
      {records.length === 0 ? (
        <p className="p-8 text-center text-slate-500">Unavailable / insufficient data.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-950/70 text-xs uppercase tracking-wider text-slate-500">
              <tr>{["Type", "Instrument", "Direction", "Entry", "Stop", "Target", "Entry time", "Exit time", "Exit", "Result", "Points", "PAPER P&L", "Status"].map((heading) => <th className="whitespace-nowrap px-4 py-3" key={heading}>{heading}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {records.map((record) => (
                <tr key={record.record_id} className="text-slate-300">
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">{record.record_type}</td>
                  <td className="px-4 py-3">{record.instrument}</td>
                  <td className="px-4 py-3 font-semibold">{record.direction}</td>
                  <td className="px-4 py-3">{value(record.entry)}</td>
                  <td className="px-4 py-3">{value(record.stop)}</td>
                  <td className="px-4 py-3">{value(record.target)}</td>
                  <td className="whitespace-nowrap px-4 py-3">{dateTime(record.entry_time)}</td>
                  <td className="whitespace-nowrap px-4 py-3">{dateTime(record.exit_time)}</td>
                  <td className="px-4 py-3">{value(record.exit_price)}</td>
                  <td className="px-4 py-3">{value(record.result)}</td>
                  <td className="px-4 py-3">{value(record.points_or_ticks)}</td>
                  <td className="px-4 py-3">{money(record.paper_pnl)}</td>
                  <td className="px-4 py-3">{record.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function PerformanceView({ performance }: { performance: BetaPerformance }) {
  const metrics: Array<[string, string]> = [
    ["Today P&L", money(performance.today_pnl)],
    ["Cumulative P&L", money(performance.cumulative_pnl)],
    ["Trades", value(performance.trades)],
    ["Wins", value(performance.wins)],
    ["Losses", value(performance.losses)],
    ["Win rate", performance.win_rate === null ? "Unavailable" : value(performance.win_rate, "%")],
    ["Average win", money(performance.average_win)],
    ["Average loss", money(performance.average_loss)],
    ["Profit factor", value(performance.profit_factor)],
    ["Maximum drawdown", money(performance.maximum_drawdown)],
  ];
  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {metrics.map(([label, metric]) => <Stat label={label} key={label}>{metric}</Stat>)}
      </div>
      <p className="mt-5 text-sm text-slate-500">Metrics marked unavailable have insufficient reliable PAPER data. No value is simulated or backfilled for display.</p>
    </div>
  );
}

function OwnerRuntimeView({ runtime }: { runtime: BetaRuntimeObservation | null }) {
  if (!runtime) {
    return <section className={card}>Runtime observation is UNAVAILABLE.</section>;
  }
  return (
    <main className="mx-auto max-w-[1500px] space-y-6 px-4 py-6 lg:px-8">
      <section className="rounded-2xl border border-cyan-900/70 bg-slate-900/80 p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">Read-only runtime observation</p>
        <p className="mt-2 text-sm text-slate-400">Canonical CURRENT PAPER and NinjaTrader health only. No command or execution credential is available to this browser.</p>
      </section>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="PAPER runtime health">{runtime.paper_runtime_health}</Stat>
        <Stat label="PAPER API">{runtime.paper_api_status}</Stat>
        <Stat label="Analysis">{runtime.analysis_status}</Stat>
        <Stat label="NinjaTrader">{runtime.ninjatrader_status}</Stat>
        <Stat label="Contract">{runtime.contract}</Stat>
        <Stat label="Market session status">{runtime.market_session_status}</Stat>
        <Stat label="Feed freshness">{runtime.feed_freshness}</Stat>
        <Stat label="Heartbeat age">{value(runtime.heartbeat_age_seconds, "s")}</Stat>
      </div>
      <section className={card}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Heartbeat">{dateTime(runtime.heartbeat_at)}</Stat>
          <Stat label="Realized PAPER P&L">{money(runtime.realized_paper_pnl)}</Stat>
          <Stat label="PAPER authority">{runtime.paper_authority_state}</Stat>
          <Stat label="PAPER execution">{runtime.paper_execution_authority}</Stat>
          <Stat label="LIVE execution">{runtime.live_execution_authority}</Stat>
          <Stat label="Position">{runtime.current_position ? runtime.current_position.status : "FLAT"}</Stat>
        </div>
      </section>
      <section className="rounded-2xl border border-emerald-900/70 bg-emerald-950/20 p-5 text-sm text-emerald-200">
        READ ONLY · LIVE execution disabled · Order submission unreachable from dashboard
      </section>
    </main>
  );
}
function AdminUsers({ data, refresh }: { data: BetaUserList; refresh: () => Promise<void> }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await createBetaUser(email, password, 30);
      setEmail("");
      setPassword("");
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "User creation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function mutate(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "User update failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Users">{data.counts.total}</Stat>
        <Stat label="Active">{data.counts.active}</Stat>
        <Stat label="Expired">{data.counts.expired}</Stat>
        <Stat label="Disabled">{data.counts.disabled}</Stat>
      </div>
      <form className={`${card} grid gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-end`} onSubmit={create}>
        <label className="text-sm text-slate-300">Email<input className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label className="text-sm text-slate-300">Temporary password<input className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2" type="password" minLength={12} required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        <button className={button} disabled={busy} type="submit">Create 30-day beta user</button>
      </form>
      {error && <p role="alert" className="rounded-lg border border-rose-800 bg-rose-950/50 p-3 text-sm text-rose-300">{error}</p>}
      <section className={`${card} overflow-x-auto p-0`}>
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-950/70 text-xs uppercase tracking-wider text-slate-500"><tr>{["Identity", "Role", "Status", "Beta start", "Beta expires", "Last login", "Actions"].map((heading) => <th className="px-4 py-3" key={heading}>{heading}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-800">
            {data.users.map((user) => (
              <tr key={user.user_id}>
                <td className="px-4 py-3 text-slate-200">{user.email}</td>
                <td className="px-4 py-3 text-slate-400">{user.role}</td>
                <td className="px-4 py-3 text-slate-400">{user.status}</td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-400">{dateTime(user.beta_start_at)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-400">{dateTime(user.beta_expires_at)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-400">{dateTime(user.last_login_at)}</td>
                <td className="whitespace-nowrap px-4 py-3">
                  <div className="flex gap-2">
                    {user.role === "beta_user" && <button className={button} disabled={busy} type="button" onClick={() => void mutate(() => extendBetaUser(user.user_id, 30))}>+30 days</button>}
                    {user.role !== "admin" && <button className={button} disabled={busy} type="button" onClick={() => void mutate(() => setBetaUserEnabled(user.user_id, user.status !== "active"))}>{user.status === "active" ? "Disable" : "Enable"}</button>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

export default function BetaDashboardV1() {
  const [user, setUser] = useState<BetaUser | null>(null);
  const [bundle, setBundle] = useState<BetaDashboardBundle | null>(null);
  const [users, setUsers] = useState<BetaUserList | null>(null);
  const [section, setSection] = useState<Section>("live");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshDashboard = useCallback(async () => {
    try {
      const incoming = await getBetaDashboard();
      setBundle((previous) => reconcileBetaBundle(previous, incoming));
      setError("");
    } catch (caught) {
      if (caught instanceof BetaApiError && (caught.status === 401 || caught.status === 403)) {
        setUser(null);
        setBundle(null);
      }
      setError(caught instanceof Error ? caught.message : "Beta data unavailable.");
    }
  }, []);

  const refreshUsers = useCallback(async () => {
    try {
      setUsers(await getBetaUsers());
    } catch (caught) {
      if (caught instanceof BetaApiError && (caught.status === 401 || caught.status === 403)) {
        setUser(null);
        setUsers(null);
      }
      setError(caught instanceof Error ? caught.message : "User list unavailable.");
    }
  }, []);

  useEffect(() => {
    let active = true;
    void getBetaSession().then(({ user: current }) => {
      if (!active) return;
      setUser(current);
      setLoading(false);
    }).catch(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!user) return;
    const initial = window.setTimeout(() => void refreshDashboard(), 0);
    const timer = window.setInterval(() => void refreshDashboard(), 5000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [user, refreshDashboard]);

  async function handleLogin(email: string, password: string) {
    const session = await loginBeta(email, password);
    setUser(session.user);
    setSection("live");
  }

  async function handleLogout() {
    try { await logoutBeta(); } finally {
      setUser(null);
      setBundle(null);
      setUsers(null);
      setSection("live");
    }
  }

  if (loading) return <main className="min-h-screen bg-slate-950 p-10 text-slate-400">Checking beta access…</main>;
  if (!user) return <Login onLogin={handleLogin} />;

  const tabs: Array<[Section, string]> = [["live", "LIVE"], ["history", "HISTORY"], ["performance", "PERFORMANCE"]];
  if (user.role === "admin") tabs.push(["admin", "BETA USERS"], ["owner", "OWNER CONSOLE"]);

  if (section === "owner" && user.role === "admin") {
    return (
      <div className="bg-slate-950 text-slate-100">
        <div className="sticky top-0 z-50 flex items-center justify-between border-b border-slate-800 bg-slate-950/95 px-4 py-3 backdrop-blur">
          <button className={button} type="button" onClick={() => setSection("live")}>← Beta dashboard</button>
          <span className="text-xs text-amber-300">ADMIN ONLY · PAPER OWNER CONSOLE</span>
        </div>
        <OwnerRuntimeView runtime={bundle?.runtime ?? null} />
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100 lg:px-8">
      <div className="mx-auto max-w-[1500px]">
        <header className="rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900 to-cyan-950/40 p-6 shadow-2xl shadow-black/20">
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div>
              <div className="flex items-center gap-3"><span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-bold tracking-[0.2em] text-amber-300">BETA</span><span className="text-xs uppercase tracking-[0.2em] text-slate-500">Dashboard V1</span></div>
              <h1 className="mt-4 text-3xl font-semibold">ARMS AI</h1>
              <p className="mt-2 text-sm text-amber-300">PAPER / SIMULATED RESULTS · NOT LIVE BROKER PERFORMANCE</p>
            </div>
            <div className="text-right text-sm text-slate-400"><p>{user.email}</p><p className="mt-1">Access expires: {user.role === "admin" ? "Admin" : dateTime(user.beta_expires_at)}</p><button className={`${button} mt-3`} type="button" onClick={() => void handleLogout()}>Log out</button></div>
          </div>
          <nav className="mt-6 flex flex-wrap gap-2" aria-label="Dashboard sections">
            {tabs.map(([key, label]) => <button className={`${button} ${section === key ? "border-cyan-500 bg-cyan-950 text-cyan-200" : ""}`} key={key} type="button" onClick={() => {
              setSection(key);
              if (key === "admin") void refreshUsers();
            }}>{label}</button>)}
          </nav>
        </header>
        {error && <p role="alert" className="mt-5 rounded-lg border border-rose-800 bg-rose-950/50 p-3 text-sm text-rose-300">{error}</p>}
        <div className="mt-6">
          {!bundle && section !== "admin" && <section className={card}><p className="text-slate-400">Authenticated PAPER data is unavailable. The dashboard remains fail-closed.</p></section>}
          {bundle && section === "live" && <LiveView bundle={bundle} />}
          {bundle && section === "history" && <HistoryView bundle={bundle} />}
          {bundle && section === "performance" && <PerformanceView performance={bundle.performance} />}
          {section === "admin" && user.role === "admin" && (users ? <AdminUsers data={users} refresh={refreshUsers} /> : <section className={card}>Loading beta users…</section>)}
        </div>
        <footer className="mt-8 border-t border-slate-800 py-6 text-center text-xs text-slate-600">Read-only beta observation · No browser execution authority · Results are simulated</footer>
      </div>
    </main>
  );
}
