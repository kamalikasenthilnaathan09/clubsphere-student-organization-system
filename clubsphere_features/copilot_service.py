"""
copilot_service.py — ClubSphere Real-Time AI Assistant Service

Features:
1. Multi-Provider Generative AI:
   - Primary / Preferred: Google Gemini via modern `google-genai` SDK (with REST fallback)
   - Optional Alternative: OpenAI via chat completions API
   - Configurable model via GEMINI_MODEL, OPENAI_MODEL, or CLUB_AI_MODEL
2. Server-Side Role-Based Access Control (RBAC):
   - Derives identity and role exclusively from authenticated session
   - Strictly read-only: blocks mutation requests (approvals, payments, role edits)
   - Financial ledger numbers restricted exclusively to Treasurer and Administrator
3. Grounded Data Retrieval:
   - SQLite database is the sole source of truth for club records
   - Calculates available seats using authoritative ticket inventory logic: max(capacity - sold, 0)
   - Retrieves only the context necessary for the user's intent
4. Conversational Flow:
   - Natural greeting handling without dumping unprompted performance briefings
   - Multi-turn conversation history resolution for follow-ups (e.g., "Which one is happening first?", "How can I register?")
   - Clean deterministic fallback when no external API key is configured or on provider errors,
     without repeating setup warning notices on every message.
"""

import os
import json
import re
import logging
import urllib.request
import urllib.error
from datetime import date, datetime

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

logger = logging.getLogger('copilot')

ADMIN_ROLES = {'Administrator'}
FINANCIAL_ROLES = {'Administrator', 'Treasurer'}
MANAGEMENT_ROLES = {'Administrator', 'Treasurer', 'Event Organizer'}
TASK_ROLES = {'Administrator', 'Event Organizer', 'Volunteer'}


def format_currency(val):
    try:
        f = float(val or 0.0)
        return f"₹{f:,.2f}"
    except (ValueError, TypeError):
        return "₹0.00"


def get_ai_config():
    """
    Inspect server-side environment variables for configured AI provider keys.
    Secrets are NEVER exposed to the frontend or sent to client responses.
    """
    preferred_provider = os.environ.get('CLUB_AI_PROVIDER', '').strip().lower()
    gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
    openai_key = os.environ.get('OPENAI_API_KEY', '').strip()
    copilot_key = os.environ.get('COPILOT_API_KEY', '').strip()

    # Model configuration
    gemini_model = (
        os.environ.get('GEMINI_MODEL') or
        os.environ.get('CLUB_AI_MODEL') or
        'gemini-2.5-flash'
    ).strip()

    openai_model = (
        os.environ.get('OPENAI_MODEL') or
        os.environ.get('CLUB_AI_MODEL') or
        'gpt-4o-mini'
    ).strip()

    if preferred_provider == 'gemini' and gemini_key:
        return {'provider': 'gemini', 'key': gemini_key, 'model': gemini_model}
    elif preferred_provider == 'openai' and openai_key:
        return {'provider': 'openai', 'key': openai_key, 'model': openai_model}

    # Auto-detect: Gemini preferred, then OpenAI, then legacy COPILOT_API_KEY
    if gemini_key:
        return {'provider': 'gemini', 'key': gemini_key, 'model': gemini_model}
    elif openai_key:
        return {'provider': 'openai', 'key': openai_key, 'model': openai_model}
    elif copilot_key:
        return {'provider': 'copilot', 'key': copilot_key, 'model': 'default'}

    return None


# -----------------------------------------------------------------------------
# DATABASE RETRIEVAL FUNCTIONS (READ-ONLY & RBAC-ENFORCED)
# -----------------------------------------------------------------------------

def get_upcoming_events(db, limit=5):
    """Retrieve upcoming uncancelled events with authoritative available seats."""
    today = date.today().isoformat()
    rows = db.execute("""
        SELECT e.id, e.title, e.description, e.venue, e.event_date, e.event_time,
               e.capacity, e.member_price, e.non_member_price,
               COUNT(t.id) AS sold
        FROM events e
        LEFT JOIN tickets t ON e.id = t.event_id AND t.payment_status = 'Confirmed'
        WHERE e.event_date >= ? AND e.status != 'Cancelled'
        GROUP BY e.id
        ORDER BY e.event_date ASC, e.event_time ASC
        LIMIT ?
    """, (today, limit)).fetchall()

    events = []
    for e in rows:
        sold = int(e['sold'] or 0)
        cap = int(e['capacity'] or 0)
        events.append({
            'id': e['id'],
            'title': e['title'],
            'venue': e['venue'],
            'date': e['event_date'],
            'time': e['event_time'],
            'capacity': cap,
            'sold': sold,
            'remaining': max(cap - sold, 0),
            'member_price': float(e['member_price'] or 0.0),
            'nonmember_price': float(e['non_member_price'] or 0.0)
        })
    return events


def get_announcements_for_role(db, role, limit=5):
    """Retrieve published announcements matching the user's role audience."""
    allowed_audiences = ['All']
    if role in ('Member', 'Treasurer', 'Event Organizer', 'Volunteer', 'Administrator'):
        allowed_audiences.append('Members')
    if role in ('Volunteer', 'Event Organizer', 'Administrator'):
        allowed_audiences.append('Volunteers')
    if role in ('Treasurer', 'Event Organizer', 'Administrator'):
        allowed_audiences.append('Executive')

    placeholders = ','.join('?' for _ in allowed_audiences)
    rows = db.execute(f"""
        SELECT title, content, audience, priority, created_at
        FROM announcements
        WHERE audience IN ({placeholders})
        ORDER BY id DESC
        LIMIT ?
    """, (*allowed_audiences, limit)).fetchall()

    return [
        {
            'title': a['title'],
            'content': a['content'],
            'audience': a['audience'],
            'priority': a['priority'],
            'created_at': str(a['created_at'])
        }
        for a in rows
    ]


