import { Request, Response } from 'express';
import { z } from 'zod';
import prisma from '../lib/prisma.js';
import { recordAuditLog } from '../middleware/audit.js';
import { sendNotificationEmail } from '../services/emailService.js';

const memberUpdateSchema = z.object({
  role: z.enum(['SUPER_ADMIN', 'CLUB_ADMIN', 'TREASURER', 'EVENT_MANAGER', 'VOLUNTEER', 'MEMBER']).optional(),
  status: z.enum(['ACTIVE', 'PENDING', 'EXPIRED', 'ARCHIVED']).optional(),
  tier: z.string().optional(),
  department: z.string().optional(),
  studentId: z.string().optional(),
  expiryDate: z.string().optional(),
});

const planSchema = z.object({
  name: z.string().min(2),
  description: z.string().optional(),
  price: z.number().min(0),
  durationMonths: z.number().int().min(1).default(12),
  benefits: z.array(z.string()).default([]),
  discountPercentage: z.number().min(0).max(100).default(0),
});

const subscribeSchema = z.object({
  planId: z.string(),
  paymentMethod: z.enum(['DEMO_CARD', 'CASH', 'BANK_TRANSFER']).default('DEMO_CARD'),
});

export async function listMembers(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { search, status, role, tier } = req.query;

  const whereClause: any = { organizationId: orgId };

  if (status && typeof status === 'string' && status !== 'ALL') {
    whereClause.status = status;
  }
  if (role && typeof role === 'string' && role !== 'ALL') {
    whereClause.role = role;
  }
  if (tier && typeof tier === 'string' && tier !== 'ALL') {
    whereClause.tier = tier;
  }
  if (search && typeof search === 'string') {
    whereClause.OR = [
      { user: { fullName: { contains: search } } },
      { user: { email: { contains: search } } },
      { studentId: { contains: search } },
      { department: { contains: search } },
    ];
  }

  const members = await prisma.organizationMembership.findMany({
    where: whereClause,
    include: {
      user: {
        select: {
          id: true,
          fullName: true,
          email: true,
          phone: true,
          avatarUrl: true,
        },
      },
      subscriptions: {
        orderBy: { createdAt: 'desc' },
        take: 1,
        include: {
          plan: true,
          payments: {
            orderBy: { paidAt: 'desc' },
            take: 1,
          },
        },
      },
    },
    orderBy: { createdAt: 'desc' },
  });

  res.json(members);
}

export async function updateMember(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { id } = req.params;
  const data = memberUpdateSchema.parse(req.body);

  const existing = await prisma.organizationMembership.findFirst({
    where: { id, organizationId: orgId },
  });

  if (!existing) {
    res.status(404).json({ error: 'Member record not found' });
    return;
  }

  // Prevent users from granting themselves higher privileges
  if (req.user && req.user.id === existing.userId && data.role && data.role !== existing.role) {
    res.status(403).json({ error: 'Security restriction: You cannot modify your own administrative role' });
    return;
  }

  const updateData: any = { ...data };
  if (data.expiryDate) {
    updateData.expiryDate = new Date(data.expiryDate);
  }

  const updated = await prisma.organizationMembership.update({
    where: { id },
    data: updateData,
    include: { user: true },
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'MEMBER_RECORD_UPDATED',
      entityType: 'OrganizationMembership',
      entityId: id,
      details: { memberEmail: updated.user.email, changedFields: data },
    });
  }

  res.json(updated);
}

