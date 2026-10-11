# CampusSphere AI
### Advanced Student Organization Management Platform
> *"One Campus. Every Club. One Intelligent Platform."*

---

## 🚀 Overview

**CampusSphere AI** is a production-minded, competition-quality unified management platform engineered for college clubs, student councils, campus societies, and nonprofit student organizations.

It replaces fragmented spreadsheets, notebook accounting, manual door check-in lists, scattered WhatsApp messages, stockout-prone merch inventory, and untracked volunteer tasks with a single, hardened full-stack platform.

---

## 🌟 Key Functional Modules

1. **Membership Management**:
   - Tiered membership programs (Standard, VIP Gold Pass, Honorary).
   - Member validity verification console (search by email or student ID with live status badge).
   - Bulk CSV Import & authorized CSV Export.
   - Renewal reminders with notification audit log.
   - Strict separation between unverified student registrations and verified paid memberships.

2. **Event Planning & QR Ticketing**:
   - Complete lifecycle: `DRAFT` → `PUBLISHED` → `SOLD_OUT` → `COMPLETED` / `CANCELLED`.
   - Seat capacity enforcement and atomic inventory reservation inside database transactions.
   - Server-side member vs. non-member pricing validation.
   - Encrypted QR code ticket wallet for students.
   - **Door Scanner Console**: Instant admission check-in with double-check-in prevention (`ALREADY_USED` rejection) and wrong event guards.
   - Ticket cancellations with automatic seat inventory restoration.

3. **Centralized Announcement Center**:
   - Targeted broadcasts by audience segment (`ALL_MEMBERS`, `ACTIVE_ONLY`, `VOLUNTEERS`, `EXECUTIVES`).
   - Category tagging (`GENERAL`, `URGENT`, `EVENT`, `ACADEMIC`, `OPPORTUNITY`).
   - Multi-channel delivery: In-app notification center + simulated email broadcast adapter.

4. **Merchandise Store & Stock Management**:
   - Product catalog with variant management (sizes `S`, `M`, `L`, `XL`, `One-Size` and colors).
   - Automatic active member discount calculation (e.g. 15% off).
   - Atomic checkout transaction preventing overselling or duplicate orders.
   - Inventory movement audit trail (`INITIAL`, `SALE`, `RESTOCK`, `RETURN`, `ADJUSTMENT`).
   - Low-stock threshold alerts for club managers.

