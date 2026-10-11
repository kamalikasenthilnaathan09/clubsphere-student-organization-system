import { describe, it, expect, beforeAll } from 'vitest';
import request from 'supertest';
import app from '../index.js';
import { seedDatabase } from '../lib/seed.js';

describe('CampusSphere AI - Critical Business Rules Integration Suite', () => {
  let presidentToken: string;
  let treasurerToken: string;
  let eventManagerToken: string;
  let volunteerToken: string;
  let memberToken: string;
  let studentToken: string;
  let orgId: string;

  beforeAll(async () => {
    // Re-seed clean database state before test run
    await seedDatabase();

    // Authenticate test accounts
    const presRes = await request(app)
      .post('/api/auth/login')
      .send({ email: 'president@skyline.edu', password: 'Skyline@123' });
    presidentToken = presRes.body.token;
    orgId = presRes.body.user.currentOrgId;

    const treasRes = await request(app)
      .post('/api/auth/login')
      .send({ email: 'treasurer@skyline.edu', password: 'Skyline@123' });
    treasurerToken = treasRes.body.token;

    const emRes = await request(app)
      .post('/api/auth/login')
      .send({ email: 'events@skyline.edu', password: 'Skyline@123' });
    eventManagerToken = emRes.body.token;

    const volRes = await request(app)
      .post('/api/auth/login')
      .send({ email: 'volunteer@skyline.edu', password: 'Skyline@123' });
    volunteerToken = volRes.body.token;

    const memRes = await request(app)
      .post('/api/auth/login')
      .send({ email: 'member@skyline.edu', password: 'Skyline@123' });
    memberToken = memRes.body.token;

    const stuRes = await request(app)
      .post('/api/auth/login')
      .send({ email: 'student@skyline.edu', password: 'Skyline@123' });
    studentToken = stuRes.body.token;
  });

  describe('1. Membership Rules & Validation', () => {
    it('Active member has verified status and discounts', async () => {
      const res = await request(app)
        .get('/api/members/verify?query=member@skyline.edu')
        .set('Authorization', `Bearer ${memberToken}`)
        .set('x-organization-id', orgId);

      expect(res.status).toBe(200);
      expect(res.body.isValid).toBe(true);
      expect(res.body.member.role).toBe('MEMBER');
      expect(res.body.member.tier).toBe('VIP_GOLD');
    });

    it('Pending student registration is NOT treated as an active paid member', async () => {
      const res = await request(app)
        .get('/api/members/verify?query=student@skyline.edu')
        .set('Authorization', `Bearer ${studentToken}`)
        .set('x-organization-id', orgId);

      expect(res.status).toBe(200);
      expect(res.body.isValid).toBe(false);
      expect(res.body.member.status).toBe('PENDING');
    });

    it('Regular member cannot promote themselves to CLUB_ADMIN or change their own role', async () => {
      const meRes = await request(app)
        .get('/api/auth/me')
        .set('Authorization', `Bearer ${memberToken}`)
        .set('x-organization-id', orgId);

      const membershipId = meRes.body.memberships[0].id;

      const res = await request(app)
        .patch(`/api/members/${membershipId}`)
        .set('Authorization', `Bearer ${memberToken}`)
        .set('x-organization-id', orgId)
        .send({ role: 'CLUB_ADMIN' });

      expect(res.status).toBe(403);
    });
  });

  describe('2. Event Ticketing, Capacity & Double Check-In Safeguards', () => {
    let eventId: string;
    let ticketTypeId: string;
    let validTicketCode: string;

    it('Discovers events and recognizes member pricing vs non-member pricing', async () => {
      const res = await request(app)
        .get('/api/events')
        .set('Authorization', `Bearer ${memberToken}`)
        .set('x-organization-id', orgId);

      expect(res.status).toBe(200);
      expect(res.body.length).toBeGreaterThan(0);
      const summit = res.body.find((e: any) => e.title.includes('Tech & AI Summit'));
      expect(summit).toBeDefined();
      eventId = summit.id;
      ticketTypeId = summit.ticketTypes[0].id;
    });

    it('Allows a student to book a ticket with automatic demo settlement', async () => {
      const bookRes = await request(app)
        .post(`/api/events/${eventId}/book`)
        .set('Authorization', `Bearer ${studentToken}`)
        .set('x-organization-id', orgId)
        .send({
          ticketTypeId,
          quantity: 1,
          attendeeName: 'Alex Rivera',
          attendeeEmail: 'student@skyline.edu',
        });

      expect(bookRes.status).toBe(201);
      expect(bookRes.body.success).toBe(true);
      expect(bookRes.body.tickets.length).toBe(1);
      validTicketCode = bookRes.body.tickets[0].ticketCode;
      expect(validTicketCode).toBeDefined();
      expect(bookRes.body.tickets[0].status).toBe('VALID');
      expect(bookRes.body.tickets[0].isCheckedIn).toBe(false);
    });

    it('Check-in manager successfully validates and checks in a valid ticket', async () => {
      const checkInRes = await request(app)
        .post(`/api/events/${eventId}/check-in`)
        .set('Authorization', `Bearer ${eventManagerToken}`)
        .set('x-organization-id', orgId)
        .send({
          ticketCode: validTicketCode,
          checkInMethod: 'QR_SCAN',
        });

      expect(checkInRes.status).toBe(200);
      expect(checkInRes.body.success).toBe(true);
      expect(checkInRes.body.validationStatus).toBe('SUCCESS');
      expect(checkInRes.body.ticket.isCheckedIn).toBe(true);
      expect(checkInRes.body.ticket.status).toBe('USED');
    });

    it('CRITICAL: A second attempt to check in the same ticket is REJECTED (ALREADY_USED)', async () => {
      const secondCheckIn = await request(app)
        .post(`/api/events/${eventId}/check-in`)
        .set('Authorization', `Bearer ${eventManagerToken}`)
        .set('x-organization-id', orgId)
        .send({
          ticketCode: validTicketCode,
          checkInMethod: 'QR_SCAN',
        });

      expect(secondCheckIn.status).toBe(409);
      expect(secondCheckIn.body.success).toBe(false);
      expect(secondCheckIn.body.validationStatus).toBe('ALREADY_USED');
    });
  });

  describe('3. Merchandise Inventory & Atomic Checkout', () => {
    let productId: string;
    let variantId: string;
    let initialStock: number;

    it('Browses merchandise and checks variant stock level', async () => {
      const res = await request(app)
        .get('/api/merchandise')
        .set('Authorization', `Bearer ${memberToken}`)
        .set('x-organization-id', orgId);

      expect(res.status).toBe(200);
      const hoodie = res.body.find((p: any) => p.name.includes('Hoodie'));
      expect(hoodie).toBeDefined();
      productId = hoodie.id;
      const variantS = hoodie.variants.find((v: any) => v.size === 'S');
      variantId = variantS.id;
      initialStock = variantS.stockQuantity;
      expect(initialStock).toBeGreaterThan(0);
    });

    it('Purchasing items deducts available stock atomically', async () => {
      const orderRes = await request(app)
        .post('/api/merchandise/checkout')
        .set('Authorization', `Bearer ${memberToken}`)
        .set('x-organization-id', orgId)
        .send({
          items: [{ productId, variantId, quantity: 2 }],
        });

      expect(orderRes.status).toBe(201);
      expect(orderRes.body.success).toBe(true);

      // Verify stock decreased in database
      const productsRes = await request(app)
        .get('/api/merchandise')
        .set('Authorization', `Bearer ${memberToken}`)
        .set('x-organization-id', orgId);

      const hoodie = productsRes.body.find((p: any) => p.id === productId);
      const variantS = hoodie.variants.find((v: any) => v.id === variantId);
      expect(variantS.stockQuantity).toBe(initialStock - 2);
    });

    it('Cannot oversell when requested quantity exceeds available stock', async () => {
      const oversellRes = await request(app)
        .post('/api/merchandise/checkout')
        .set('Authorization', `Bearer ${memberToken}`)
        .set('x-organization-id', orgId)
        .send({
          items: [{ productId, variantId, quantity: 15 }],
        });

      expect(oversellRes.status).toBe(400);
      expect(oversellRes.body.error).toContain('Insufficient stock');
    });
  });

  describe('4. Expense Approval & Separation of Duties', () => {
    let claimId: string;

    it('Volunteer submits an expense claim for supplies', async () => {
      const claimRes = await request(app)
        .post('/api/volunteers/expenses')
        .set('Authorization', `Bearer ${volunteerToken}`)
        .set('x-organization-id', orgId)
        .send({
          title: 'Extra marker pens and whiteboard wipes',
          description: 'Needed for workshop brainstorming breakout sessions',
          amount: 24.5,
          category: 'EVENT_SUPPLIES',
        });

      expect(claimRes.status).toBe(201);
      claimId = claimRes.body.id;
      expect(claimRes.body.status).toBe('PENDING');
    });

    it('CRITICAL: Volunteer CANNOT approve their own expense claim (Self-Approval Forbidden)', async () => {
      const selfApproveRes = await request(app)
        .post(`/api/volunteers/expenses/${claimId}/review`)
        .set('Authorization', `Bearer ${volunteerToken}`)
        .set('x-organization-id', orgId)
        .send({
          status: 'APPROVED',
          reviewNotes: 'Approving my own claim',
        });

      // Role check or self-approval check denies this
      expect(selfApproveRes.status).toBe(403);
    });

    it('Authorized Treasurer approves the expense, automatically creating ledger entry', async () => {
      const approveRes = await request(app)
        .post(`/api/volunteers/expenses/${claimId}/review`)
        .set('Authorization', `Bearer ${treasurerToken}`)
        .set('x-organization-id', orgId)
        .send({
          status: 'APPROVED',
          reviewNotes: 'Receipt verified and approved for reimbursement',
        });

      expect(approveRes.status).toBe(200);
      expect(approveRes.body.success).toBe(true);
      expect(approveRes.body.claim.status).toBe('APPROVED');
      expect(approveRes.body.transaction).toBeDefined();
      expect(approveRes.body.transaction.amount).toBe(24.5);
      expect(approveRes.body.transaction.type).toBe('EXPENSE');
    });
  });

  describe('5. Financial Ledger & Decimal-Safe Balance Calculations', () => {
    it('Financial summary calculates total income, expenses, and recorded balance accurately', async () => {
      const summaryRes = await request(app)
        .get('/api/finance/summary')
        .set('Authorization', `Bearer ${treasurerToken}`)
        .set('x-organization-id', orgId);

      expect(summaryRes.status).toBe(200);
      const { totalIncome, totalExpenses, recordedBalance } = summaryRes.body;
      expect(totalIncome).toBeGreaterThan(0);
      expect(totalExpenses).toBeGreaterThan(0);
      expect(recordedBalance).toBe(Number((totalIncome - totalExpenses).toFixed(2)));
    });

    it('Supports reversing transactions with full audit trail instead of silent deletion', async () => {
      const txsRes = await request(app)
        .get('/api/finance/transactions')
        .set('Authorization', `Bearer ${treasurerToken}`)
        .set('x-organization-id', orgId);

      const targetTx = txsRes.body.find((t: any) => t.status === 'SETTLED' && t.type === 'EXPENSE');
      expect(targetTx).toBeDefined();

      const reverseRes = await request(app)
        .post(`/api/finance/transactions/${targetTx.id}/reverse`)
        .set('Authorization', `Bearer ${treasurerToken}`)
        .set('x-organization-id', orgId)
        .send({ reason: 'Accidental duplicate voucher entry' });

      expect(reverseRes.status).toBe(200);
      expect(reverseRes.body.success).toBe(true);
      expect(reverseRes.body.originalTransaction.status).toBe('REVERSED');
      expect(reverseRes.body.reversalTransaction.status).toBe('SETTLED');
    });
  });

  describe('6. AI Club Copilot Context Filtering & Fallback Degradation', () => {
    it('Copilot produces fact-based answers using authorized organization data', async () => {
      const aiRes = await request(app)
        .post('/api/ai/query')
        .set('Authorization', `Bearer ${presidentToken}`)
        .set('x-organization-id', orgId)
        .send({
          prompt: 'Summarize this month club performance and activity',
          intent: 'performance_summary',
        });

      expect(aiRes.status).toBe(200);
      expect(aiRes.body.answer).toContain('Skyline Student Association');
      expect(aiRes.body.contextSummary.activeMembersCount).toBeGreaterThan(0);
      expect(aiRes.body.contextSummary.recordedBalance).toBeDefined();
    });

    it('Copilot gracefully handles questions without inventing data', async () => {
      const aiRes = await request(app)
        .post('/api/ai/query')
        .set('Authorization', `Bearer ${presidentToken}`)
        .set('x-organization-id', orgId)
        .send({
          prompt: 'Which volunteer tasks are currently open or overdue?',
          intent: 'task_summary',
        });

      expect(aiRes.status).toBe(200);
      expect(aiRes.body.answer).toContain('Volunteer Workload');
    });
  });
});
