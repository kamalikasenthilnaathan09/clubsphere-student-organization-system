# ClubSphere: Student Organization System

A web app for running a student club: members, events and ticketing, finance, merchandise, volunteer tasks, announcements, analytics, achievements, certificates, feedback and an AI assistant.

Built for the **Odoo x NMIT Bangalore Hackathon 2026**.

## Team

- Y S Kamalika
- S Mahisa
- S Kanishka

## Repository layout

```
backend/    Flask app (app.py, database.py, seed_demo.py), tests, and the Express/Prisma server (node-server/)
frontend/   Flask templates, CSS, JS, images, and the React client (react-client/)
features/   AI Copilot, analytics, achievements, certificates and feedback code with their templates and tests
*.zip       Zipped copies of the three folders
```

The project contains two implementations:
- **ClubSphere (Flask + Jinja2 + SQLite):** the main app.
- **CampusSphere AI (React + Express + Prisma):** a second version in `frontend/react-client` and `backend/node-server`.

## Main features

- Role-based access: Administrator, Treasurer, Event Organizer, Volunteer, Member
- Member management with dues, part-payments and renewals
- Events with member and non-member pricing, QR tickets and a simulated payment popup
- Live ticket check-in console with duplicate detection and gate logs
- Finance ledger and an expense workflow (Pending, Approved or Rejected, Paid)
- Merchandise with size variants and stock tracking
- Volunteer task board, announcements, analytics charts
- Achievement points, badges, certificates (PDF) and a feedback center
- AI assistant that works with no API key, or with Gemini or OpenAI

## Run the Flask app

The Flask app needs `templates/` and `static/` next to `app.py`, so copy them into the backend folder first:

```bash
cp -r frontend/templates backend/templates
cp -r frontend/static backend/static
cp features/copilot_service.py backend/copilot_service.py
cd backend
pip install -r requirements.txt
pip install qrcode
cp .env.example .env      # optional: add GEMINI_API_KEY or OPENAI_API_KEY
python app.py --demo
```

Then open http://127.0.0.1:5000. `--demo` uses a pre-seeded demo database; the demo account names are in `seed_demo.py`. Without `--demo`, the first visit opens a setup page to create your Administrator account.

> `app.py` imports `copilot_service.py`, which lives in `features/`, so the copy step above is required.

On Windows PowerShell, use `Copy-Item -Recurse` instead of `cp -r`.

## Run the tests

```bash
cd backend
pytest
```

## Run the React / Node version (optional)

```bash
cd backend/node-server
npm install
npx prisma generate
npx prisma db push
npm run dev
```

```bash
cd frontend/react-client
npm install
npm run dev
```

Set `JWT_SECRET` in the Node server's environment before running it.

## Security notes

- Never commit a real `.env` file. Only `.env.example` belongs in the repo.
- `app.py` starts with `debug=True`; turn it off before any real deployment.
- The Flask forms have no CSRF protection yet.
- Payments are simulated; there is no real payment gateway.