export async function verifyMemberStatus(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { query } = req.query; // email or studentId

  if (!query || typeof query !== 'string') {
    res.status(400).json({ error: 'Search query required' });
    return;
  }

  const membership = await prisma.organizationMembership.findFirst({
    where: {
      organizationId: orgId,
      OR: [
        { user: { email: query } },
        { studentId: query },
        { id: query },
      ],
    },
    include: {
      user: { select: { fullName: true, email: true, phone: true } },
      subscriptions: {
        where: { status: 'ACTIVE' },
        include: { plan: true },
      },
    },
  });

  if (!membership) {
    res.status(404).json({ isValid: false, message: 'No registered membership found for this identifier' });
    return;
  }

  const isExpired = membership.expiryDate ? new Date(membership.expiryDate) < new Date() : false;
  const isPaidActive = membership.status === 'ACTIVE' && !isExpired;

  res.json({
    isValid: isPaidActive,
    member: {
      id: membership.id,
      name: membership.user.fullName,
      email: membership.user.email,
      studentId: membership.studentId,
      role: membership.role,
      tier: membership.tier,
      status: isExpired ? 'EXPIRED' : membership.status,
      expiryDate: membership.expiryDate,
      activePlan: membership.subscriptions[0]?.plan?.name || 'None',
      discountPercentage: membership.subscriptions[0]?.plan?.discountPercentage || 0,
    },
  });
}

export async function sendRenewalReminder(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { id } = req.params;

  const membership = await prisma.organizationMembership.findFirst({
    where: { id, organizationId: orgId },
    include: { user: true, organization: true },
  });

  if (!membership) {
    res.status(404).json({ error: 'Member not found' });
    return;
  }

  const emailResult = await sendNotificationEmail({
    to: membership.user.email,
    subject: `Notice: Membership Renewal for ${membership.organization.name}`,
    body: `Hello ${membership.user.fullName},\n\nThis is a friendly reminder that your membership tier (${membership.tier}) with ${membership.organization.name} is approaching expiry. Please log in to your portal to renew your dues and keep your member perks.`,
  });

  await prisma.notification.create({
    data: {
      userId: membership.userId,
      title: 'Membership Renewal Reminder',
      message: `Your membership dues renewal is pending. Please renew to retain event discounts and perks.`,
      type: 'WARNING',
      linkUrl: '/members',
    },
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'RENEWAL_REMINDER_SENT',
      entityType: 'OrganizationMembership',
      entityId: id,
      details: { memberEmail: membership.user.email, messageId: emailResult.messageId },
    });
  }

  res.json({
    success: true,
    message: `Renewal reminder dispatched to ${membership.user.email}`,
    delivery: emailResult,
  });
}

export async function importMembersCsv(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const { members } = req.body; // array of { fullName, email, studentId, department, role, tier }

  if (!Array.isArray(members) || members.length === 0) {
    res.status(400).json({ error: 'Valid members array required in payload' });
    return;
  }

  let createdCount = 0;
  let skippedCount = 0;

  for (const m of members) {
    if (!m.email || !m.fullName) {
      skippedCount++;
      continue;
    }

    let user = await prisma.user.findUnique({ where: { email: m.email } });
    if (!user) {
      user = await prisma.user.create({
        data: {
          email: m.email,
          fullName: m.fullName,
          passwordHash: '$2a$10$wT5a083Vd...', // placeholder hash
        },
      });
    }

    const existingMembership = await prisma.organizationMembership.findFirst({
      where: { userId: user.id, organizationId: orgId },
    });

    if (!existingMembership) {
      await prisma.organizationMembership.create({
        data: {
          userId: user.id,
          organizationId: orgId,
          role: m.role || 'MEMBER',
          status: 'ACTIVE',
          tier: m.tier || 'STANDARD',
          studentId: m.studentId || null,
          department: m.department || null,
          expiryDate: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000),
        },
      });
      createdCount++;
    } else {
      skippedCount++;
    }
  }

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'MEMBERS_CSV_IMPORTED',
      entityType: 'OrganizationMembership',
      entityId: orgId,
      details: { createdCount, skippedCount },
    });
  }

  res.json({ success: true, createdCount, skippedCount });
}

