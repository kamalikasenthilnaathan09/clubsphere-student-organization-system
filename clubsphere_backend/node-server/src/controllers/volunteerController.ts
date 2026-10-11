import { Request, Response } from 'express';
import { z } from 'zod';
import prisma from '../lib/prisma.js';
import { recordAuditLog } from '../middleware/audit.js';

const taskCreateSchema = z.object({
  title: z.string().min(3),
  description: z.string().min(5),
  priority: z.enum(['LOW', 'MEDIUM', 'HIGH', 'URGENT']).default('MEDIUM'),
  dueDate: z.string().optional(),
  assignedUserIds: z.array(z.string()).default([]),
});

const taskUpdateSchema = z.object({
  title: z.string().min(3).optional(),
  description: z.string().min(5).optional(),
  priority: z.enum(['LOW', 'MEDIUM', 'HIGH', 'URGENT']).optional(),
  status: z.enum(['TODO', 'IN_PROGRESS', 'BLOCKED', 'COMPLETED']).optional(),
  dueDate: z.string().optional(),
  assignedUserIds: z.array(z.string()).optional(),
});

const campaignCreateSchema = z.object({
  title: z.string().min(3),
  description: z.string().min(5),
  goalAmount: z.number().min(1),
  startDate: z.string(),
  endDate: z.string(),
});

const donationSchema = z.object({
  amount: z.number().min(1),
  donorName: z.string().min(2),
  donorEmail: z.string().email().optional(),
  note: z.string().optional(),
});

const expenseClaimSchema = z.object({
  title: z.string().min(3),
  description: z.string().min(5),
  amount: z.number().min(0.01),
  category: z.enum(['EVENT_SUPPLIES', 'TRAVEL', 'REFRESHMENTS', 'MARKETING', 'PRINTING', 'OTHER']),
  receiptUrl: z.string().optional(),
});

const reviewClaimSchema = z.object({
  status: z.enum(['APPROVED', 'REJECTED']),
  reviewNotes: z.string().min(2),
});

export async function listTasks(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { status, priority, myTasksOnly } = req.query;

  const whereClause: any = { organizationId: orgId };

  if (status && typeof status === 'string' && status !== 'ALL') {
    whereClause.status = status;
  }
  if (priority && typeof priority === 'string' && priority !== 'ALL') {
    whereClause.priority = priority;
  }
  if (myTasksOnly === 'true' && req.user) {
    whereClause.assignments = {
      some: { userId: req.user.id },
    };
  }

  const tasks = await prisma.volunteerTask.findMany({
    where: whereClause,
    include: {
      assignments: {
        include: {
          user: {
            select: { id: true, fullName: true, email: true, avatarUrl: true },
          },
        },
      },
    },
    orderBy: { createdAt: 'desc' },
  });

  res.json(tasks);
}

export async function createTask(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const userId = req.user!.id;
  const data = taskCreateSchema.parse(req.body);

  const task = await prisma.volunteerTask.create({
    data: {
      organizationId: orgId,
      title: data.title,
      description: data.description,
      priority: data.priority,
      status: 'TODO',
      dueDate: data.dueDate ? new Date(data.dueDate) : null,
      createdByUserId: userId,
      assignments: {
        create: data.assignedUserIds.map((uid) => ({ userId: uid })),
      },
    },
    include: {
      assignments: { include: { user: true } },
    },
  });

  // Notify assigned users
  for (const uid of data.assignedUserIds) {
    await prisma.notification.create({
      data: {
        userId: uid,
        title: 'New Volunteer Task Assigned',
        message: `You were assigned: ${task.title} (Priority: ${task.priority})`,
        type: 'INFO',
        linkUrl: '/tasks',
      },
    });
  }

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'VOLUNTEER_TASK_CREATED',
      entityType: 'VolunteerTask',
      entityId: task.id,
      details: { title: task.title, assignedCount: data.assignedUserIds.length },
    });
  }

  res.status(201).json(task);
}

export async function updateTask(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { id } = req.params;
  const data = taskUpdateSchema.parse(req.body);

  const existing = await prisma.volunteerTask.findFirst({
    where: { id, organizationId: orgId },
  });

  if (!existing) {
    res.status(404).json({ error: 'Task not found' });
    return;
  }

  const updateData: any = {};
  if (data.title) updateData.title = data.title;
  if (data.description) updateData.description = data.description;
  if (data.priority) updateData.priority = data.priority;
  if (data.status) updateData.status = data.status;
  if (data.dueDate !== undefined) updateData.dueDate = data.dueDate ? new Date(data.dueDate) : null;

  const updated = await prisma.$transaction(async (tx) => {
    if (data.assignedUserIds) {
      await tx.taskAssignment.deleteMany({ where: { taskId: id } });
      await tx.taskAssignment.createMany({
        data: data.assignedUserIds.map((uid) => ({ taskId: id, userId: uid })),
      });
    }

    return await tx.volunteerTask.update({
      where: { id },
      data: updateData,
      include: {
        assignments: { include: { user: true } },
      },
    });
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'VOLUNTEER_TASK_UPDATED',
      entityType: 'VolunteerTask',
      entityId: id,
      details: { changes: data },
    });
  }

  res.json(updated);
}

