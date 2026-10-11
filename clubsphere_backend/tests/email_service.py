import os
import re
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Global test hooks to simulate partial or complete SMTP failures during automated tests
TEST_SIMULATE_SMTP_FAILURE = False
TEST_SMTP_FAIL_EMAILS = set()


def mask_email(email):
    """Safely mask an email address for logging without leaking full PII."""
    if not email or '@' not in email:
        return '***@***.***'
    parts = email.split('@')
    name = parts[0]
    domain = parts[1]
    if len(name) <= 2:
        masked_name = name[:1] + '*'
    else:
        masked_name = name[0] + '***' + name[-1]
    return f"{masked_name}@{domain}"


def get_email_config():
    """Retrieve SMTP configuration from environment variables."""
    smtp_server = os.environ.get('MAIL_SERVER') or os.environ.get('SMTP_HOST')
    smtp_port = int(os.environ.get('MAIL_PORT') or os.environ.get('SMTP_PORT') or 587)
    smtp_user = os.environ.get('MAIL_USERNAME') or os.environ.get('SMTP_USER')
    smtp_pass = os.environ.get('MAIL_PASSWORD') or os.environ.get('SMTP_PASSWORD')
    smtp_use_tls = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 'yes')
    default_sender = (
        os.environ.get('MAIL_DEFAULT_SENDER')
        or os.environ.get('FROM_EMAIL')
        or 'ClubSphere Announcements <no-reply@clubsphere.org>'
    )
    
    mock_override = os.environ.get('EMAIL_MOCK_MODE', '').lower() in ('true', '1', 'yes')
    is_mock = mock_override or not smtp_server

    return {
        'server': smtp_server,
        'port': smtp_port,
        'user': smtp_user,
        'password': smtp_pass,
        'use_tls': smtp_use_tls,
        'default_sender': default_sender,
        'is_mock': is_mock
    }


def send_single_email(recipient_email, recipient_name, subject, body_text, config, club_name=None):
    """
    Send an email to a single recipient preserving privacy.
    Returns (success: bool, error_message: str or None)
    """
    global TEST_SIMULATE_SMTP_FAILURE, TEST_SMTP_FAIL_EMAILS

    # 1. Check test simulation overrides
    if TEST_SIMULATE_SMTP_FAILURE:
        return False, "Simulated SMTP connection error (test mode)"
    if recipient_email.lower() in TEST_SMTP_FAIL_EMAILS:
        return False, f"Simulated delivery failure for {mask_email(recipient_email)}"

    # 2. Mock mode (local development, demo environment, or tests without live SMTP)
    if config['is_mock']:
        # Simulate successful transmission
        msg_id = f"mock-msg-{int(datetime.now().timestamp())}"
        masked = mask_email(recipient_email)
        # Safe logging without exposing real email addresses or secrets
        print(f"[EMAIL-SERVICE] [DEMO_MOCK] Dispatched email to {masked}. Club: '{club_name or 'General'}'. Subject: '{subject}'")
        return True, None

    # 3. Live SMTP Transmission
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = config['default_sender']
        msg['To'] = f"{recipient_name} <{recipient_email}>" if recipient_name else recipient_email
        msg['X-ClubSphere-Club'] = club_name or 'General'

        # Plaintext and basic HTML content
        part_text = MIMEText(body_text, 'plain', 'utf-8')
        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; background-color: #f8fafc; padding: 24px;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
    <div style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); color: #ffffff; padding: 20px 24px;">
      <h2 style="margin: 0; font-size: 1.25rem; font-weight: 700;">ClubSphere &bull; {club_name or 'Campus Announcement'}</h2>
    </div>
    <div style="padding: 24px;">
      <h3 style="margin-top: 0; color: #0f172a; font-size: 1.15rem;">{subject}</h3>
      <div style="white-space: pre-wrap; color: #334155; font-size: 0.95rem;">{body_text}</div>
    </div>
    <div style="background: #f1f5f9; padding: 14px 24px; font-size: 0.78rem; color: #64748b; border-top: 1px solid #e2e8f0; text-align: center;">
      You received this because you are an active registered member of {club_name or 'ClubSphere'}.
    </div>
  </div>