def get_user_membership(db, user_id, email=None):
    """Retrieve the authenticated user's own membership status and renewal details."""
    query = """
        SELECT member_code, full_name, membership_type, status, join_date, expiry_date, membership_fee, amount_paid
        FROM members
        WHERE user_id = ?
    """
    params = [user_id]
    if email:
        query += " OR LOWER(email) = LOWER(?)"
        params.append(email)
    query += " LIMIT 1"

    row = db.execute(query, params).fetchone()
    if not row:
        return None

    fee = float(row['membership_fee'] or 0.0)
    paid = float(row['amount_paid'] or 0.0)
    return {
        'member_code': row['member_code'],
        'full_name': row['full_name'],
        'membership_type': row['membership_type'],
        'status': row['status'],
        'join_date': str(row['join_date']),
        'expiry_date': str(row['expiry_date']),
        'membership_fee': fee,
        'amount_paid': paid,
        'balance': max(fee - paid, 0.0)
    }


def get_financial_summary(db, role):
    """
    Retrieve financial summary. Strictly restricted to Treasurer and Administrator.
    Returns unauthorized flag for other roles.
    """
    if role not in FINANCIAL_ROLES:
        return {
            'authorized': False,
            'reason': 'Financial ledger and cash records are restricted to Administrator and Treasurer accounts.'
        }

    inc_row = db.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM financial_transactions
        WHERE transaction_type = 'Income'
    """).fetchone()

    exp_row = db.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM financial_transactions
        WHERE transaction_type = 'Expense'
    """).fetchone()

    income = float(inc_row['total']) if inc_row else 0.0
    expenses = float(exp_row['total']) if exp_row else 0.0
    net_cash = income - expenses

    cat_rows = db.execute("""
        SELECT category, transaction_type, SUM(amount) AS total
        FROM financial_transactions
        GROUP BY category, transaction_type
    """).fetchall()

    pending_exp_row = db.execute("""
        SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total
        FROM expense_requests
        WHERE status = 'Pending'
    """).fetchone()

    return {
        'authorized': True,
        'recorded_income': income,
        'paid_expenses': expenses,
        'net_cash': net_cash,
        'categories': [{'category': r['category'], 'type': r['transaction_type'], 'total': float(r['total'])} for r in cat_rows],
        'pending_expenses_count': pending_exp_row['count'] if pending_exp_row else 0,
        'pending_expenses_total': float(pending_exp_row['total']) if pending_exp_row else 0.0
    }


def get_tasks_summary(db, user_id, role):
    """Retrieve volunteer task status filtered by user role permissions."""
    today = date.today().isoformat()
    if role in ('Administrator', 'Event Organizer'):
        overdue_tasks = db.execute("""
            SELECT t.id, t.title, t.priority, t.deadline, t.status, u.full_name AS assignee
            FROM volunteer_tasks t
            LEFT JOIN users u ON t.assigned_to = u.id
            WHERE t.deadline < ? AND t.status NOT IN ('Completed', 'Cancelled')
            ORDER BY t.deadline ASC
        """, (today,)).fetchall()

        upcoming_tasks = db.execute("""
            SELECT t.id, t.title, t.priority, t.deadline, t.status, u.full_name AS assignee
            FROM volunteer_tasks t
            LEFT JOIN users u ON t.assigned_to = u.id
            WHERE t.deadline >= ? AND t.status NOT IN ('Completed', 'Cancelled')
            ORDER BY t.deadline ASC
            LIMIT 5
        """, (today,)).fetchall()

        completed_count = db.execute("""
            SELECT COUNT(*) AS count FROM volunteer_tasks WHERE status = 'Completed'
        """).fetchone()['count']

        total_tasks_count = db.execute("""
            SELECT COUNT(*) AS count FROM volunteer_tasks
        """).fetchone()['count']

        return {
            'scope': 'organization_wide',
            'total_tasks': total_tasks_count,
            'completed_tasks': completed_count,
            'overdue': [{'id': t['id'], 'title': t['title'], 'priority': t['priority'], 'deadline': t['deadline'], 'status': t['status'], 'assignee': t['assignee']} for t in overdue_tasks],
            'upcoming': [{'id': t['id'], 'title': t['title'], 'priority': t['priority'], 'deadline': t['deadline'], 'status': t['status'], 'assignee': t['assignee']} for t in upcoming_tasks]
        }
    elif role == 'Volunteer':
        overdue_tasks = db.execute("""
            SELECT id, title, priority, deadline, status
            FROM volunteer_tasks
            WHERE assigned_to = ? AND deadline < ? AND status NOT IN ('Completed', 'Cancelled')
            ORDER BY deadline ASC
        """, (user_id, today)).fetchall()

        upcoming_tasks = db.execute("""
            SELECT id, title, priority, deadline, status
            FROM volunteer_tasks
            WHERE assigned_to = ? AND deadline >= ? AND status NOT IN ('Completed', 'Cancelled')
            ORDER BY deadline ASC
            LIMIT 5
        """, (user_id, today)).fetchall()

        return {
            'scope': 'assigned_to_user',
            'overdue': [{'id': t['id'], 'title': t['title'], 'priority': t['priority'], 'deadline': t['deadline'], 'status': t['status']} for t in overdue_tasks],
            'upcoming': [{'id': t['id'], 'title': t['title'], 'priority': t['priority'], 'deadline': t['deadline'], 'status': t['status']} for t in upcoming_tasks]
        }
    else:
        return {'scope': 'summary_only', 'overdue': [], 'upcoming': []}


