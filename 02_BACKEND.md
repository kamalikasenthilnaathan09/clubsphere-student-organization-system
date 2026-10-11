# ClubSphere — Backend Analysis

Like the frontend, the zip holds **two backends**:

| | A. Flask (primary) | B. Express + Prisma (`Odoo/server`) |
|---|---|---|
| Language | Python 3 | TypeScript / Node |
| Database | SQLite via `sqlite3` (raw SQL) | SQLite via Prisma ORM |
| Auth | Server session cookie | JWT (7-day expiry) |
| Tenancy | Single organisation | Multi-organisation |
| Size | `app.py` 4,475 lines | 12 controllers, 12 route files |

---

## A. Flask backend

### Files
| File | Lines | Role |
|---|---|---|
| `app.py` | 4,475 | All routes, business rules, PDF/QR helpers, CLI entry point |
| `database.py` | 412 | Schema creation, light migrations, DB connection helper |
| `copilot_service.py` | 1,031 | AI assistant: database context, deterministic answers, Gemini/OpenAI calls |
| `seed_demo.py` | 738 | Builds the isolated demo database |
| `requirements.txt` | | Flask, Werkzeug, pytest, google-genai, python-dotenv, reportlab |

### Configuration
- `SECRET_KEY` comes from the environment, otherwise from `instance/secret_key.txt`, otherwise it is generated and saved there.
- Database path: `CLUB_SPHERE_DB`, else the demo DB if it exists, else `instance/clubsphere.db`.
- AI keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`, model overrides, `CLUB_AI_PROVIDER`) load from `.env`; `.env.example` is provided.
- Run flags: `--demo`, `--prod`, `--db <path>`, `--host`, `--port`.

### Database (17 tables)
| Group | Tables |
|---|---|
| People | `users`, `members`, `membership_payments` |
| Events | `events`, `tickets`, `gate_checkin_logs` |
| Merchandise | `merchandise_items`, `merchandise_variants`, `merchandise_orders`, `merchandise_order_items` |
| Finance | `expense_requests`, `financial_transactions` |
| Operations | `volunteer_tasks`, `announcements` |
| Engagement | `student_feedback`, `achievement_points`, `student_certificates` |

Design points:
- `PRAGMA foreign_keys = ON` and WAL journal mode.
- `CHECK` constraints enforce enums (roles, statuses), non-negative money and stock, and ratings from 1 to 5.
- `UNIQUE(user_id, source_type, source_id)` on `achievement_points` stops the same action awarding points twice.
- `UNIQUE(item_id, size)` and a unique `sku` on merchandise variants.
- Lightweight migrations use `PRAGMA table_info` plus `ALTER TABLE ADD COLUMN`.
- 22 indexes on lookup columns.

### Authentication and access control
- `@login_required` checks the session; `@role_required(...)` checks the role.
- **`Administrator` passes every role check.**
- `before_request` hook:
  - redirects everything to `/setup` while no admin exists (no default password anywhere);
  - ends the session at once if the logged-in user was deactivated or deleted.
- Passwords use Werkzeug hashes.
- Login portal separates admin and non-admin accounts; signing in on the wrong portal is rejected server-side.

### Routes by module (55 route decorators)
| Module | Key routes | Who |
|---|---|---|
| Auth | `/setup`, `/register`, `/login`, `/logout`, `/profile` | public / any user |
| Users | `/users`, `/users/new`, `/users/<id>/toggle` | Administrator |
| Dashboard | `/`, `/dashboard` | any user |
| Analytics | `/analytics` | Admin, Treasurer, Organizer |
| Members | list, new, view, edit, `/<id>/pay`, `/<id>/renew` | Admin, Treasurer (list also Organizer) |
| Events | list, new, view, edit, `/<id>/sell`, `/<id>/register` | Admin, Organizer to manage; any user to register |
| Tickets | `/tickets/badge/<ref>`, `/tickets/download/<ref>`, `/tickets/checkin` | Admin, Organizer, Volunteer for check-in |
| JSON APIs | `POST /api/events/<id>/register`, `POST /api/tickets/checkin` | logged-in users / gate staff |
| Finance | `/finance`, `/finance/income/new` | Admin, Treasurer |
| Expenses | list, new, `/approve`, `/reject`, `/pay` | any user submits; Admin and Treasurer decide |
| Merchandise | list, new, `/variants/<id>/restock`, `/order` | Admin, Treasurer manage; any user orders |
| Tasks | list, new, `/<id>/status` | Admin, Organizer create; assignee updates |
| Announcements | list, new | Admin, Organizer post |
| Feedback | `/feedback`, `/feedback/<id>/status` | any user; Admin, Organizer review |
| Achievements and certificates | `/achievements`, `/certificates`, `/certificates/<ref>`, `/certificates/<ref>/pdf`, `/certificates/issue` | any user; Admin, Organizer issue |
| Memberships | `/my-memberships` | any user |
| Copilot | `/copilot`, `/copilot/ask`, `/copilot/clear` | Treasurer, Organizer, Volunteer, Member only |

### Core business logic worth knowing

**Event registration** (`process_event_registration`)
- Runs in a `BEGIN IMMEDIATE` transaction so two buyers cannot take the last seat.
- Rejects cancelled or full events.
- **Price is decided on the server**: member price only if the attendee matches an Active member whose membership has not expired.
- Optional idempotency key returns the existing ticket instead of creating a duplicate.
- Creates ticket reference `CS-TKT-<event>-<hex>`, a payment reference and a QR payload, and writes the ledger income row in the same transaction.
- Payment is **simulated** (`demo_success` / `simulate_failure`); no real gateway.

**Ticket check-in** (`process_ticket_checkin`)
- Possible outcomes: not found (`INVALID`), `CANCELLED_EVENT`, `WRONG_EVENT`, payment not eligible, already used (reports the earlier time and verifier), or success.
- Every attempt is written to `gate_checkin_logs`.

**Expenses**
- Lifecycle: `Pending` → `Approved` / `Rejected` → `Paid`.
- The ledger gets an `Expense` row **only when marked Paid**, using `UPDATE ... WHERE status='Approved'` plus a row-count check to block double payment.

**Merchandise**
- Orders deduct stock atomically; the `stock_quantity >= 0` constraint backs this up.

**Achievements**
- `award_achievement_points` ignores duplicates via the unique constraint.
- `calculate_user_badges` derives 8 badges from live counts (attendance, feedback, tasks, certificates, points).

**Certificates**
- Unique reference per certificate; PDF rendered with ReportLab; public verify page.

### AI Copilot (`copilot_service.py`)
- Builds a **role-filtered database context** (events, announcements, the user's membership, tasks; finance only for Treasurer).
- Deterministic engine answers common questions without any API key.
- If `GEMINI_API_KEY` or `OPENAI_API_KEY` is set, sends the context plus up to 8 recent turns to the provider; on failure it falls back to the deterministic answer.
- Mutation requests (approve expense, escalate role, and similar) are detected and refused.

### Tests (`tests/`)
Pytest suites cover auth, members, events and tickets, finances, merchandise, tasks, announcements, user management, dashboard, analytics, copilot, edge cases, connected workflows, engagement features, success feedback and event images/payment. I counted roughly **100 test functions**. I did not run them.

---

## B. Express + Prisma backend (`Odoo/server`)

### Stack
Express 4, Prisma 5 (SQLite), JWT, bcryptjs, Zod, Helmet, CORS, Morgan, QRCode, Vitest + Supertest.

### API (`/api/...`)
| Mount | Highlights |
|---|---|
| `/auth` | register, login, me, demo-accounts, reset-demo |
| `/organizations` | list, current, settings, provision |
| `/members` | list, update, verify status, renewal reminder, CSV import, plans, subscribe |
| `/events` | list, details, create, status, **book**, **check-in**, my tickets, ticket QR, cancel booking |
| `/announcements` | list, create, archive |
| `/merchandise` | products, checkout, my orders, low-stock, stock adjust |
| `/volunteers` | tasks, workload, fundraising campaigns, donations, expense claims and review |
| `/finance` | transactions, summary, reverse a transaction, budgets |
| `/analytics` | dashboard metrics, CSV export |
| `/ai` | copilot query |
| `/audit-logs`, `/notifications` | audit trail, in-app notifications |

### Data model (24 Prisma models)
`User`, `Organization`, `OrganizationMembership`, `MembershipPlan`, `MemberSubscription`, `MembershipPayment`, `Event`, `TicketType`, `Booking`, `Ticket`, `CheckIn`, `Announcement`, `Notification`, `MerchandiseProduct`, `ProductVariant`, `InventoryMovement`, `Order`, `OrderItem`, `Payment`, `FundraisingCampaign`, `VolunteerTask`, `TaskAssignment`, `ExpenseClaim`, `FinancialTransaction`, `Budget`, `AuditLog`.

### Access control
- Global `authenticate` middleware decodes the JWT and resolves the user's role inside the current organisation.
- `requireRoles([...])` per route, with a hierarchy where `CLUB_ADMIN` satisfies `TREASURER` and `EVENT_MANAGER` checks; `SUPER_ADMIN` bypasses.
- Roles: `SUPER_ADMIN`, `CLUB_ADMIN`, `TREASURER`, `EVENT_MANAGER`, `VOLUNTEER`, `MEMBER`, `STUDENT`.
- `server/src/tests/businessRules.test.ts` has 17 test cases.

---

## Issues I noticed

These are observations from reading the code; I did not test the apps.

**Flask app**
1. `app.run(..., debug=True)` is hard-coded at the bottom of `app.py`. The Werkzeug debugger must never be exposed on a real host.
2. No CSRF protection anywhere (zero matches for "csrf"); every POST form and `fetch` is unprotected.
3. `qrcode` is imported but missing from `requirements.txt` (the import is wrapped in try/except, so QR generation would silently be unavailable on a fresh install).
4. The schema allows tickets to be `Refunded` or `Cancelled`, but there is no route that cancels or refunds a ticket.
5. `app.py` is a 4,475-line single file; splitting into Flask blueprints (auth, members, events, finance, merchandise, engagement, copilot) would make it far easier to maintain.
6. README test counts (58 and 61) no longer match the test folder.

**Node app**
7. `middleware/auth.ts` falls back to a hard-coded JWT secret when `JWT_SECRET` is unset.
8. CORS is `origin: '*'` together with `credentials: true`.
9. `src/scripts/createKamalika.ts` creates a **super-admin** with a weak hard-coded password. Delete it or move the credentials to environment variables before sharing the project.
10. `prisma/dev.db`, `dist/` folders and (in the zip) the whole `venv/` and `node_modules/` are included; these should be git-ignored and left out of the archive.
