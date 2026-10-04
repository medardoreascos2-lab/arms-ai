export default function OfflinePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-4 bg-slate-950 px-6 py-12 text-slate-100">
      <p className="text-sm font-semibold uppercase tracking-widest text-cyan-200">Connection unavailable</p>
      <h1 className="text-3xl font-semibold">ARMS + MEDAR is offline</h1>
      <p className="text-slate-300">
        Product data is unavailable without a verified connection. Reconnect and refresh to request current information.
      </p>
      <a className="min-h-11 w-fit rounded-lg border border-cyan-200 px-4 py-3 text-cyan-100 focus:outline-2 focus:outline-offset-2 focus:outline-cyan-200" href="/product">
        Refresh Product
      </a>
    </main>
  );
}