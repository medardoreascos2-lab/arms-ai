# Authorized local PAPER dashboard

The operational view is `/dashboard-v2`. Use the coordinated backend on loopback
(`python -m uvicorn backend.api.asgi:app --host 127.0.0.1 --port 8000`) with its
existing PAPER account namespace, admission policy, admin authorization and
certified calendar/news configuration. V11 does not supply permissive trading
defaults or enable LIVE execution.

Set the public **origin only** in your existing local frontend configuration:

```dotenv
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_PAPER_SYMBOL=MNQ
NEXT_PUBLIC_PAPER_TIMEFRAME=5m
```

Match the API origin to the actual backend port. These values are compiled into
the browser bundle: restart `npm run dev`, or rebuild with `npm run build` and
then `npm run start`, after changing them. Open
`http://127.0.0.1:3000/dashboard-v2`. Existing backend CORS supports localhost or
127.0.0.1 on port 3000. HTTP/WS is allowed only on loopback; a remote API origin
must use HTTPS/WSS and requires an independently configured deployment boundary.

Enter the existing **PAPER** backend `ARMS_ADMIN_TOKEN` in the password field and
select **Conectar PAPER**. This reuses `AdminAuthorizationV2`; it does not create
an account, session issuer or second token authority. The credential stays in
page memory and is cleared on disconnect, unmount or reload. Never put it in a
`NEXT_PUBLIC_*` variable, source code, a URL, browser storage or this README.
Never enter LIVE or broker credentials. Test credentials in regression fixtures
are disposable and are not deployment configuration.

Protected account switching uses `X-ARMS-ADMIN-TOKEN`. Public observational GETs
send no credential. The browser offers `arms-dashboard-v1` plus an
`arms-admin.<base64url credential>` WebSocket subprotocol. The backend validates
with the same authority before acceptance and selects only `arms-dashboard-v1`;
it never echoes the credential. Base64 is transport encoding, not encryption.
Keep header/handshake tracing disabled or redact the admin header and
`Sec-WebSocket-Protocol` at any configured proxy. No credential appears in the
WebSocket URL.

The account selector lists actual runtime account identities. Switching clears
all projections, retires the socket and reconnects to the new generation.
Rejected/unavailable connections display an error and no prior account data;
correct the credential/service and reconnect. Refresh and five-second polling
only read backend state. Candidate approval remains observational and is not an
order or execution permission. This dashboard contains no trade-submit control.
Missing market analysis is explicitly unavailable. Legacy demonstration setup,
ranking and approval cards are excluded from the authorized PAPER projection.

Validation commands supported by this repository:

```powershell
npm run lint
node --test src/lib/dashboardApi.test.mjs src/lib/dashboardConnection.test.mjs src/lib/dashboardProjection.test.mjs
npm run build
```

`build` includes TypeScript checking. There is no separate `test` or `typecheck`
package script. See the [V11 certificate](../docs/architecture/phase2_authorized_paper_dashboard_v11.md)
for evidence and the remaining operational acceptance boundary.

---

This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