# -----------------------------------------------------------------------------
# CONTEXT SELECTION & INTENT DETECTION
# -----------------------------------------------------------------------------

GREETING_WORDS = {
    'hey', 'hi', 'hello', 'heyy', 'heyyy', 'good morning', 'good afternoon',
    'good evening', 'howdy', 'sup', 'hiya', 'greetings', 'hey there',
    'hi there', 'hello there', 'yo'
}

ACKNOWLEDGEMENT_WORDS = {
    'thanks', 'thank you', 'thx', 'thank you so much', 'thanks a lot',
    'bye', 'goodbye', 'see you', 'see ya', 'cya', 'cheers'
}


def is_greeting(prompt_text):
    clean = re.sub(r'[^\w\s]', '', prompt_text.lower()).strip()
    if clean in GREETING_WORDS:
        return True
    words = clean.split()
    if words and words[0] in {'hey', 'hi', 'hello', 'yo', 'hiya', 'howdy'}:
        if len(words) <= 3 and any(w in words[1:] for w in {'copilot', 'assistant', 'clubsphere', 'bot', 'there', 'team', 'everyone'}):
            return True
    return False


def is_acknowledgement(prompt_text):
    clean = re.sub(r'[^\w\s]', '', prompt_text.lower()).strip()
    return clean in ACKNOWLEDGEMENT_WORDS


def is_mutation_request(prompt_text):
    p = prompt_text.lower()
    mutation_keywords = [
        'approve', 'pay expense', 'delete', 'change role', 'make admin',
        'grant access', 'update status', 'remove', 'issue refund', 'execute write'
    ]
    targets = ['expense', 'role', 'user', 'pay', 'ticket', 'member', 'admin']
    return any(k in p for k in mutation_keywords) and any(t in p for t in targets)


def is_followup_first_event(prompt_text, history):
    p = prompt_text.lower().strip()
    first_keywords = [
        'which one is happening first', 'which one is first', 'which is first',
        'which one happens first', 'which event is first', 'what is the first event',
        'which one is next', 'what event is first', 'which one first'
    ]
    if any(k in p for k in first_keywords):
        return True
    if 'which one' in p and ('first' in p or 'next' in p or 'earliest' in p or 'soonest' in p):
        return True
    return False


def fetch_database_context(db, user, prompt_text=None, history=None):
    """
    Extract verified, deterministic context from SQLite database
    strictly according to the user's authenticated database role and message intent.
    Does NOT query every table for every message.
    """
    user_id = user['id']
    role = user['role']
    user_name = user.get('full_name', 'Student')
    user_email = user.get('email')
    today = date.today().isoformat()

    context = {
        'role': role,
        'user_name': user_name,
        'today': today
    }

    p = (prompt_text or '').lower().strip()

    # If simple greeting or acknowledgement, minimal context is sufficient
    if is_greeting(p) or is_acknowledgement(p):
        return context

    # Check intents
    wants_events = (
        'event' in p or 'schedule' in p or 'when' in p or 'venue' in p or
        'ticket' in p or 'register' in p or 'coming up' in p or
        is_followup_first_event(p, history)
    )
    wants_announcements = 'announcement' in p or 'notice' in p or 'broadcast' in p
    wants_membership = 'membership' in p or 'member status' in p or 'my status' in p or 'dues' in p
    wants_finances = (
        'income' in p or 'expense' in p or 'net cash' in p or 'finance' in p or
        'budget' in p or 'ledger' in p or 'cash reserve' in p
    )
    wants_tasks = 'task' in p or 'deadline' in p or 'volunteer' in p or 'overdue' in p
    wants_summary = 'performance' in p or 'briefing' in p or 'summary' in p or 'overview' in p

    # 1. Events context
    if wants_events or wants_summary:
        upcoming_events = get_upcoming_events(db, limit=5)
        past_events_count = db.execute(
            "SELECT COUNT(*) AS count FROM events WHERE event_date < ? AND status != 'Cancelled'",
            (today,)
        ).fetchone()['count']
        total_tickets_sold = db.execute(
            "SELECT COUNT(*) AS count FROM tickets WHERE payment_status = 'Confirmed'"
        ).fetchone()['count']

        context['events'] = {
            'upcoming': upcoming_events,
            'upcoming_count': len(upcoming_events),
            'past_events_count': past_events_count,
            'total_tickets_sold': total_tickets_sold
        }

    # 2. Announcements context
    if wants_announcements or wants_summary:
        context['announcements'] = get_announcements_for_role(db, role, limit=5)

    # 3. User Membership context
    if wants_membership or wants_summary:
        context['user_membership'] = get_user_membership(db, user_id, user_email)

    # 4. Financial context (strictly RBAC enforced)
    if wants_finances or wants_summary:
        context['finances'] = get_financial_summary(db, role)

    # 5. Tasks context
    if wants_tasks or wants_summary:
        context['tasks'] = get_tasks_summary(db, user_id, role)

    # 6. Organization-wide membership totals (Executive / Management roles only)
    if wants_summary and role in MANAGEMENT_ROLES:
        total_mem = db.execute("SELECT COUNT(*) AS count FROM members").fetchone()['count']
        act_mem = db.execute(
            "SELECT COUNT(*) AS count FROM members WHERE status = 'Active' AND expiry_date >= ?",
            (today,)
        ).fetchone()['count']
        dues_row = db.execute("""
            SELECT COALESCE(SUM(CASE WHEN membership_fee > amount_paid THEN membership_fee - amount_paid ELSE 0 END), 0) AS dues
            FROM members WHERE status IN ('Active', 'Pending')
        """).fetchone()
        context['members'] = {
            'authorized': True,
            'total_members': total_mem,
            'active_members': act_mem,
            'outstanding_dues': float(dues_row['dues']) if dues_row else 0.0
        }

    return context