5. **Volunteer Coordination & Fundraising**:
   - Interactive Volunteer Task Kanban Board (`TODO`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`).
   - Volunteer workload metrics and task priority tagging (`URGENT`, `HIGH`, `MEDIUM`, `LOW`).
   - Fundraising campaign drives with real-time verified donation progress.
   - **Expense Reimbursement Workflow**: Receipts upload, category assignment, and Treasurer review.
   - **Separation of Duties**: Strictly prevents users from approving their own expense claims; approved claims automatically generate a financial ledger expense entry.

6. **Financial Ledger & Accounting**:
   - Decimal-safe double-entry ledger tracking dues, tickets, merchandise sales, donations, venue deposits, and reimbursements.
   - Core Formula: `Total Settled Income − Total Settled Expenses = Recorded Net Balance`.
   - Distinct statuses: `SETTLED` vs. `PENDING` (pending claims do not count as settled cash).
   - Departmental Budget vs. Actual Expenditure utilization meters.
   - Immutable audit rule: Finalized records are never silently erased; auditable offsetting reversals are generated.
   - Full CSV ledger export.

7. **AI Club Operations Copilot**:
   - Integrated with authorized, tenant-filtered database metrics.
   - Performance summaries, overdue task summaries, announcement drafting, and financial health overviews.
   - Graceful offline fallback: Uses deterministic structured reasoning engine when no external API key is provided, or integrates seamlessly with Google Gemini 1.5 Flash when `GEMINI_API_KEY` is present.

8. **Security, Multi-Tenancy & Auditability**:
   - Role-Based Access Control (RBAC): `SUPER_ADMIN`, `CLUB_ADMIN`, `TREASURER`, `EVENT_MANAGER`, `VOLUNTEER`, `MEMBER`, `STUDENT`.
   - Organization tenant isolation on every protected endpoint.
   - Complete audit trail logging privileged actions.
   - 1-Click Competition Fast-Login strip in the UI header for smooth presentations.
   - Resettable demo environment button.

---

## 🛠️ Technology Stack

- **Frontend**:
  - React 18 & TypeScript
  - Vite (fast bundling & proxying)
  - Tailwind CSS (Midnight Navy `#05070e`, Electric Violet `#8b5cf6`, Electric Teal `#14b8a6`)
  - Lucide React Icons
  - Recharts (Analytics and financial graphs)
  - TanStack React Query (Server-state caching)
  - Canvas Confetti
- **Backend**:
  - Node.js & Express with TypeScript
  - Prisma ORM (26 normalized models, constraints, relations, and transactions)
  - Persistent SQLite database (zero external installation friction; portable across any machine)
  - JWT authentication & Bcrypt password hashing
  - Zod request validation
  - Helmet & CORS security middleware
- **Testing**:
  - Vitest & Supertest (Comprehensive integration test suite verifying 17 business rules)

---

## ⚡ Quick Start Guide

### 1. Install Dependencies
```bash
# Install root, server, and client packages
npm run install:all
```

### 2. Initialize Database & Seed Demo Data
```bash
# Generate Prisma Client, push SQLite database schema, and seed demo records
npm run seed
```

### 3. Start Full-Stack Application
```bash
# Starts backend server (port 5000) and frontend client (port 5173) concurrently
npm run dev
```
Open **[http://localhost:5173](http://localhost:5173)** in your browser.

---

## 🔑 Pre-Configured Demo Accounts (1-Click Switcher Available in UI)

| Role | Role Label | Email | Password | Access Scope |
| :--- | :--- | :--- | :--- | :--- |
| **SUPER_ADMIN** | Platform Super Admin | `superadmin@campussphere.edu` | `Admin@123` | Platform-wide health, multi-org provisioning |
| **CLUB_ADMIN** | Club President | `president@skyline.edu` | `Skyline@123` | Full club authority: events, merchandise, settings |
| **TREASURER** | Club Treasurer | `treasurer@skyline.edu` | `Skyline@123` | Financial ledger, expense review, budget tracking |
| **EVENT_MANAGER**| Event Manager | `events@skyline.edu` | `Skyline@123` | Event creation & live door QR ticket scanner |
| **VOLUNTEER** | Student Volunteer | `volunteer@skyline.edu` | `Skyline@123` | Assigned task board & reimbursement claims |
| **MEMBER** | Active Paid Member | `member@skyline.edu` | `Skyline@123` | VIP Gold discounts, ticket wallet & merch store |
| **STUDENT** | General Student | `student@skyline.edu` | `Skyline@123` | Non-member ticket booking & public store |

*Tip: You can switch between any of these accounts with a single click using the top competition control bar.*

---

## 🧪 Running Automated Tests

Run the full integration test suite:
```bash
npm test
```

This executes the Vitest suite in `server/src/tests/businessRules.test.ts` verifying:
- Active vs expired membership benefits.
- Prevention of administrative self-promotion.
- Seat limits and member discount calculation.
- Door check-in and duplicate check-in rejection (`ALREADY_USED`).
- Merchandise stock atomicity and overselling prevention.
- Separation of duties in expense approvals (self-approval forbidden).
- Automatic financial ledger synchronization.
- Traceable transaction reversals.
- AI Copilot tenant data isolation and fallback degradation.

---

## 📁 Repository Architecture

```
CampusSphere/
├── client/                     # React 18 + Vite + Tailwind frontend
│   ├── src/
│   │   ├── components/         # Modals, Navbar, Sidebar, AppLayout
│   │   ├── context/            # AuthContext (1-click role switcher)
│   │   ├── pages/              # 9 Full-featured management screens
│   │   ├── services/           # Typed API client
│   │   └── types/              # Domain TypeScript interfaces
│   └── vite.config.ts          # Port 5173 with proxy to backend port 5000
│
├── server/                     # Node.js + Express + Prisma REST API
│   ├── prisma/
│   │   ├── schema.prisma       # 26 entities with constraints & relations
│   │   ├── dev.db              # SQLite persistent database
│   │   └── seed.ts             # Repeatable factory seed script
│   ├── src/
│   │   ├── controllers/        # Domain controllers with Zod validation
│   │   ├── middleware/         # Auth, RBAC, tenant isolation, error handling
│   │   ├── routes/             # REST endpoints
│   │   ├── services/           # AI Copilot engine & email mock service
│   │   └── tests/              # Vitest integration test suite
│   └── tsconfig.json
│
├── REQUIREMENTS-COMPLIANCE.md  # Requirement Traceability Matrix (RTM)
├── package.json                # Unified root orchestrator
└── README.md
```

---

## 🏆 Competition Demonstration Flow

To reproduce the verified competition presentation from start to finish:

1. **Sign In**: Navigate to `http://localhost:5173/login` and click the **"🏛️ President"** preset card to enter as President Elena Rostova.
2. **Overview Dashboard**: Observe live KPIs, financial inflows/outflows bar chart, upcoming events, and recent ledger entries.
3. **Verify Membership**: Open **Membership Roster** → Click **Verify Member ID** → Search `member@skyline.edu` to observe the verified member green badge.
4. **Door Check-in Console**: Open **Events & Ticketing** → Click **Door Scanner Console** → Select *Skyline Tech & AI Summit 2026* → Enter ticket code `TKT-SKY-SUMMIT-9901` → Click **Validate & Admit** → Observe the green admission confirmation.
5. **Double Check-in Protection**: Click **Validate & Admit** again with the same ticket code → Observe the instant rejection alert confirming `Already Used: This ticket was already checked in!`.
6. **Store & Inventory**: Open **Merchandise Store** → Observe member discount badges (15% off) → Open **Stock Management** tab to inspect low-stock alerts.
7. **Volunteers & Expenses**: Open **Volunteers & Tasks** → View Kanban columns → Switch to **Expense Claims** tab to view pending receipts.
8. **Treasurer Financial Ledger**: Open **Financial Ledger** → Verify recorded balance, budget utilization meters, and transactions table.
9. **AI Copilot**: Open **AI Club Copilot** → Click *"Summarize this month's club performance"* → Receive structured summary grounded in real database records.
10. **Role Switcher**: Click the **"⭐ Member"** button in the top bar to instantly switch view to student Zara Patel.