export async function getVolunteerWorkload(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;

  const volunteers = await prisma.organizationMembership.findMany({
    where: {
      organizationId: orgId,
      role: { in: ['VOLUNTEER', 'EVENT_MANAGER', 'CLUB_ADMIN'] },
    },
    include: {
      user: {
        select: {
          id: true,
          fullName: true,
          email: true,
          avatarUrl: true,
          assignedTasks: {
            include: { task: true },
          },
        },
      },
    },
  });

  const workload = volunteers.map((v) => {
    const tasks = v.user.assignedTasks.map((at) => at.task).filter((t) => t.organizationId === orgId);
    const todoCount = tasks.filter((t) => t.status === 'TODO').length;
    const inProgressCount = tasks.filter((t) => t.status === 'IN_PROGRESS').length;
    const completedCount = tasks.filter((t) => t.status === 'COMPLETED').length;
    const blockedCount = tasks.filter((t) => t.status === 'BLOCKED').length;

    return {
      userId: v.user.id,
      fullName: v.user.fullName,
      email: v.user.email,
      role: v.role,
      tier: v.tier,
      totalAssigned: tasks.length,
      todoCount,
      inProgressCount,
      completedCount,
      blockedCount,
    };
  });

  res.json(workload);
}

export async function listCampaigns(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;

  const campaigns = await prisma.fundraisingCampaign.findMany({
    where: { organizationId: orgId },
    include: {
      financialTransactions: {
        where: { status: 'SETTLED' },
      },
    },
    orderBy: { createdAt: 'desc' },
  });

  // Calculate actual progress based on recorded settled financial transactions
  const enriched = campaigns.map((c) => {
    const recordedTotal = c.financialTransactions.reduce((acc, t) => acc + t.amount, 0);
    const currentAmount = Math.max(c.currentAmount, recordedTotal);
    const progressPercent = Math.min(100, Number(((currentAmount / c.goalAmount) * 100).toFixed(1)));
    return {
      ...c,
      currentAmount,
      progressPercent,
    };
  });

  res.json(enriched);
}

export async function createCampaign(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const coordinatorId = req.user!.id;
  const data = campaignCreateSchema.parse(req.body);

  const campaign = await prisma.fundraisingCampaign.create({
    data: {
      organizationId: orgId,
      coordinatorId,
      title: data.title,
      description: data.description,
      goalAmount: data.goalAmount,
      currentAmount: 0,
      startDate: new Date(data.startDate),
      endDate: new Date(data.endDate),
      status: 'ACTIVE',
    },
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'FUNDRAISING_CAMPAIGN_CREATED',
      entityType: 'FundraisingCampaign',
      entityId: campaign.id,
      details: { title: campaign.title, goal: campaign.goalAmount },
    });
  }

  res.status(201).json(campaign);
}

export async function recordDonation(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { id: campaignId } = req.params;
  const data = donationSchema.parse(req.body);

  const campaign = await prisma.fundraisingCampaign.findFirst({
    where: { id: campaignId, organizationId: orgId },
  });

  if (!campaign) {
    res.status(404).json({ error: 'Fundraising campaign not found' });
    return;
  }

  // Atomically update campaign amount & record financial ledger transaction
  const result = await prisma.$transaction(async (tx) => {
    const updatedCampaign = await tx.fundraisingCampaign.update({
      where: { id: campaignId },
      data: { currentAmount: { increment: data.amount } },
    });

    const txRef = `DON-${Date.now().toString().slice(-6)}-${Math.floor(Math.random() * 900 + 100)}`;

    const finTx = await tx.financialTransaction.create({
      data: {
        organizationId: orgId,
        type: 'INCOME',
        category: 'FUNDRAISING',
        amount: data.amount,
        currency: 'USD',
        status: 'SETTLED',
        description: `Fundraiser donation: ${campaign.title} (Donor: ${data.donorName}${data.note ? ` - "${data.note}"` : ''})`,
        reference: txRef,
        campaignId,
        createdByUserId: req.user?.id || campaign.coordinatorId,
      },
    });

    return { updatedCampaign, finTx };
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'DONATION_RECORDED',
      entityType: 'FundraisingCampaign',
      entityId: campaignId,
      details: { amount: data.amount, donor: data.donorName },
    });
  }

  res.status(201).json({
    success: true,
    message: `Donation of $${data.amount} successfully recorded and added to financial ledger`,
    campaign: result.updatedCampaign,
    transaction: result.finTx,
  });
}