# -----------------------------------------------------------------------------
# DETERMINISTIC RESPONSE GENERATOR (ACCURATE & AUDIT-PROOF FALLBACK)
# -----------------------------------------------------------------------------

def generate_deterministic_response(prompt_text, context, history=None):
    """
    Build 100% deterministic, audit-proof responses directly from database context.
    Never fabricates figures, records, or members.
    Clearly indicates when records are empty or access is restricted.
    """
    p = prompt_text.lower().strip()
    role = context['role']
    user_name = context.get('user_name', 'Student')

    # Security Guard: Mutation attempts blocked
    if is_mutation_request(p):
        return (
            "🔒 **Security Notice**: Club Copilot operates in **read-only** advisory and drafting mode. "
            "It cannot modify database records, approve expense vouchers, trigger ledger payments, or alter user permissions. "
            "Please use the official ClubSphere management modules (e.g., [Expenses](/expenses) or [User Directory](/users)) "
            "with appropriate role authorization to complete these actions."
        )

    # 1. GREETING INTENT (e.g. "Hey", "Hi", "Hello")
    if is_greeting(p):
        return (
            f"Hey {user_name}! 👋 How can I help you with ClubSphere today?\n\n"
            f"You can ask me about:\n"
            f"- 📅 **Upcoming events & dates**\n"
            f"- 🎟️ **How to register for an event**\n"
            f"- 📢 **Latest club announcements**\n"
            f"- 👤 **Checking your membership status**\n"
            + (f"- 💰 **Financial ledger & cash balance**\n" if role in FINANCIAL_ROLES else "")
            + (f"- ⏰ **Volunteer task deadlines**\n" if role in TASK_ROLES else "")
        )

    # 2. ACKNOWLEDGEMENT INTENT (e.g. "Thanks", "Bye")
    if is_acknowledgement(p):
        if any(w in p for w in ['bye', 'goodbye', 'see you', 'see ya', 'cya']):
            return f"Goodbye {user_name}! Have a great day on campus! 👋"
        return f"You're very welcome, {user_name}! Let me know if you need any more assistance with your club activities. 😊"

    # 3. FOLLOW-UP: WHICH EVENT IS HAPPENING FIRST?
    if is_followup_first_event(p, history):
        events = context.get('events', {}).get('upcoming', [])
        if not events:
            return (
                "📅 **Event Schedule**:\n\n"
                "ℹ️ *There are currently no upcoming events scheduled in the club calendar.*\n\n"
                "Check back soon or browse previous events under [Events & Tickets](/events)."
            )
        first_ev = events[0]
        return (
            f"🎯 **{first_ev['title']}** is happening first!\n\n"
            f"- **Date & Time**: 🗓️ `{first_ev['date']}` at `{first_ev['time']}`\n"
            f"- **Venue**: 📍 {first_ev['venue']}\n"
            f"- **Available Seats**: ⚡ **{first_ev['remaining']}** seats left (Capacity: {first_ev['capacity']})\n"
            f"- **Ticket Rates**: 🎟️ **{format_currency(first_ev['member_price'])}** (Members) | **{format_currency(first_ev['nonmember_price'])}** (General)\n\n"
            f"👉 *You can register for your pass on the [Events & Tickets](/events) page.*"
        )

    # 4. MEMBERSHIP STATUS PROMPT
    if ('membership' in p and ('status' in p or 'check' in p or 'my' in p or 'tier' in p or 'renewal' in p)) or \
       'how do i check my membership status' in p or 'check my membership status' in p:
        user_mem = context.get('user_membership')
        if user_mem:
            return (
                f"👤 **Your ClubSphere Membership Status**:\n\n"
                f"- **Member Code**: `{user_mem['member_code']}`\n"
                f"- **Full Name**: **{user_mem['full_name']}**\n"
                f"- **Membership Tier**: **{user_mem['membership_type']}**\n"
                f"- **Status**: **{user_mem['status']}**\n"
                f"- **Join Date**: `{user_mem['join_date']}`\n"
                f"- **Expiry Date**: `{user_mem['expiry_date']}`\n"
                f"- **Dues / Balance**: Paid **{format_currency(user_mem['amount_paid'])}** of **{format_currency(user_mem['membership_fee'])}** (Outstanding Balance: **{format_currency(user_mem['balance'])}**)\n\n"
                f"💡 *You can view your complete membership details and password settings under [Profile](/profile).*"
            )
        else:
            return (
                f"ℹ️ **Membership Status Check**:\n\n"
                f"No active membership record is currently linked to your user account (**{user_name}**).\n\n"
                f"**How to check or activate your membership**:\n"
                f"1. Navigate to your account [Profile](/profile) to view your account details.\n"
                f"2. View available membership plans under [Memberships](/members).\n"
                f"3. Contact your club treasurer to activate your student membership code."
            )

    # 5. EVENT REGISTRATION INSTRUCTIONS
    if ('register' in p and ('event' in p or 'how' in p or 'ticket' in p or 'pass' in p)) or \
       'how can i register' in p or 'how do i register' in p:
        events = context.get('events', {}).get('upcoming', [])
        ev_list_text = ""
        if events:
            lines = ["\n\n**Currently Open for Registration**:"]
            for ev in events:
                lines.append(f"- **{ev['title']}** &bull; `{ev['date']}` at `{ev['time']}` &bull; {ev['venue']} (Seats remaining: **{ev['remaining']}/{ev['capacity']}**)")
            ev_list_text = "\n".join(lines)

        return (
            "🎟️ **How to Register for an Event**:\n\n"
            "1. Navigate to **[Events & Tickets](/events)** from your navigation sidebar.\n"
            "2. Browse scheduled events and select the one you wish to attend.\n"
            "3. Select your ticket tier — **Active Members** automatically receive discounted member pricing!\n"
            "4. Confirm your registration to generate your unique ticket pass code (e.g. `CS-TKT-...`).\n"
            "5. Present your digital ticket code at the venue gate for instant check-in."
            f"{ev_list_text}"
        )

    # 6. UPCOMING EVENTS & EVENT DATES
    if ('what events' in p or 'coming up' in p or 'upcoming event' in p or 'event date' in p or
        ('event' in p and ('date' in p or 'when' in p or 'schedule' in p or 'next' in p or 'list' in p))) and 'draft' not in p and 'announcement' not in p:
        events = context.get('events', {}).get('upcoming', [])
        if not events:
            return (
                "📅 **Upcoming Club Events**:\n\n"
                "ℹ️ *There are currently no upcoming events scheduled in the club calendar.*\n\n"
                "Please check back soon or browse past events in [Events & Tickets](/events)."
            )

        lines = ["📅 **Upcoming Club Events & Schedules**:\n"]
        for ev in events:
            lines.append(
                f"### 🎯 {ev['title']}\n"
                f"- **Date & Time**: 🗓️ `{ev['date']}` at `{ev['time']}`\n"
                f"- **Venue**: 📍 {ev['venue']}\n"
                f"- **Available Seats**: ⚡ **{ev['remaining']}** seats left (Capacity: {ev['capacity']})\n"
                f"- **Ticket Rates**: 🎟️ **{format_currency(ev['member_price'])}** (Members) | **{format_currency(ev['nonmember_price'])}** (General)\n"
            )
        lines.append("👉 *To reserve your seat, visit [Events & Tickets](/events) and select your event.*")
        return "\n".join(lines)

    # 7. SHOW LATEST CLUB ANNOUNCEMENTS
    if ('announcement' in p and 'draft' not in p) or 'latest club announcement' in p or 'latest announcement' in p or 'noticeboard' in p or 'show the latest' in p:
        ann = context.get('announcements', [])
        if not ann:
            return (
                "📢 **Club Noticeboard**:\n\n"
                "ℹ️ *There are currently no active announcements posted on the club noticeboard.*"
            )

        lines = ["📢 **Latest Club Announcements**:\n"]
        for a in ann:
            priority_tag = f" `[{a['priority']}]`" if a.get('priority') and a['priority'] != 'Normal' else ""
            lines.append(
                f"**{a['title']}**{priority_tag} *(Audience: {a.get('audience', 'All')})*\n"
                f"> {a.get('content', '')}\n"
                f"*(Posted: {a.get('created_at', '')})*\n"
            )
        lines.append("👉 *View full noticeboard on the [Announcements](/announcements) page.*")
        return "\n".join(lines)

    # 8. FINANCIAL SUMMARY PROMPT
    if 'income' in p or 'expense' in p or 'net cash' in p or 'finance' in p or 'budget' in p or 'ledger' in p:
        fin = context.get('finances') or {}
        if not fin.get('authorized'):
            return (
                f"🚫 **Access Restricted**: Financial ledger details and cash reserves are visible only to **Treasurer** roles.\n\n"
                f"Your account is currently signed in as **{role}**. You can ask about scheduled events, registration, announcements, or your membership status."
            )

        inc = fin['recorded_income']
        exp = fin['paid_expenses']
        net = fin['net_cash']
        pending_c = fin['pending_expenses_count']
        pending_amt = fin['pending_expenses_total']

        if inc == 0.0 and exp == 0.0:
            return (
                "📊 **Financial Ledger Overview**:\n\n"
                "- **Total Recorded Income**: ₹0.00\n"
                "- **Total Paid Expenses**: ₹0.00\n"
                "- **Net Cash Position**: ₹0.00\n\n"
                "ℹ️ *No financial transactions have been posted to the ledger yet. Income from confirmed tickets, membership dues, and merchandise will appear automatically once recorded.*"
            )

        breakdown_lines = []
        for cat in fin.get('categories', []):
            breakdown_lines.append(f"  • {cat['category']} ({cat['type']}): {format_currency(cat['total'])}")
        breakdown_text = "\n".join(breakdown_lines) if breakdown_lines else "  • No itemized categories recorded."

        return (
            f"💰 **ClubSphere Financial Analysis**:\n\n"
            f"- **Total Recorded Income**: **{format_currency(inc)}**\n"
            f"- **Total Paid Expenses**: **{format_currency(exp)}**\n"
            f"- **Net Cash Reserves**: **{format_currency(net)}**\n\n"
            f"**Itemized Breakdown**:\n{breakdown_text}\n\n"
            f"**Pending Expense Requests**: {pending_c} request(s) totaling **{format_currency(pending_amt)}** are currently awaiting review. "
            f"*(Note: Under ClubSphere's cash accounting rules, pending requests do not reduce net cash until approved and marked Paid).* "
        )

    # 9. OVERDUE TASKS & DEADLINES PROMPT
    if 'overdue' in p or 'deadline' in p or 'task' in p or 'volunteer' in p:
        tasks = context.get('tasks') or {}
        overdue = tasks.get('overdue', [])
        upcoming = tasks.get('upcoming', [])

        lines = []
        if overdue:
            lines.append("⚠️ **Overdue Volunteer Tasks**:")
            for t in overdue:
                assignee_str = f" — Assigned to: *{t.get('assignee', 'Volunteer')}*" if t.get('assignee') else ""
                lines.append(f"- **{t['title']}** [{t['priority']} Priority] &bull; Due: `{t['deadline']}`{assignee_str}")
        else:
            lines.append("✅ **No Overdue Tasks**: All recorded volunteer tasks are on schedule.")

        if upcoming:
            lines.append("\n📅 **Upcoming Task Deadlines**:")
            for t in upcoming:
                assignee_str = f" — Assignee: *{t.get('assignee', 'Volunteer')}*" if t.get('assignee') else ""
                lines.append(f"- **{t['title']}** [{t['priority']}] &bull; Deadline: `{t['deadline']}`{assignee_str}")
        elif not overdue:
            lines.append("\nℹ️ *No pending volunteer tasks found in the database.*")

        return "\n".join(lines)

    # 10. DRAFT ANNOUNCEMENT PROMPT
    if 'announcement' in p or 'draft' in p or 'broadcast' in p:
        events = context.get('events', {}).get('upcoming', [])
        if not events:
            return (
                "📢 **Announcement Drafting Assistant**:\n\n"
                "ℹ️ *No upcoming events are currently scheduled in the database.*\n\n"
                "Here is a customizable general template:\n\n"
                "```markdown\n"
                "Subject: Upcoming Club Meeting & Activity Briefing\n"
                "Audience: All Members\n\n"
                "Dear ClubSphere Community,\n"
                "We are finalizing details for our upcoming activities. Check the ClubSphere portal "
                "for event registration, merchandise collections, and volunteer task sign-ups.\n"
                "```\n\n"
                "💡 *Tip: Schedule an event under [Events & Tickets](/events) so Copilot can draft an announcement with real date, venue, and pricing data.*"
            )

        ev = events[0]
        return (
            f"📢 **Draft Announcement for Upcoming Event**:\n\n"
            f"```markdown\n"
            f"Title: 🚀 Join Us for {ev['title']}!\n"
            f"Audience: All Members & Students\n"
            f"Priority: Important\n\n"
            f"Hello Campus Community,\n\n"
            f"We are excited to announce our upcoming event: **{ev['title']}**!\n\n"
            f"📅 Date: {ev['date']} at {ev['time']}\n"
            f"📍 Venue: {ev['venue']}\n"
            f"🎟️ Passes: {format_currency(ev['member_price'])} for Members | {format_currency(ev['nonmember_price'])} General\n"
            f"⚡ Seats: Only {ev['remaining']} of {ev['capacity']} seats remaining!\n\n"
            f"Secure your pass now through your ClubSphere account before capacity is reached.\n"
            f"```\n\n"
            f"✨ *Drafted using real event records for '{ev['title']}' from your database.*"
        )

    # 11. EXECUTIVE PERFORMANCE SUMMARY (Triggered ONLY when user explicitly asks for performance/briefing/summary)
    if 'performance' in p or 'summary' in p or 'briefing' in p or 'overview' in p:
        fin = context.get('finances')
        ev_ctx = context.get('events') or {}
        mem_ctx = context.get('members') or {}
        tsk_ctx = context.get('tasks') or {}

        sections = [f"📊 **ClubSphere Performance Briefing** *(Role: {role})*:\n"]

        # Memberships
        if mem_ctx.get('authorized'):
            sections.append(
                f"👥 **Membership Health**:\n"
                f"- Total Registered Members: **{mem_ctx['total_members']}**\n"
                f"- Active Unexpired Members: **{mem_ctx['active_members']}**\n"
                f"- Outstanding Dues Balance: **{format_currency(mem_ctx['outstanding_dues'])}**"
            )
        else:
            sections.append("👥 **Membership**: Detailed roster metrics restricted to officers.")

        # Events
        up_cnt = ev_ctx.get('upcoming_count', 0)
        tkt_sold = ev_ctx.get('total_tickets_sold', 0)
        next_ev_str = f"Next up: *{ev_ctx['upcoming'][0]['title']}* ({ev_ctx['upcoming'][0]['date']})" if up_cnt > 0 else "No upcoming events scheduled."
        sections.append(
            f"\n📅 **Events & Turnout**:\n"
            f"- Scheduled Upcoming Events: **{up_cnt}**\n"
            f"- Total Confirmed Ticket Sales: **{tkt_sold}**\n"
            f"- {next_ev_str}"
        )

        # Finances
        if fin and fin.get('authorized'):
            sections.append(
                f"\n💰 **Financial Ledger Status**:\n"
                f"- Recorded Income: **{format_currency(fin['recorded_income'])}**\n"
                f"- Paid Expenses: **{format_currency(fin['paid_expenses'])}**\n"
                f"- Net Cash Reserves: **{format_currency(fin['net_cash'])}**"
            )
        else:
            sections.append("\n💰 **Financial Ledger**: Restricted to Treasurer and Administrator accounts.")

        # Tasks
        if tsk_ctx.get('scope') == 'organization_wide':
            ov_cnt = len(tsk_ctx.get('overdue', []))
            comp_cnt = tsk_ctx.get('completed_tasks', 0)
            tot_tsk = tsk_ctx.get('total_tasks', 0)
            sections.append(
                f"\n📋 **Volunteer Tasks**:\n"
                f"- Completed Tasks: **{comp_cnt}** / {tot_tsk}\n"
                f"- Overdue Tasks Flagged: **{ov_cnt}**"
            )
        elif tsk_ctx.get('scope') == 'assigned_to_user':
            ov_cnt = len(tsk_ctx.get('overdue', []))
            up_cnt = len(tsk_ctx.get('upcoming', []))
            sections.append(
                f"\n📋 **Your Assigned Tasks**:\n"
                f"- Overdue: **{ov_cnt}** | Pending: **{up_cnt}**"
            )

        return "\n".join(sections)

    # 12. GENERAL CONVERSATIONAL FALLBACK (Polite, helpful, no unprompted briefings)
    return (
        f"Hey {user_name}! 👋 How can I help you with ClubSphere campus organization activities today?\n\n"
        f"You can ask me questions such as:\n"
        f"- 📅 *\"What events are coming up?\"*\n"
        f"- 🎟️ *\"How can I register for an event?\"*\n"
        f"- 📢 *\"Show the latest club announcements.\"*\n"
        f"- 👤 *\"How do I check my membership status?\"*\n"
        + (f"- 💰 *\"Explain our income, expenses, and net cash.\"*\n" if role in FINANCIAL_ROLES else "")
        + (f"- ⏰ *\"Identify overdue tasks and upcoming deadlines.\"*\n" if role in TASK_ROLES else "")
    )