</body>
</html>"""
        part_html = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(part_text)
        msg.attach(part_html)

        # Connect to SMTP server
        server = smtplib.SMTP(config['server'], config['port'], timeout=12)
        if config['use_tls']:
            server.starttls()
        if config['user'] and config['password']:
            server.login(config['user'], config['password'])

        server.send_message(msg)
        server.quit()
        return True, None
    except Exception as e:
        masked = mask_email(recipient_email)
        error_msg = f"SMTP error for recipient {masked}: {type(e).__name__}"
        return False, error_msg


def dispatch_club_announcement_email(db, club_id, announcement_id, title, content, publisher_id=None):
    """
    Retrieve eligible registered members of the selected club, deduplicate,
    validate emails and eligibility, and dispatch announcement emails individually.
    
    Returns a structured result dictionary:
    {
        'success': bool,
        'club_name': str,
        'eligible_count': int,
        'sent_count': int,
        'failed_count': int,
        'skipped_count': int,
        'skipped_details': list of dicts,
        'failures': list of str,
        'provider': 'SMTP' or 'DEMO_MOCK'
    }
    """
    # 1. Fetch club info
    club = db.execute("SELECT * FROM clubs WHERE id = ?", (club_id,)).fetchone()
    if not club:
        return {
            'success': False,
            'club_name': 'Unknown Club',
            'error': f'Club with ID {club_id} not found in database.',
            'eligible_count': 0,
            'sent_count': 0,
            'failed_count': 0,
            'skipped_count': 0,
            'skipped_details': [],
            'failures': [],
            'provider': 'NONE'
        }

    club_name = club['name']

    # 2. Query registered members for this specific club ONLY
    # Never retrieve members of unrelated clubs!
    query = """
        SELECT cm.id, cm.club_id, cm.member_id, cm.user_id,
               cm.full_name, cm.email, cm.status, cm.join_date,
               u.notification_preferences
        FROM club_members cm
        LEFT JOIN users u ON cm.user_id = u.id
        WHERE cm.club_id = ?
        ORDER BY cm.id ASC
    """
    rows = db.execute(query, (club_id,)).fetchall()

    # 3. Filter and deduplicate recipients
    email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    seen_emails = set()
    eligible_recipients = []
    skipped_details = []

    for r in rows:
        raw_email = (r['email'] or '').strip()
        full_name = (r['full_name'] or '').strip() or 'Club Member'
        status = r['status'] or 'Active'

        # Rule A: Check email presence & format
        if not raw_email or not email_regex.match(raw_email):
            skipped_details.append({
                'name': full_name,
                'email': raw_email,
                'reason': 'Missing or invalid email address'
            })
            continue

        email_norm = raw_email.lower()

        # Rule B: Recipient deduplication within this announcement
        if email_norm in seen_emails:
            skipped_details.append({
                'name': full_name,
                'email': email_norm,
                'reason': 'Duplicate recipient email'
            })
            continue

        # Rule C: Membership eligibility check (must be Active)
        if status != 'Active':
            skipped_details.append({
                'name': full_name,
                'email': email_norm,
                'reason': f"Membership status is '{status}' (must be Active)"
            })
            continue

        # Rule D: Notification preferences check if user has preferences set
        prefs_raw = r['notification_preferences']
        if prefs_raw:
            try:
                prefs = json.loads(prefs_raw)
                if prefs.get('email') is False or prefs.get('announcements') is False:
                    skipped_details.append({
                        'name': full_name,
                        'email': email_norm,
                        'reason': 'User opted out of email announcements in preferences'
                    })
                    continue
            except Exception:
                pass

        # Recipient is eligible and unique
        seen_emails.add(email_norm)
        eligible_recipients.append({
            'name': full_name,
            'email': email_norm
        })

    config = get_email_config()
    provider_name = 'DEMO_MOCK' if config['is_mock'] else 'SMTP'

    sent_count = 0
    failed_count = 0
    failures = []

    subject = f"[{club_name}] {title}"

    # 4. Dispatch individual emails
    for recipient in eligible_recipients:
        ok, err = send_single_email(
            recipient_email=recipient['email'],
            recipient_name=recipient['name'],
            subject=subject,
            body_text=content,
            config=config,
            club_name=club_name
        )
        if ok:
            sent_count += 1
        else:
            failed_count += 1
            failures.append(err or f"Delivery failed for {mask_email(recipient['email'])}")

    # 5. Determine overall success status
    # Success means all eligible recipients succeeded (or 0 eligible recipients)
    overall_success = (failed_count == 0)

    # 6. Update announcement record in database with delivery audit trail
    if announcement_id:
        status_text = 'Delivered' if overall_success and sent_count > 0 else (
            'Partial' if sent_count > 0 and failed_count > 0 else (
                'Failed' if failed_count > 0 else 'No Recipients'
            )
        )
        summary_text = (
            f"Club: {club_name} | Eligible: {len(eligible_recipients)} | "
            f"Sent: {sent_count} | Failed: {failed_count} | Skipped: {len(skipped_details)} | "
            f"Provider: {provider_name}"
        )
        try:
            db.execute("""
                UPDATE announcements
                SET email_sent_count = ?, email_status = ?, email_summary = ?
                WHERE id = ?
            """, (sent_count, status_text, summary_text, announcement_id))
            db.commit()
        except Exception:
            pass

    return {
        'success': overall_success,
        'club_name': club_name,
        'eligible_count': len(eligible_recipients),
        'sent_count': sent_count,
        'failed_count': failed_count,
        'skipped_count': len(skipped_details),
        'skipped_details': skipped_details,
        'failures': failures,
        'provider': provider_name
    }
