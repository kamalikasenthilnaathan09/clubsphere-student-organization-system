import { Request, Response } from 'express';
import { z } from 'zod';
import prisma from '../lib/prisma.js';
import { recordAuditLog } from '../middleware/audit.js';

const transactionSchema = z.object({
  type: z.enum(['INCOME', 'EXPENSE']),
  category: z.enum([
    'MEMBERSHIP_DUES',
    'EVENT_TICKETS',
    'MERCHANDISE',
    'FUNDRAISING',
    'OPERATING_EXPENSES',
    'EVENT_EXPENSES',
    'MERCH_COSTS',
    'VOLUNTEER_REIMBURSEMENT',
    'FEES',
    'REFUND',
  ]),
  amount: z.number().min(0.01),
  status: z.enum(['SETTLED', 'PENDING']).default('SETTLED'),
  description: z.string().min(3),
  reference: z.string().optional(),
  eventId: z.string().optional(),
  campaignId: z.string().optional(),
  transactionDate: z.string().optional(),
});

const budgetSchema = z.object({
  category: z.string(),
  allocatedAmount: z.number().min(0),
  fiscalYear: z.number().int().default(new Date().getFullYear()),
  period: z.enum(['ANNUAL', 'Q1', 'Q2', 'Q3', 'Q4']).default('ANNUAL'),
});

const reverseTransactionSchema = z.object({
  reason: z.string().min(5),
});

export async function listTransactions(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { type, category, status, startDate, endDate, search } = req.query;

  const whereClause: any = { organizationId: orgId };

  if (type && typeof type === 'string' && type !== 'ALL') {
    whereClause.type = type;
  }
  if (category && typeof category === 'string' && category !== 'ALL') {
    whereClause.category = category;
  }
  if (status && typeof status === 'string' && status !== 'ALL') {
    whereClause.status = status;
  }
  if (startDate && typeof startDate === 'string') {
    whereClause.transactionDate = { ...whereClause.transactionDate, gte: new Date(startDate) };
  }
  if (endDate && typeof endDate === 'string') {
    whereClause.transactionDate = { ...whereClause.transactionDate, lte: new Date(endDate) };
  }
  if (search && typeof search === 'string') {
    whereClause.OR = [
      { description: { contains: search } },
      { reference: { contains: search } },
    ];
  }

  const transactions = await prisma.financialTransaction.findMany({
    where: whereClause,
    include: {
      event: { select: { id: true, title: true } },
      campaign: { select: { id: true, title: true } },
      expenseClaim: { select: { id: true, title: true, claimant: { select: { fullName: true } } } },
    },
    orderBy: { transactionDate: 'desc' },
  });

  res.json(transactions);
}

export async function getFinancialSummary(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { startDate, endDate } = req.query;

  const whereClause: any = { organizationId: orgId };
  if (startDate && typeof startDate === 'string') {
    whereClause.transactionDate = { ...whereClause.transactionDate, gte: new Date(startDate) };
  }
  if (endDate && typeof endDate === 'string') {
    whereClause.transactionDate = { ...whereClause.transactionDate, lte: new Date(endDate) };
  }

  const allTransactions = await prisma.financialTransaction.findMany({
    where: whereClause,
  });

  // Calculate decimal-safe aggregates
  let totalSettledIncome = 0;
  let totalSettledExpense = 0;
  let pendingIncome = 0;
  let pendingExpense = 0;

  const categoryBreakdown: Record<string, { income: number; expense: number }> = {};

  for (const t of allTransactions) {
    if (!categoryBreakdown[t.category]) {
      categoryBreakdown[t.category] = { income: 0, expense: 0 };
    }

    if (t.status === 'SETTLED') {
      if (t.type === 'INCOME') {
        totalSettledIncome += t.amount;
        categoryBreakdown[t.category].income += t.amount;
      } else if (t.type === 'EXPENSE') {
        totalSettledExpense += t.amount;
        categoryBreakdown[t.category].expense += t.amount;
      }
    } else if (t.status === 'PENDING') {
      if (t.type === 'INCOME') pendingIncome += t.amount;
      else if (t.type === 'EXPENSE') pendingExpense += t.amount;
    }
  }

  totalSettledIncome = Number(totalSettledIncome.toFixed(2));
  totalSettledExpense = Number(totalSettledExpense.toFixed(2));
  const recordedNetBalance = Number((totalSettledIncome - totalSettledExpense).toFixed(2));

  // Count pending expense claims
  const pendingClaimsCount = await prisma.expenseClaim.count({
    where: { organizationId: orgId, status: 'PENDING' },
  });

  res.json({
    recordedBalance: recordedNetBalance,
    totalIncome: totalSettledIncome,
    totalExpenses: totalSettledExpense,
    pendingIncome: Number(pendingIncome.toFixed(2)),
    pendingExpense: Number(pendingExpense.toFixed(2)),
    pendingClaimsCount,
    categoryBreakdown,
    balanceFormula: 'Total Settled Income - Total Settled Expenses = Recorded Net Balance',
    labelNote: 'Internal application recorded ledger balance (not a verified bank balance)',
  });
}