# -----------------------------------------------------------------------------
# GENERATIVE AI INTEGRATION (GEMINI SDK / REST & OPENAI)
# -----------------------------------------------------------------------------

def build_system_instruction(context):
    role = context.get('role', 'Member')
    user_name = context.get('user_name', 'Student')
    return (
        f"You are ClubSphere AI Assistant, a friendly, professional, and knowledgeable conversational assistant for student organizations.\n"
        f"The user speaking with you is named {user_name}, and their verified database role is '{role}'.\n\n"
        f"STRICT BEHAVIOR RULES:\n"
        f"1. GREETINGS: If the user says 'Hey', 'Hi', 'Hello', or similar pleasantries, respond warmly: "
        f"'Hey {user_name}! 👋 How can I help you with ClubSphere today?' "
        f"DO NOT return analytics, financial figures, event schedules, or performance briefings unless specifically asked.\n"
        f"2. ACCURACY: Answer using ONLY the verified SQLite database records provided in the context. Never fabricate event dates, venues, ticket counts, pricing, members, or financial numbers.\n"
        f"3. MISSING RECORDS: If no events or records exist, explicitly state that none are scheduled. If the user asks about membership and none is linked, state that clearly.\n"
        f"4. FOLLOW-UPS: Use the recent conversation history to understand pronouns and references (e.g. 'Which one is happening first?' refers to events discussed earlier; 'How can I register?' refers to ticket registration).\n"
        f"5. ROLE PERMISSIONS: The user's role is strictly '{role}'. Financial ledger balances, expenses, and cash reserves are visible ONLY to 'Treasurer' and 'Administrator'. If a user without permission asks about finances or other members' private records, politely decline and inform them that access is restricted to authorized officers.\n"
        f"6. READ-ONLY: You are strictly read-only. Never attempt to approve expenses, register tickets, change permissions, or execute database updates. Provide instructions and link to the relevant ClubSphere page (e.g. [Events & Tickets](/events), [Profile](/profile), [Announcements](/announcements)).\n"
        f"7. FORMATTING: Keep responses concise, readable, and well-structured using Markdown headings, bold highlights, bullet points, and links."
    )


