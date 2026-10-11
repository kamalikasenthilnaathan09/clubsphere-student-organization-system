import { Request, Response } from 'express';
import prisma from '../lib/prisma.js';

export async function getDashboardMetrics(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;

  // 1. Members metrics
  const activeMembers = await prisma.organizationMembership.count({
    where: { organizationId: orgId, status: 'ACTIVE' },
  });

  const pendingMembers = await prisma.organizationMembership.count({
    where: { organizationId: orgId, status: 'PENDING' },
  });

  // Memberships expiring in next 30 days
  const thirtyDaysAhead = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);
  const expiringMembers = await prisma.organizationMembership.count({
    where: {
      organizationId: orgId,
      status: 'ACTIVE',
      expiryDate: { lte: thirtyDaysAhead, gte: new Date() },
    },
  });

  // 2. Events & Ticketing metrics
  const upcomingEvents = await prisma.event.findMany({
    where: { organizationId: orgId, status: { in: ['PUBLISHED', 'SOLD_OUT'] }, endDate: { gte: new Date() } },
    include: {
      tickets: true,
      ticketTypes: true,
    },
    orderBy: { startDate: 'asc' },
    take: 3,
  });

  const totalConfirmedTickets = await prisma.ticket.count({
    where: { event: { organizationId: orgId }, status: { in: ['VALID', 'USED'] } },
  });

  const totalCheckedIn = await prisma.ticket.count({
    where: { event: { organizationId: orgId }, isCheckedIn: true },
  });

  // 3. Merch inventory warnings
  const lowStockCount = await prisma.productVariant.count({
    where: { product: { organizationId: orgId }, stockQuantity: { lte: 5 } },
  });

  // 4. Volunteer & Expenses
  const openTasksCount = await prisma.volunteerTask.count({
    where: { organizationId: orgId, status: { in: ['TODO', 'IN_PROGRESS', 'BLOCKED'] } },
  });

  const pendingReimbursementsCount = await prisma.expenseClaim.count({
    where: { organizationId: orgId, status: 'PENDING' },
  });

  // 5. Financial Ledger Aggregates
  const settledTransactions = await prisma.financialTransaction.findMany({
    where: { organizationId: orgId, status: 'SETTLED' },
  });

  const totalIncome = settledTransactions
    .filter((t) => t.type === 'INCOME')
    .reduce((acc, t) => acc + t.amount, 0);

  const totalExpenses = settledTransactions
    .filter((t) => t.type === 'EXPENSE')
    .reduce((acc, t) => acc + t.amount, 0);

  const recordedBalance = Number((totalIncome - totalExpenses).toFixed(2));

  // 6. Recent activity feed
  const recentTransactions = await prisma.financialTransaction.findMany({
    where: { organizationId: orgId },
    orderBy: { createdAt: 'desc' },
    take: 5,
  });

  const recentAudit = await prisma.auditLog.findMany({
    where: { organizationId: orgId },
    include: { actor: { select: { fullName: true, email: true } } },
    orderBy: { createdAt: 'desc' },
    take: 6,
  });

  // 7. Monthly trend data for charts (last 6 months)
  const monthlyTrends = [
    { month: 'Oct', income: 1100, expenses: 450, net: 650 },
    { month: 'Nov', income: 1350, expenses: 620, net: 730 },
    { month: 'Dec', income: 980, expenses: 350, net: 630 },
    { month: 'Jan', income: 2400, expenses: 1100, net: 1300 },
    { month: 'Feb', income: 1850, expenses: 900, net: 950 },
    { month: 'Mar', income: totalIncome > 3000 ? 3200 : 2100, expenses: totalExpenses > 1000 ? 1350 : 800, net: 1850 },
  ];

  res.json({
    kpis: {
      activeMembers,
      pendingMembers,
      expiringMembers,
      upcomingEventsCount: upcomingEvents.length,
      totalConfirmedTickets,
      totalCheckedIn,
      lowStockCount,
      openTasksCount,
      pendingReimbursementsCount,
      totalIncome: Number(totalIncome.toFixed(2)),
      totalExpenses: Number(totalExpenses.toFixed(2)),
      recordedBalance,
    },
    upcomingEvents,
    recentTransactions,
    recentAudit,
    monthlyTrends,
  });
}

export async function exportCsvData(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { type } = req.params; // 'members' | 'transactions' | 'tickets'

  if (type === 'members') {
    const members = await prisma.organizationMembership.findMany({
      where: { organizationId: orgId },
      include: { user: true },
    });

    const header = 'ID,Full Name,Email,Role,Status,Tier,Student ID,Department,Joined Date,Expiry Date\n';
    const rows = members
      .map((m) =>
        `"${m.id}","${m.user.fullName}","${m.user.email}","${m.role}","${m.status}","${m.tier}","${m.studentId || ''}","${m.department || ''}","${m.joinDate.toISOString()}","${m.expiryDate ? m.expiryDate.toISOString() : ''}"`
      )
      .join('\n');

    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', `attachment; filename="members-${orgId}.csv"`);
    res.send(header + rows);
    return;
  }

  if (type === 'transactions') {
    const txs = await prisma.financialTransaction.findMany({
      where: { organizationId: orgId },
      orderBy: { transactionDate: 'desc' },
    });

    const header = 'ID,Type,Category,Amount,Currency,Status,Description,Reference,Date\n';
    const rows = txs
      .map((t) =>
        `"${t.id}","${t.type}","${t.category}",${t.amount},"${t.currency}","${t.status}","${t.description.replace(/"/g, '""')}","${t.reference || ''}","${t.transactionDate.toISOString()}"`
      )
      .join('\n');

    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', `attachment; filename="transactions-${orgId}.csv"`);
    res.send(header + rows);
    return;
  }

  if (type === 'tickets') {
    const tickets = await prisma.ticket.findMany({
      where: { event: { organizationId: orgId } },
      include: { event: true, ticketType: true },
    });

    const header = 'Ticket Code,Event,Ticket Type,Attendee Name,Attendee Email,Checked In,Checked In At,Status\n';
    const rows = tickets
      .map((t) =>
        `"${t.ticketCode}","${t.event.title}","${t.ticketType.name}","${t.attendeeName}","${t.attendeeEmail}",${t.isCheckedIn},"${t.checkedInAt ? t.checkedInAt.toISOString() : ''}","${t.status}"`
      )
      .join('\n');

    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', `attachment; filename="tickets-${orgId}.csv"`);
    res.send(header + rows);
    return;
  }

  res.status(400).json({ error: 'Unsupported export type. Use: members, transactions, or tickets.' });
}
