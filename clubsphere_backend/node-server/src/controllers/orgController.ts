import { Request, Response } from 'express';
import { z } from 'zod';
import prisma from '../lib/prisma.js';
import { recordAuditLog } from '../middleware/audit.js';

const updateOrgSchema = z.object({
  name: z.string().min(2).optional(),
  description: z.string().optional(),
  logoUrl: z.string().optional(),
  primaryColor: z.string().optional(),
  currency: z.string().optional(),
});

const provisionOrgSchema = z.object({
  name: z.string().min(2),
  slug: z.string().min(2),
  description: z.string().optional(),
  primaryColor: z.string().optional(),
  currency: z.string().default('USD'),
});

export async function getCurrentOrg(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId;
  if (!orgId) {
    res.status(400).json({ error: 'No organization specified' });
    return;
  }

  const org = await prisma.organization.findUnique({
    where: { id: orgId },
    include: {
      _count: {
        select: {
          memberships: true,
          events: true,
          products: true,
        },
      },
    },
  });

  if (!org) {
    res.status(404).json({ error: 'Organization not found' });
    return;
  }

  res.json(org);
}

export async function listOrganizations(req: Request, res: Response): Promise<void> {
  const orgs = await prisma.organization.findMany({
    select: {
      id: true,
      name: true,
      slug: true,
      description: true,
      logoUrl: true,
      primaryColor: true,
      currency: true,
      createdAt: true,
    },
  });
  res.json(orgs);
}

export async function updateOrgSettings(req: Request, res: Response): Promise<void> {
  const orgId = req.organizationId!;
  const data = updateOrgSchema.parse(req.body);

  const updated = await prisma.organization.update({
    where: { id: orgId },
    data,
  });

  if (req.user) {
    await recordAuditLog({
      organizationId: orgId,
      actorUserId: req.user.id,
      action: 'ORGANIZATION_SETTINGS_UPDATED',
      entityType: 'Organization',
      entityId: orgId,
      details: data,
    });
  }

  res.json(updated);
}

export async function provisionOrganization(req: Request, res: Response): Promise<void> {
  const data = provisionOrgSchema.parse(req.body);

  const existing = await prisma.organization.findUnique({ where: { slug: data.slug } });
  if (existing) {
    res.status(400).json({ error: 'An organization with this slug URL already exists' });
    return;
  }

  const newOrg = await prisma.organization.create({
    data: {
      name: data.name,
      slug: data.slug,
      description: data.description || null,
      primaryColor: data.primaryColor || '#8b5cf6',
      currency: data.currency,
    },
  });

  // Automatically assign creator as CLUB_ADMIN
  if (req.user) {
    await prisma.organizationMembership.create({
      data: {
        userId: req.user.id,
        organizationId: newOrg.id,
        role: 'CLUB_ADMIN',
        status: 'ACTIVE',
        tier: 'FOUNDER',
      },
    });

    await recordAuditLog({
      organizationId: newOrg.id,
      actorUserId: req.user.id,
      action: 'ORGANIZATION_PROVISIONED',
      entityType: 'Organization',
      entityId: newOrg.id,
      details: { name: newOrg.name, slug: newOrg.slug },
    });
  }

  res.status(201).json(newOrg);
}