def call_gemini(prompt_text, context, history, ai_config):
    """
    Call Google Gemini via modern `google-genai` SDK, with automatic REST API fallback.
    """
    model_name = ai_config.get('model') or 'gemini-2.5-flash'
    api_key = ai_config['key']
    system_instruction = build_system_instruction(context)

    context_json = json.dumps(context, indent=2)
    user_payload = f"Current Database Context:\n```json\n{context_json}\n```\n\nUser Question:\n{prompt_text}"

    # Method A: Modern google-genai SDK
    if genai is not None:
        try:
            client = genai.Client(api_key=api_key)

            contents = []
            if history:
                for turn in history[-6:]:
                    role = 'user' if turn.get('role') == 'user' else 'model'
                    text_content = turn.get('content', '')
                    if text_content:
                        part = types.Part.from_text(text=text_content) if types else text_content
                        content_obj = types.Content(role=role, parts=[part]) if types else {"role": role, "parts": [{"text": text_content}]}
                        contents.append(content_obj)

            user_part = types.Part.from_text(text=user_payload) if types else user_payload
            user_content_obj = types.Content(role='user', parts=[user_part]) if types else {"role": "user", "parts": [{"text": user_payload}]}
            contents.append(user_content_obj)

            config_arg = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3,
                max_output_tokens=800,
            ) if types else None

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config_arg
            )
            if response and response.text:
                return {'success': True, 'text': response.text.strip(), 'provider': f'Google Gemini ({model_name})'}
        except Exception as sdk_err:
            logger.warning(f"google-genai SDK call failed, attempting REST API: {sdk_err}")

    # Method B: Direct REST API via urllib.request (graceful fallback)
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        contents_payload = []
        if history:
            for turn in history[-6:]:
                role = 'user' if turn.get('role') == 'user' else 'model'
                text_content = turn.get('content', '')
                if text_content:
                    contents_payload.append({
                        "role": role,
                        "parts": [{"text": text_content}]
                    })

        contents_payload.append({
            "role": "user",
            "parts": [{"text": user_payload}]
        })

        payload = {
            "contents": contents_payload,
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 800
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            candidates = data.get('candidates', [])
            if candidates:
                text = candidates[0]['content']['parts'][0]['text']
                return {'success': True, 'text': text.strip(), 'provider': f'Google Gemini ({model_name})'}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='ignore') if hasattr(e, 'read') else str(e)
        logger.error(f"Gemini REST HTTP error {e.code}: {error_body}")
        return {'success': False, 'error': f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        logger.error(f"Gemini REST error: {e}")
        return {'success': False, 'error': str(e)}

    return {'success': False, 'error': 'Gemini returned an empty response'}


def call_openai(prompt_text, context, history, ai_config):
    """Call OpenAI chat completions API with timeout and error handling."""
    model_name = ai_config.get('model') or 'gpt-4o-mini'
    api_key = ai_config['key']
    system_instruction = build_system_instruction(context)

    context_json = json.dumps(context, indent=2)
    user_payload = f"Current Database Context:\n```json\n{context_json}\n```\n\nUser Question:\n{prompt_text}"

    messages = [{"role": "system", "content": system_instruction}]
    if history:
        for turn in history[-6:]:
            role = 'user' if turn.get('role') == 'user' else 'assistant'
            text_content = turn.get('content', '')
            if text_content:
                messages.append({"role": role, "content": text_content})
    messages.append({"role": "user", "content": user_payload})

    try:
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 800
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {api_key}"
            }
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            choices = data.get('choices', [])
            if choices:
                text = choices[0]['message']['content']
                return {'success': True, 'text': text.strip(), 'provider': f'OpenAI ({model_name})'}
    except urllib.error.HTTPError as e:
        logger.error(f"OpenAI HTTP error {e.code}: {e.reason}")
        return {'success': False, 'error': f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return {'success': False, 'error': str(e)}

    return {'success': False, 'error': 'OpenAI returned an empty response'}


def call_external_ai(prompt_text, context, history, ai_config):
    """
    Route request to configured generative AI provider.
    Maintains clean separation, strict role-filtered context, and timeouts.
    """
    provider = ai_config['provider']
    if provider == 'gemini':
        return call_gemini(prompt_text, context, history, ai_config)
    elif provider == 'openai':
        return call_openai(prompt_text, context, history, ai_config)
    return {'success': False, 'error': f"Unsupported provider: {provider}"}


# -----------------------------------------------------------------------------
# PRIMARY SERVICE ENTRY POINT
# -----------------------------------------------------------------------------

def ask_copilot(db, user, prompt_text, history=None):
    """
    Primary Copilot entry point:
    1. Validates authenticated user and prompt text.
    2. Extracts role-authorized context from SQLite database.
    3. If an external AI provider (Gemini or OpenAI) is configured, calls it with grounded context and history.
    4. If the provider succeeds, returns the generative AI completion.
    5. If provider fails, falls back gracefully to verified deterministic records.
    6. If NO provider key is configured, operates cleanly in deterministic mode without repeating setup warnings.
    """
    if not prompt_text or not prompt_text.strip():
        return {
            'status': 'error',
            'message': 'Please provide a question or select a suggested prompt.'
        }

    clean_prompt = prompt_text.strip()
    history = history or []

    # 1. Fetch authorized database context
    context = fetch_database_context(db, user, prompt_text=clean_prompt, history=history)

    # 2. Build deterministic response
    deterministic_answer = generate_deterministic_response(clean_prompt, context, history=history)

    # 3. Check for external AI configuration
    ai_config = get_ai_config()

    if ai_config:
        ai_res = call_external_ai(clean_prompt, context, history, ai_config)
        if ai_res.get('success'):
            return {
                'status': 'ok',
                'response': ai_res['text'],
                'provider': ai_res['provider'],
                'mode': 'generative_ai',
                'prompt': clean_prompt
            }
        else:
            # AI Provider failed (invalid key, timeout, etc.): gracefully fall back
            fallback_text = (
                f"> ⚠️ **AI Provider Notice**: Connection to external AI provider encountered an issue ({ai_res.get('error', 'Unknown error')}). "
                f"Falling back to verified deterministic ClubSphere records:\n\n{deterministic_answer}"
            )
            return {
                'status': 'ok',
                'response': fallback_text,
                'provider': 'Deterministic Fallback',
                'mode': 'fallback',
                'error': ai_res.get('error'),
                'prompt': clean_prompt
            }
    else:
        # Deterministic mode: clean, authoritative answer WITHOUT repeated setup notice
        return {
            'status': 'ok',
            'response': deterministic_answer,
            'provider': 'Deterministic Engine',
            'mode': 'deterministic',
            'prompt': clean_prompt
        }