export async function createTransaction(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const userId = req.user!.id;
  const data = transactionSchema.parse(req.body);

  const txRecord = await prisma.financialTransaction.create({
    data: {
      organizationId: orgId,
      type: data.type,
      category: data.category,
      amount: data.amount,
      currency: 'USD',
      status: data.status,
      description: data.description,
      reference: data.reference || `MAN-${Date.now().toString().slice(-6)}`,
      eventId: data.eventId || null,
      campaignId: data.campaignId || null,
      transactionDate: data.transactionDate ? new Date(data.transactionDate) : new Date(),
      createdByUserId: userId,
    },
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'FINANCIAL_TRANSACTION_CREATED',
      entityType: 'FinancialTransaction',
      entityId: txRecord.id,
      details: {
        type: txRecord.type,
        category: txRecord.category,
        amount: txRecord.amount,
        description: txRecord.description,
      },
    });
  }

  res.status(201).json(txRecord);
}

export async function reverseTransaction(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const userId = req.user!.id;
  const { id } = req.params;
  const data = reverseTransactionSchema.parse(req.body);

  const originalTx = await prisma.financialTransaction.findFirst({
    where: { id, organizationId: orgId },
  });

  if (!originalTx) {
    res.status(404).json({ error: 'Transaction not found' });
    return;
  }

  if (originalTx.status === 'REVERSED') {
    res.status(400).json({ error: 'This transaction has already been reversed' });
    return;
  }

  // CRITICAL RULE: Never silently delete finalized financial records. Create authorized reversal entry with audit trail.
  const result = await prisma.$transaction(async (tx) => {
    // 1. Mark original transaction as REVERSED
    const updatedOriginal = await tx.financialTransaction.update({
      where: { id },
      data: { status: 'REVERSED' },
    });

    // 2. Create offsetting transaction
    const opposingType = originalTx.type === 'INCOME' ? 'EXPENSE' : 'INCOME';
    const reversalTx = await tx.financialTransaction.create({
      data: {
        organizationId: orgId,
        type: opposingType,
        category: 'REFUND',
        amount: originalTx.amount,
        currency: originalTx.currency,
        status: 'SETTLED',
        description: `REVERSAL of ${originalTx.reference}: ${originalTx.description} (Reason: ${data.reason})`,
        reference: `REV-${originalTx.reference || originalTx.id.slice(0, 8)}`,
        eventId: originalTx.eventId,
        campaignId: originalTx.campaignId,
        createdByUserId: userId,
      },
    });

    return { updatedOriginal, reversalTx };
  });

  await recordAuditLog({
    organizationId: orgId,
    actorUserId: userId,
    action: 'FINANCIAL_TRANSACTION_REVERSED',
    entityType: 'FinancialTransaction',
    entityId: id,
    details: {
      originalId: id,
      reversalId: result.reversalTx.id,
      amount: originalTx.amount,
      reason: data.reason,
    },
  });

  res.json({
    success: true,
    message: 'Transaction reversed and balancing ledger correction recorded',
    originalTransaction: result.updatedOriginal,
    reversalTransaction: result.reversalTx,
  });
}

export async function listBudgets(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;

  const budgets = await prisma.budget.findMany({
    where: { organizationId: orgId },
    orderBy: { category: 'asc' },
  });

  // Calculate actual spending for each budget category
  const actualExpenses = await prisma.financialTransaction.findMany({
    where: {
      organizationId: orgId,
      type: 'EXPENSE',
      status: 'SETTLED',
    },
  });

  const enrichedBudgets = budgets.map((b) => {
    const actualSpent = actualExpenses
      .filter((t) => t.category === b.category)
      .reduce((acc, t) => acc + t.amount, 0);

    const remaining = Number((b.allocatedAmount - actualSpent).toFixed(2));
    const utilizationRate = b.allocatedAmount > 0 ? Number(((actualSpent / b.allocatedAmount) * 100).toFixed(1)) : 0;

    return {
      ...b,
      actualSpent: Number(actualSpent.toFixed(2)),
      remaining,
      utilizationRate,
      isOverBudget: actualSpent > b.allocatedAmount,
    };
  });

  res.json(enrichedBudgets);
}

export async function createOrUpdateBudget(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const data = budgetSchema.parse(req.body);

  const existing = await prisma.budget.findFirst({
    where: {
      organizationId: orgId,
      category: data.category,
      fiscalYear: data.fiscalYear,
      period: data.period,
    },
  });

  let budget;
  if (existing) {
    budget = await prisma.budget.update({
      where: { id: existing.id },
      data: { allocatedAmount: data.allocatedAmount },
    });
  } else {
    budget = await prisma.budget.create({
      data: {
        organizationId: orgId,
        category: data.category,
        allocatedAmount: data.allocatedAmount,
        fiscalYear: data.fiscalYear,
        period: data.period,
      },
    });
  }

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'BUDGET_ALLOCATION_UPDATED',
      entityType: 'Budget',
      entityId: budget.id,
      details: { category: budget.category, allocatedAmount: budget.allocatedAmount },
    });
  }

  res.status(201).json(budget);
}
