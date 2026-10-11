import { Request, Response } from 'express';
import bcrypt from 'bcryptjs';
import { z } from 'zod';
import prisma from '../lib/prisma.js';
import { generateToken } from '../middleware/auth.js';
import { seedDatabase } from '../lib/seed.js';

const registerSchema = z.object({
  email: z.string().email(),
  password: z.string().min(6),
  fullName: z.string().min(2),
  phone: z.string().optional(),
  organizationId: z.string().optional(),
  department: z.string().optional(),
  studentId: z.string().optional(),
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export async function register(req: Request, res: Response): Promise<void> {
  const data = registerSchema.parse(req.body);

  const existing = await prisma.user.findUnique({ where: { email: data.email } });
  if (existing) {
    res.status(400).json({ error: 'A user with this email address already exists' });
    return;
  }

  const passwordHash = await bcrypt.hash(data.password, 10);
  const user = await prisma.user.create({
    data: {
      email: data.email,
      passwordHash,
      fullName: data.fullName,
      phone: data.phone || null,
    },
  });

  // If organizationId provided, create a pending member record
  if (data.organizationId) {
    await prisma.organizationMembership.create({
      data: {
        userId: user.id,
        organizationId: data.organizationId,
        role: 'MEMBER',
        status: 'PENDING',
        department: data.department || null,
        studentId: data.studentId || null,
      },
    });
  }

  const token = generateToken({ id: user.id, email: user.email, isSuperAdmin: user.isSuperAdmin });

  res.status(201).json({
    token,
    user: {
      id: user.id,
      email: user.email,
      fullName: user.fullName,
      isSuperAdmin: user.isSuperAdmin,
    },
  });
}

export async function login(req: Request, res: Response): Promise<void> {
  const data = loginSchema.parse(req.body);

  const user = await prisma.user.findUnique({
    where: { email: data.email },
    include: {
      memberships: {
        include: { organization: true },
      },
    },
  });

  if (!user) {
    res.status(401).json({ error: 'Invalid email or password' });
    return;
  }

  const valid = await bcrypt.compare(data.password, user.passwordHash);
  if (!valid) {
    res.status(401).json({ error: 'Invalid email or password' });
    return;
  }

  const token = generateToken({ id: user.id, email: user.email, isSuperAdmin: user.isSuperAdmin });

  const activeMembership = user.memberships[0];

  res.json({
    token,
    user: {
      id: user.id,
      email: user.email,
      fullName: user.fullName,
      avatarUrl: user.avatarUrl,
      isSuperAdmin: user.isSuperAdmin,
      currentOrgId: activeMembership?.organizationId,
      currentRole: activeMembership?.role || 'MEMBER',
      memberships: user.memberships.map((m) => ({
        id: m.id,
        organizationId: m.organizationId,
        organizationName: m.organization.name,
        organizationSlug: m.organization.slug,
        role: m.role,
        status: m.status,
        tier: m.tier,
      })),
    },
  });
}

export async function getMe(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Unauthenticated' });
    return;
  }

  const user = await prisma.user.findUnique({
    where: { id: req.user.id },
    include: {
      memberships: {
        include: {
          organization: true,
          subscriptions: {
            where: { status: 'ACTIVE' },
            include: { plan: true },
          },
        },
      },
    },
  });

  if (!user) {
    res.status(404).json({ error: 'User not found' });
    return;
  }

  const requestedOrgId = (req.headers['x-organization-id'] as string) || req.user.currentOrgId;
  const currentMembership = user.memberships.find((m) => m.organizationId === requestedOrgId) || user.memberships[0];

  res.json({
    id: user.id,
    email: user.email,
    fullName: user.fullName,
    avatarUrl: user.avatarUrl,
    phone: user.phone,
    isSuperAdmin: user.isSuperAdmin,
    currentOrgId: currentMembership?.organizationId,
    currentRole: currentMembership?.role || (user.isSuperAdmin ? 'SUPER_ADMIN' : 'MEMBER'),
    currentOrganization: currentMembership?.organization,
    membershipStatus: currentMembership?.status || 'NONE',
    membershipTier: currentMembership?.tier || 'STANDARD',
    activeSubscription: currentMembership?.subscriptions[0] || null,
    memberships: user.memberships.map((m) => ({
      id: m.id,
      organizationId: m.organizationId,
      organizationName: m.organization.name,
      organizationSlug: m.organization.slug,
      role: m.role,
      status: m.status,
      tier: m.tier,
      expiryDate: m.expiryDate,
    })),
  });
}

export async function getDemoAccounts(_req: Request, res: Response): Promise<void> {
  res.json({
    demoAccounts: [
      {
        role: 'SUPER_ADMIN',
        roleLabel: 'Main Admin / Executive',
        email: 'kamalika@skyline.edu',
        password: '12345678',
        name: 'Kamalika',
        badge: 'Main Executive',
        description: 'Main System Executive & Super Club Administrator with full platform controls',
      },
      {
        role: 'SUPER_ADMIN',
        roleLabel: 'Platform Super Admin',
        email: 'superadmin@campussphere.edu',
        password: 'Admin@123',
        name: 'Dr. Harrison Vance',
        badge: 'Platform Wide',
        description: 'Multi-organization provisioning, system health & platform-level audits',
      },
      {
        role: 'CLUB_ADMIN',
        roleLabel: 'Club President',
        email: 'president@skyline.edu',
        password: 'Skyline@123',
        name: 'Elena Rostova',
        badge: 'Executive',
        description: 'Full club authority: members, events, merchandising, fundraising & settings',
      },
      {
        role: 'TREASURER',
        roleLabel: 'Club Treasurer',
        email: 'treasurer@skyline.edu',
        password: 'Skyline@123',
        name: 'Marcus Chen',
        badge: 'Financial Oversight',
        description: 'Ledger management, expense approvals, budget tracking & financial audits',
      },
      {
        role: 'EVENT_MANAGER',
        roleLabel: 'Event Manager',
        email: 'events@skyline.edu',
        password: 'Skyline@123',
        name: 'Sophia Martinez',
        badge: 'Operations',
        description: 'Event creation, seat tiers, live QR ticket scanner check-in & attendance',
      },
      {
        role: 'VOLUNTEER',
        roleLabel: 'Student Volunteer',
        email: 'volunteer@skyline.edu',
        password: 'Skyline@123',
        name: 'Liam O’Connor',
        badge: 'Field Ops',
        description: 'Assigned tasks board, fundraiser support, and expense reimbursement claims',
      },
      {
        role: 'MEMBER',
        roleLabel: 'Active Paid Member',
        email: 'member@skyline.edu',
        password: 'Skyline@123',
        name: 'Zara Patel',
        badge: 'Gold VIP Member',
        description: 'Member discounts, priority ticket bookings, QR wallet & merchandise store',
      },
      {
        role: 'STUDENT',
        roleLabel: 'Non-Member / General Student',
        email: 'student@skyline.edu',
        password: 'Skyline@123',
        name: 'Alex Rivera',
        badge: 'Campus General',
        description: 'General event discovery, non-member ticket registration & public store',
      },
    ],
  });
}

export async function resetDemoData(_req: Request, res: Response): Promise<void> {
  try {
    await seedDatabase();
    res.json({ success: true, message: 'Demo database safely reset to factory presentation state!' });
  } catch (err: any) {
    res.status(500).json({ error: 'Failed to reset demo database: ' + err.message });
  }
}