export async function submitExpenseClaim(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const claimantId = req.user!.id;
  const data = expenseClaimSchema.parse(req.body);

  const claim = await prisma.expenseClaim.create({
    data: {
      organizationId: orgId,
      claimantId,
      title: data.title,
      description: data.description,
      amount: data.amount,
      category: data.category,
      receiptUrl: data.receiptUrl || null,
      status: 'PENDING',
    },
    include: { claimant: { select: { fullName: true, email: true } } },
  });

  // Notify treasurers
  const treasurers = await prisma.organizationMembership.findMany({
    where: { organizationId: orgId, role: { in: ['TREASURER', 'CLUB_ADMIN'] } },
    select: { userId: true },
  });

  for (const t of treasurers) {
    await prisma.notification.create({
      data: {
        userId: t.userId,
        title: 'New Reimbursement Claim',
        message: `${req.user!.fullName} requested $${data.amount} for "${data.title}". Review needed.`,
        type: 'WARNING',
        linkUrl: '/finance',
      },
    });
  }

  await recordAuditLog({
    organizationId: orgId,
    actorUserId: claimantId,
    action: 'EXPENSE_CLAIM_SUBMITTED',
    entityType: 'ExpenseClaim',
    entityId: claim.id,
    details: { title: claim.title, amount: claim.amount },
  });

  res.status(201).json(claim);
}

export async function reviewExpenseClaim(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const reviewerId = req.user!.id;
  const { id } = req.params;
  const data = reviewClaimSchema.parse(req.body);

  const claim = await prisma.expenseClaim.findFirst({
    where: { id, organizationId: orgId },
    include: { claimant: true },
  });

  if (!claim) {
    res.status(404).json({ error: 'Expense claim not found' });
    return;
  }

  // CRITICAL RULE: Prevent user from approving their own expense claim
  if (claim.claimantId === reviewerId) {
    res.status(403).json({
      error: 'Security restriction: Separation of duties requires that you cannot approve your own expense claim.',
    });
    return;
  }

  if (claim.status !== 'PENDING') {
    res.status(400).json({ error: `Expense claim has already been resolved with status "${claim.status}"` });
    return;
  }

  // Atomically update claim & if approved, insert into financial ledger exactly once
  const result = await prisma.$transaction(async (tx) => {
    const updatedClaim = await tx.expenseClaim.update({
      where: { id },
      data: {
        status: data.status,
        reviewedByUserId: reviewerId,
        reviewedAt: new Date(),
        reviewNotes: data.reviewNotes,
      },
    });

    let finTx = null;
    if (data.status === 'APPROVED') {
      const ref = `REIMB-${Date.now().toString().slice(-6)}-${Math.floor(Math.random() * 900 + 100)}`;
      finTx = await tx.financialTransaction.create({
        data: {
          organizationId: orgId,
          type: 'EXPENSE',
          category: 'VOLUNTEER_REIMBURSEMENT',
          amount: claim.amount,
          currency: 'USD',
          status: 'SETTLED',
          description: `Volunteer reimbursement: ${claim.title} (${claim.claimant.fullName})`,
          reference: ref,
          expenseClaimId: claim.id,
          createdByUserId: reviewerId,
        },
      });
    }

    return { updatedClaim, finTx };
  });

  // Notify claimant
  await prisma.notification.create({
    data: {
      userId: claim.claimantId,
      title: `Reimbursement Claim ${data.status === 'APPROVED' ? 'Approved ✅' : 'Rejected ❌'}`,
      message: `Your claim for $${claim.amount} was ${data.status.toLowerCase()}. Note: "${data.reviewNotes}"`,
      type: data.status === 'APPROVED' ? 'SUCCESS' : 'ALERT',
      linkUrl: '/finance',
    },
  });

  await recordAuditLog({
    organizationId: orgId,
    actorUserId: reviewerId,
    action: data.status === 'APPROVED' ? 'EXPENSE_APPROVED' : 'EXPENSE_REJECTED',
    entityType: 'ExpenseClaim',
    entityId: claim.id,
    details: {
      claimant: claim.claimant.fullName,
      amount: claim.amount,
      notes: data.reviewNotes,
    },
  });

  res.json({
    success: true,
    message: `Expense claim has been ${data.status.toLowerCase()}`,
    claim: result.updatedClaim,
    transaction: result.finTx,
  });
}

export async function listExpenseClaims(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { status, myClaimsOnly } = req.query;

  const whereClause: any = { organizationId: orgId };

  if (status && typeof status === 'string' && status !== 'ALL') {
    whereClause.status = status;
  }
  if (myClaimsOnly === 'true' && req.user) {
    whereClause.claimantId = req.user.id;
  }

  const claims = await prisma.expenseClaim.findMany({
    where: whereClause,
    include: {
      claimant: { select: { id: true, fullName: true, email: true } },
      reviewer: { select: { id: true, fullName: true } },
      financialTransaction: true,
    },
    orderBy: { createdAt: 'desc' },
  });

  res.json(claims);
}
