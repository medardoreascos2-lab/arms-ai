# ARMS AI — REQUIREMENTS MATRIX

> Matriz para cruzar lo solicitado históricamente contra el estado real del repositorio.

---

## STATUS LEGEND

- `VERIFIED_IMPLEMENTED`
- `VERIFIED_CLOSED`
- `PARTIAL`
- `NOT_IMPLEMENTED`
- `NEEDS_VERIFICATION`
- `SUPERSEDED`
- `CONFLICT`
- `BLOCKED`

---

## PHASE 0 CERTIFICATION

Phase 0 — Critical Stabilization está formalmente cerrada.

Certification evidence:

- `PHASE0_REQUIREMENTS=8`
- `PHASE0_VERIFIED_CLOSED=8`
- `PHASE0_PARTIAL_COUNT=0`
- `PHASE0_OPEN_COUNT=0`
- `PHASE0_NEEDS_VERIFICATION_COUNT=0`
- `PHASE0_AUDIT_COMPLETE=YES`
- `PHASE0_CLOSE_RECOMMENDATION=CLOSE`
- Full backend regression: `5082 tests passed`
- Closure commit: `c13cd54d7ec0453c86e934ce117ce11764de5a4e`
- Closure commit message: `test: close Phase 0 critical stabilization gaps`

`VERIFIED_CLOSED` indicates that the requirement was included in the formal Phase 0 recertification and had closure evidence. It does not imply that unrelated historical requirements or future phase scope have been fully consolidated.

---

## REQUIREMENTS

| ID | Area | Requirement | Historical Source | Current Code Evidence | Status | Priority | Notes |
|---|---|---|---|---|---|---|---|
| REQ-001 | TBD | Pending historical consolidation | TBD | TBD | NEEDS_VERIFICATION | TBD | Awaiting full history |
| PHASE0-REQ-001 | Trading Execution Safety | Prevent blocked signals from executing | Phase 0 critical stabilization audit | Phase 0 final recertification; 8/8 requirements verified closed; closure commit c13cd54d7ec0453c86e934ce117ce11764de5a4e | VERIFIED_CLOSED | CRITICAL | `PHASE0_AUDIT_COMPLETE=YES`; no partial, open, or needs-verification Phase 0 items remained |
| PHASE0-REQ-002 | Dashboard / Read Operations | Remove execution side effects from dashboard read operations | Phase 0 critical stabilization audit | Phase 0 final recertification; 8/8 requirements verified closed; closure commit c13cd54d7ec0453c86e934ce117ce11764de5a4e | VERIFIED_CLOSED | CRITICAL | Read-only execution-side-effect requirement formally closed |
| PHASE0-REQ-003 | Account State / Daily PnL | Correct daily PnL synchronization | Phase 0 critical stabilization audit | Phase 0 final recertification; 8/8 requirements verified closed; closure commit c13cd54d7ec0453c86e934ce117ce11764de5a4e | VERIFIED_CLOSED | CRITICAL | Daily PnL synchronization requirement formally closed |
| PHASE0-REQ-004 | Risk Management | Correct daily loss and trading-block synchronization | Phase 0 critical stabilization audit | Phase 0 final recertification; 8/8 requirements verified closed; closure commit c13cd54d7ec0453c86e934ce117ce11764de5a4e | VERIFIED_CLOSED | CRITICAL | Risk and trading-block synchronization requirement formally closed |
| PHASE0-REQ-005 | Accounts | Correct account switching consistency | Phase 0 critical stabilization audit | Phase 0 final recertification; 8/8 requirements verified closed; closure commit c13cd54d7ec0453c86e934ce117ce11764de5a4e | VERIFIED_CLOSED | CRITICAL | Account state consistency requirement formally closed |
| PHASE0-REQ-006 | Execution / Recovery | Complete execution state recovery | Phase 0 critical stabilization audit | Phase 0 final recertification; 8/8 requirements verified closed; closure commit c13cd54d7ec0453c86e934ce117ce11764de5a4e | VERIFIED_CLOSED | CRITICAL | Execution recovery requirement formally closed |
| PHASE0-REQ-007 | Runtime / Infrastructure | Resolve startup/runtime path inconsistencies | Phase 0 critical stabilization audit | Phase 0 final recertification; 8/8 requirements verified closed; closure commit c13cd54d7ec0453c86e934ce117ce11764de5a4e | VERIFIED_CLOSED | CRITICAL | Startup and runtime path requirement formally closed |
| PHASE0-REQ-008 | API / Security | Review and enforce API security boundaries | Phase 0 critical stabilization audit | Phase 0 final recertification; 8/8 requirements verified closed; closure commit c13cd54d7ec0453c86e934ce117ce11764de5a4e | VERIFIED_CLOSED | CRITICAL | API security boundary requirement formally closed |

---

## PHASE 0 TRACEABILITY

| Phase 0 Evidence | Certified Value |
|---|---|
| Requirements assessed | 8 |
| Requirements verified closed | 8 |
| Partial requirements | 0 |
| Open requirements | 0 |
| Requirements needing verification | 0 |
| Audit complete | YES |
| Close recommendation | CLOSE |
| Full backend regression | 5082 tests passed |
| Closure commit | `c13cd54d7ec0453c86e934ce117ce11764de5a4e` |
| Closure commit message | `test: close Phase 0 critical stabilization gaps` |

---

## AREAS TO AUDIT

- Market Data
- TradingView
- Technical Analysis
- Market Structure
- Smart Money
- Confluence
- Probability
- Sessions
- Economic News
- Risk Management
- Position Sizing
- Account Rules
- Execution
- Broker Integration
- PAPER Trading
- LIVE Trading
- Portfolio
- Journal
- Daily PnL
- Drawdown
- Backtesting
- Optimization
- Walk Forward
- Monte Carlo
- Strategy Certification
- Machine Learning
- Adaptive Learning
- Memory
- AI Assistant
- Voice
- Telegram
- WhatsApp
- Mobile App
- Dashboard
- Admin Dashboard
- Memberships
- API
- WebSocket
- Persistence
- Recovery
- Security
- Deployment
- Monitoring
- Testing
- Reporting
- Commercial Product
- Home Assistant / Jarvis Extensions

---

## VALIDATION RULE

A feature may only be marked `VERIFIED_IMPLEMENTED` when there is concrete evidence in the repository and, where applicable, supporting tests.

A Phase 0 requirement may only be marked `VERIFIED_CLOSED` when it is included in the formal Phase 0 closure evidence and the certified Phase 0 audit reports it closed with no remaining partial, open, or needs-verification status.