export async function listMembershipPlans(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const plans = await prisma.membershipPlan.findMany({
    where: { organizationId: orgId, isActive: true },
    include: {
      _count: { select: { subscriptions: true } },
    },
  });

  const parsedPlans = plans.map((p) => ({
    ...p,
    benefitsList: (() => {
      try {
        return JSON.parse(p.benefits);
      } catch {
        return [];
      }
    })(),
  }));

  res.json(parsedPlans);
}

export async function createMembershipPlan(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const data = planSchema.parse(req.body);

  const plan = await prisma.membershipPlan.create({
    data: {
      organizationId: orgId,
      name: data.name,
      description: data.description || null,
      price: data.price,
      durationMonths: data.durationMonths,
      benefits: JSON.stringify(data.benefits),
      discountPercentage: data.discountPercentage,
      isActive: true,
    },
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'MEMBERSHIP_PLAN_CREATED',
      entityType: 'MembershipPlan',
      entityId: plan.id,
      details: { name: plan.name, price: plan.price },
    });
  }

  res.status(201).json(plan);
}

export async function subscribeMembership(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const userId = req.user!.id;
  const data = subscribeSchema.parse(req.body);

  const plan = await prisma.membershipPlan.findFirst({
    where: { id: data.planId, organizationId: orgId, isActive: true },
  });

  if (!plan) {
    res.status(404).json({ error: 'Membership plan not found or inactive' });
    return;
  }

  let membership = await prisma.organizationMembership.findFirst({
    where: { userId, organizationId: orgId },
  });

  if (!membership) {
    membership = await prisma.organizationMembership.create({
      data: {
        userId,
        organizationId: orgId,
        role: 'MEMBER',
        status: 'PENDING',
      },
    });
  }

  const startDate = new Date();
  const endDate = new Date(startDate.getTime() + plan.durationMonths * 30 * 24 * 60 * 60 * 1000);

  // Atomic database transaction
  const result = await prisma.$transaction(async (tx) => {
    const sub = await tx.memberSubscription.create({
      data: {
        membershipId: membership.id,
        planId: plan.id,
        startDate,
        endDate,
        status: 'ACTIVE',
      },
    });

    const paymentRef = `MEM-PAY-${Date.now()}-${Math.floor(Math.random() * 1000)}`;

    const payment = await tx.membershipPayment.create({
      data: {
        subscriptionId: sub.id,
        amount: plan.price,
        paymentMethod: data.paymentMethod,
        status: 'COMPLETED',
        transactionReference: paymentRef,
      },
    });

    // Activate membership record
    const updatedMembership = await tx.organizationMembership.update({
      where: { id: membership.id },
      data: {
        status: 'ACTIVE',
        tier: plan.name.toUpperCase().includes('VIP') ? 'VIP_GOLD' : 'STANDARD',
        expiryDate: endDate,
      },
    });

    // Record into financial ledger if plan price > 0
    if (plan.price > 0) {
      await tx.financialTransaction.create({
        data: {
          organizationId: orgId,
          type: 'INCOME',
          category: 'MEMBERSHIP_DUES',
          amount: plan.price,
          status: 'SETTLED',
          description: `Membership dues: ${plan.name} (${req.user!.fullName})`,
          reference: paymentRef,
          createdByUserId: userId,
        },
      });
    }

    return { sub, payment, updatedMembership };
  });

  await prisma.notification.create({
    data: {
      userId,
      title: 'Membership Activated!',
      message: `Your subscription to ${plan.name} is now active until ${endDate.toLocaleDateString()}. Enjoy member benefits!`,
      type: 'SUCCESS',
      linkUrl: '/members',
    },
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'MEMBERSHIP_PAID_ACTIVATED',
      entityType: 'MemberSubscription',
      entityId: result.sub.id,
      details: { plan: plan.name, amount: plan.price, reference: result.payment.transactionReference },
    });
  }

  res.status(201).json({
    success: true,
    message: 'Membership subscription successfully paid and activated',
    subscription: result.sub,
    membership: result.updatedMembership,
  });
}
